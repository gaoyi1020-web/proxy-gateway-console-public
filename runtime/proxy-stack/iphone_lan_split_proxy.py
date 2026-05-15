#!/usr/bin/env python3
"""Same-LAN HTTP proxy for iPhone traffic with CN/private direct split.

The iPhone still uses one manual Wi-Fi HTTP proxy endpoint. This proxy decides
per CONNECT/HTTP target whether to connect directly from the host or forward
the request to the new upstream HTTP proxy.
"""

from __future__ import annotations

import argparse
import ipaddress
import logging
import select
import socket
import socketserver
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


HEADER_LIMIT = 65536
CACHE_TTL = 300

PRIVATE_NETS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "224.0.0.0/4",
        "240.0.0.0/4",
    )
)

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(frozen=True)
class RouteDecision:
    mode: str
    reason: str
    ips: tuple[str, ...] = ()


def load_networks(path: Path) -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    if not path.exists():
        return networks
    for line in path.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        network = ipaddress.ip_network(value, strict=False)
        if isinstance(network, ipaddress.IPv4Network):
            networks.append(network)
    return networks


def parse_patterns(value: str) -> list[str]:
    patterns: list[str] = []
    for item in value.split(","):
        item = item.strip().lower().strip(".")
        if item.startswith("*."):
            item = item[2:]
        if item:
            patterns.append(item)
    return patterns


def host_matches(host: str, patterns: list[str]) -> bool:
    host = host.lower().strip(".")
    return any(host == pattern or host.endswith(f".{pattern}") for pattern in patterns)


def parse_headers(raw: bytes) -> tuple[str, list[tuple[str, str]]]:
    text = raw.decode("iso-8859-1", errors="replace")
    lines = text.split("\r\n")
    headers: list[tuple[str, str]] = []
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers.append((name.strip(), value.lstrip()))
    return lines[0], headers


def recv_headers(sock: socket.socket, limit: int = HEADER_LIMIT) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError("request header too large")
    return bytes(data)


def proxy_status(response: bytes) -> int:
    line = response.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
    parts = line.split()
    if len(parts) >= 2 and parts[1].isdigit():
        return int(parts[1])
    return 0


def parse_host_port(value: str, default_port: int) -> tuple[str, int]:
    if value.startswith("["):
        host, _, rest = value[1:].partition("]")
        if rest.startswith(":"):
            return host, int(rest[1:])
        return host, default_port
    if ":" in value:
        host, port = value.rsplit(":", 1)
        return host, int(port)
    return value, default_port


def is_direct_ip(ip: ipaddress.IPv4Address, cn_networks: list[ipaddress.IPv4Network]) -> tuple[bool, str]:
    if any(ip in network for network in PRIVATE_NETS):
        return True, "private"
    if any(ip in network for network in cn_networks):
        return True, "cn-ip"
    return False, "foreign-ip"


