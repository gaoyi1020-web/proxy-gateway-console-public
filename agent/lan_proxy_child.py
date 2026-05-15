#!/usr/bin/env python3
from __future__ import annotations

import argparse
import select
import socket
import socketserver


class ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def make_handler(upstream_host: str, upstream_port: int):
    class ProxyHandler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            with socket.create_connection((upstream_host, upstream_port), timeout=10) as upstream:
                self.request.setblocking(False)
                upstream.setblocking(False)
                sockets = [self.request, upstream]
                while True:
                    readable, _, errored = select.select(sockets, [], sockets, 30)
                    if errored:
                        return
                    if not readable:
                        return
                    for source in readable:
                        try:
                            data = source.recv(65536)
                        except OSError:
                            return
                        if not data:
                            return
                        target = upstream if source is self.request else self.request
                        try:
                            target.sendall(data)
                        except OSError:
                            return

    return ProxyHandler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="v2 LAN proxy child TCP bridge")
    parser.add_argument("--listen-host", required=True)
    parser.add_argument("--listen-port", required=True, type=int)
    parser.add_argument("--upstream-host", required=True)
    parser.add_argument("--upstream-port", required=True, type=int)
    args = parser.parse_args(argv)

    handler = make_handler(args.upstream_host, args.upstream_port)
    with ThreadingTCPServer((args.listen_host, args.listen_port), handler) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
