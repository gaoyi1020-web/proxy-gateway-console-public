#!/usr/bin/env python3
"""Small TCP bridge for exposing a local-only proxy on a LAN address."""

from __future__ import annotations

import argparse
import ipaddress
import logging
import selectors
import socket
import threading
from typing import Iterable


def parse_networks(values: Iterable[str]) -> list[ipaddress._BaseNetwork]:
    networks = []
    for value in values:
        if not value:
            continue
        networks.append(ipaddress.ip_network(value, strict=False))
    return networks


def client_allowed(host: str, networks: list[ipaddress._BaseNetwork]) -> bool:
    if not networks:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in networks)


def relay(client: socket.socket, target_host: str, target_port: int) -> None:
    peer = client.getpeername()
    try:
        upstream = socket.create_connection((target_host, target_port), timeout=8)
    except OSError as error:
        logging.warning("upstream connect failed for %s: %s", peer, error)
        client.close()
        return

    selector = selectors.DefaultSelector()
    sockets = {client: upstream, upstream: client}
    for sock in sockets:
        sock.setblocking(False)
        selector.register(sock, selectors.EVENT_READ)

    try:
        while sockets:
            for key, _ in selector.select(timeout=60):
                source = key.fileobj
                target = sockets.get(source)
                if target is None:
                    continue
                try:
                    data = source.recv(65536)
                except OSError:
                    data = b""
                if not data:
                    for sock in (source, target):
                        if sock in sockets:
                            try:
                                selector.unregister(sock)
                            except Exception:  # noqa: BLE001 - best-effort close path
                                pass
                            sockets.pop(sock, None)
                            sock.close()
                    break
                try:
                    target.sendall(data)
                except OSError:
                    return
    finally:
        for sock in list(sockets):
            try:
                selector.unregister(sock)
            except Exception:  # noqa: BLE001 - best-effort close path
                pass
            sock.close()
        selector.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Expose a local TCP service on a LAN bind address.")
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument("--target-host", default="127.0.0.1")
    parser.add_argument("--target-port", type=int, default=18122)
    parser.add_argument("--allow-cidr", action="append", default=[])
    parser.add_argument("--log-file", default="")
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log_file or None,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    networks = parse_networks(args.allow_cidr)
    server = socket.create_server((args.listen_host, args.listen_port), reuse_port=False)
    server.listen(64)
    logging.info(
        "listening on %s:%s -> %s:%s allow=%s",
        args.listen_host,
        args.listen_port,
        args.target_host,
        args.target_port,
        ",".join(str(item) for item in networks) or "all",
    )
    try:
        while True:
            client, address = server.accept()
            if not client_allowed(address[0], networks):
                logging.warning("rejected client %s outside allow list", address[0])
                client.close()
                continue
            logging.info("accepted client %s:%s", address[0], address[1])
            thread = threading.Thread(
                target=relay,
                args=(client, args.target_host, args.target_port),
                daemon=True,
            )
            thread.start()
    finally:
        server.close()


if __name__ == "__main__":
    raise SystemExit(main())