def resolve_ipv4(host: str) -> list[str]:
    answers = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    ips: list[str] = []
    for item in answers:
        ip = item[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips


def choose_route(
    host: str,
    cn_networks: list[ipaddress.IPv4Network],
    force_direct: list[str],
    force_proxy: list[str],
    resolver=resolve_ipv4,
) -> RouteDecision:
    host = host.lower().strip(".")
    if host_matches(host, force_proxy):
        return RouteDecision("proxy", "force-proxy")
    if host_matches(host, force_direct):
        return RouteDecision("direct", "force-direct")

    try:
        ip = ipaddress.ip_address(host)
        if not isinstance(ip, ipaddress.IPv4Address):
            return RouteDecision("proxy", "non-ipv4")
        direct, reason = is_direct_ip(ip, cn_networks)
        return RouteDecision("direct" if direct else "proxy", reason, (str(ip),))
    except ValueError:
        pass

    try:
        ips = resolver(host)
    except OSError as error:
        return RouteDecision("proxy", f"dns-failed:{type(error).__name__}")
    if not ips:
        return RouteDecision("proxy", "dns-empty")

    parsed = [ipaddress.ip_address(item) for item in ips]
    direct_reasons = []
    for ip in parsed:
        if not isinstance(ip, ipaddress.IPv4Address):
            return RouteDecision("proxy", "non-ipv4", tuple(ips))
        direct, reason = is_direct_ip(ip, cn_networks)
        if not direct:
            return RouteDecision("proxy", reason, tuple(ips))
        direct_reasons.append(reason)
    reason = "private" if all(item == "private" for item in direct_reasons) else "cn-ip"
    return RouteDecision("direct", reason, tuple(ips))


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class SplitHttpProxy(socketserver.BaseRequestHandler):
    allow_nets: list[ipaddress._BaseNetwork] = []
    cn_networks: list[ipaddress.IPv4Network] = []
    force_direct: list[str] = []
    force_proxy: list[str] = []
    upstream_host = "127.0.0.1"
    upstream_port = 18122
    connect_timeout = 6.0
    idle_timeout = 180.0
    cache: dict[str, tuple[float, RouteDecision]] = {}
    cache_lock = threading.Lock()

    def allowed(self) -> bool:
        peer = ipaddress.ip_address(self.client_address[0])
        return any(peer in net for net in self.allow_nets)

    def route(self, host: str) -> RouteDecision:
        now = time.time()
        key = host.lower().strip(".")
        with self.cache_lock:
            cached = self.cache.get(key)
            if cached and now - cached[0] < CACHE_TTL:
                return cached[1]
        decision = choose_route(key, self.cn_networks, self.force_direct, self.force_proxy)
        with self.cache_lock:
            self.cache[key] = (now, decision)
        return decision

    def open_direct(self, host: str, port: int) -> socket.socket:
        remote = socket.create_connection((host, port), timeout=self.connect_timeout)
        remote.settimeout(self.idle_timeout)
        return remote

    def open_upstream(self) -> socket.socket:
        remote = socket.create_connection((self.upstream_host, self.upstream_port), timeout=self.connect_timeout)
        remote.settimeout(self.idle_timeout)
        return remote

    def tunnel(self, a: socket.socket, b: socket.socket) -> None:
        sockets = [a, b]
        for sock in sockets:
            sock.setblocking(False)
        while True:
            readable, _, errored = select.select(sockets, [], sockets, self.idle_timeout)
            if errored or not readable:
                return
            for sock in readable:
                try:
                    chunk = sock.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                other = b if sock is a else a
                try:
                    other.sendall(chunk)
                except OSError:
                    return

    def fail(self, code: int, message: str) -> None:
        body = f"iphone lan proxy: {message}\n".encode("utf-8")
        response = (
            f"HTTP/1.1 {code} Bad Gateway\r\n"
            "Connection: close\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode("ascii") + body
        self.request.sendall(response)

    def log_route(self, method: str, target: str, decision: RouteDecision) -> None:
        ips = ",".join(decision.ips)
        suffix = f" ips={ips}" if ips else ""
        logging.info(
            "%s %s route=%s reason=%s client=%s%s",
            method,
            target,
            decision.mode,
            decision.reason,
            self.client_address[0],
            suffix,
        )

    def handle_connect(self, raw: bytes, target: str) -> None:
        host, port = parse_host_port(target, 443)
        decision = self.route(host)
        if decision.mode == "direct":
            remote = self.open_direct(host, port)
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.log_route("CONNECT", f"{host}:{port}", decision)
            with remote:
                self.tunnel(self.request, remote)
            return

        remote = self.open_upstream()
        remote.sendall(raw)
        response = recv_headers(remote)
        code = proxy_status(response)
        if code != 200:
            remote.close()
            raise OSError(f"upstream CONNECT returned {code}")
        self.request.sendall(response)
        self.log_route("CONNECT", f"{host}:{port}", decision)
        with remote:
            self.tunnel(self.request, remote)

    def handle_http(self, raw: bytes, method: str, target: str, version: str, headers: list[tuple[str, str]], body: bytes) -> None:
        url = urlsplit(target)
        if url.scheme and url.netloc:
            host, port = parse_host_port(url.netloc, 443 if url.scheme == "https" else 80)
            path = url.path or "/"
            if url.query:
                path += "?" + url.query
        else:
            host_header = next((v for k, v in headers if k.lower() == "host"), "")
            if not host_header:
                self.request.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                return
            host, port = parse_host_port(host_header, 80)
            path = target or "/"

        decision = self.route(host)
        if decision.mode == "proxy":
            remote = self.open_upstream()
            remote.sendall(raw)
            self.log_route(method, target, decision)
            with remote:
                self.tunnel(self.request, remote)
            return

        outbound_headers = [(k, v) for k, v in headers if k.lower() not in HOP_BY_HOP]
        outbound_headers.append(("Connection", "close"))
        head = f"{method} {path} {version}\r\n".encode("iso-8859-1")
        for key, value in outbound_headers:
            head += f"{key}: {value}\r\n".encode("iso-8859-1")
        head += b"\r\n"

        remote = self.open_direct(host, port)
        self.log_route(method, f"{host}:{port}{path}", decision)
        with remote:
            remote.sendall(head + body)
            while True:
                chunk = remote.recv(65536)
                if not chunk:
                    return
                self.request.sendall(chunk)

    def handle(self) -> None:
        logging.info("accepted client %s:%s", self.client_address[0], self.client_address[1])
        if not self.allowed():
            logging.warning("rejected client %s", self.client_address[0])
            self.request.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\n")
            return
        try:
            raw = recv_headers(self.request)
            if not raw:
                return
            head, _, body = raw.partition(b"\r\n\r\n")
            request_line, headers = parse_headers(head)
            parts = request_line.split()
            if len(parts) != 3:
                self.request.sendall(b"HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n")
                return
            method, target, version = parts
            if method.upper() == "CONNECT":
                self.handle_connect(raw, target)
            else:
                self.handle_http(raw, method, target, version, headers, body)
        except Exception as error:  # noqa: BLE001 - keep service alive per request.
            logging.warning("request from %s failed: %s", self.client_address[0], error)
            try:
                self.fail(502, str(error))
            except OSError:
                return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--listen-port", type=int, default=18181)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, default=18122)
    parser.add_argument("--allow-cidr", action="append", default=[])
    parser.add_argument("--cn-routes", default=str(Path.home() / ".local" / "share" / "hotspot-split-gateway" / "cn_ipv4.txt"))
    parser.add_argument("--force-direct", default="")
    parser.add_argument("--force-proxy", default="google.com,googlevideo.com,gstatic.com,ytimg.com,youtube.com,ggpht.com")
    parser.add_argument("--log-file", default="")
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log_file or None,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    SplitHttpProxy.allow_nets = [ipaddress.ip_network(item, strict=False) for item in args.allow_cidr]
    SplitHttpProxy.cn_networks = load_networks(Path(args.cn_routes))
    SplitHttpProxy.force_direct = parse_patterns(args.force_direct)
    SplitHttpProxy.force_proxy = parse_patterns(args.force_proxy)
    SplitHttpProxy.upstream_host = args.upstream_host
    SplitHttpProxy.upstream_port = args.upstream_port
    with ThreadedServer((args.listen_host, args.listen_port), SplitHttpProxy) as server:
        logging.info(
            "iphone LAN split proxy listening on %s:%s direct=CN/private upstream=%s:%s allow=%s",
            args.listen_host,
            args.listen_port,
            args.upstream_host,
            args.upstream_port,
            ",".join(args.allow_cidr),
        )
        server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
