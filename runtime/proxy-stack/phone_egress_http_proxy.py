#!/usr/bin/env python3
"""Explicit HTTP proxy for USB phone egress.

The proxy never changes the host default route. Outbound sockets bind to the
phone tether source IP; a source-policy routing table decides where those
packets go.
"""

from __future__ import annotations

import argparse
import logging
import select
import socket
import socketserver
from urllib.parse import urlsplit


HEADER_LIMIT = 65536


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


def host_header(raw: bytes) -> str:
    for line in raw.split(b"\r\n")[1:]:
        if line.lower().startswith(b"host:"):
            return line.split(b":", 1)[1].decode("iso-8859-1", errors="replace").strip()
    return ""


def split_host_port(value: str, default_port: int) -> tuple[str, int]:
    if value.startswith("[") and "]" in value:
        host, _, tail = value[1:].partition("]")
        port = int(tail[1:]) if tail.startswith(":") else default_port
        return host, port
    if ":" in value:
        host, port_text = value.rsplit(":", 1)
        if port_text.isdigit():
            return host, int(port_text)
    return value, default_port


def origin_request(raw: bytes, target: str) -> bytes:
    parsed = urlsplit(target)
    if not parsed.scheme or not parsed.netloc:
        return raw
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    first, rest = raw.split(b"\r\n", 1)
    parts = first.split()
    if len(parts) != 3:
        return raw
    return b" ".join([parts[0], path.encode("ascii", errors="ignore"), parts[2]]) + b"\r\n" + rest


class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class PhoneEgressProxy(socketserver.BaseRequestHandler):
    source_ip = ""
    connect_timeout = 8.0
    idle_timeout = 120.0

    def open_remote(self, host: str, port: int) -> socket.socket:
        errors: list[str] = []
        for family, socktype, proto, _canon, address in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
            sock = socket.socket(family, socktype, proto)
            try:
                bind_address = (self.source_ip, 0) if family == socket.AF_INET else ("::", 0, 0, 0)
                sock.bind(bind_address)
                sock.settimeout(self.connect_timeout)
                sock.connect(address)
                sock.settimeout(self.idle_timeout)
                return sock
            except OSError as error:
                errors.append(str(error))
                sock.close()
        raise OSError("; ".join(errors) or "connect failed")

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

    def fail(self, message: str) -> None:
        body = f"phone egress proxy: {message}\n".encode("utf-8")
        response = (
            b"HTTP/1.1 502 Bad Gateway\r\n"
            b"Connection: close\r\n"
            b"Content-Type: text/plain; charset=utf-8\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            + body
        )
        self.request.sendall(response)

    def handle_connect(self, target: str) -> None:
        host, port = split_host_port(target, 443)
        with self.open_remote(host, port) as remote:
            logging.info("CONNECT %s:%s via %s", host, port, self.source_ip)
            self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            self.tunnel(self.request, remote)

    def handle_forward(self, raw: bytes, method: str, target: str) -> None:
        parsed = urlsplit(target)
        if parsed.scheme and parsed.netloc:
            host, port = split_host_port(parsed.netloc, 443 if parsed.scheme == "https" else 80)
            outbound = origin_request(raw, target)
        else:
            host, port = split_host_port(host_header(raw), 80)
            outbound = raw
        if not host:
            self.fail("missing host")
            return
        with self.open_remote(host, port) as remote:
            logging.info("%s %s:%s via %s", method, host, port, self.source_ip)
            remote.sendall(outbound)
            self.tunnel(self.request, remote)

    def handle(self) -> None:
        try:
            raw = recv_headers(self.request)
            if not raw:
                return
            request_line = raw.split(b"\r\n", 1)[0].decode("iso-8859-1", errors="replace")
            parts = request_line.split()
            if len(parts) < 3:
                self.fail("bad request line")
                return
            method, target = parts[0].upper(), parts[1]
            if method == "CONNECT":
                self.handle_connect(target)
            else:
                self.handle_forward(raw, method, target)
        except Exception as error:  # noqa: BLE001 - proxy must fail closed per request.
            logging.exception("request failed: %s", error)
            try:
                self.fail(str(error))
            except OSError:
                return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=18190)
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--log-file", default="")
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log_file or None,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    PhoneEgressProxy.source_ip = args.source_ip
    with ThreadedServer((args.listen_host, args.listen_port), PhoneEgressProxy) as server:
        logging.info("phone egress proxy listening on %s:%s source=%s", args.listen_host, args.listen_port, args.source_ip)
        server.serve_forever()


if __name__ == "__main__":
    main()
