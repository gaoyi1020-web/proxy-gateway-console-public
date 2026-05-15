#!/usr/bin/env python3
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 15
LAN_PROXY_URL = os.environ.get("PROXY_GATEWAY_LAN_PROXY_URL", "")

PROBES = [
    {
        "id": "naked-domestic-baidu",
        "route": "naked",
        "url": "https://www.baidu.com/",
        "expect": "domestic-200"
    },
    {
        "id": "naked-foreign-google",
        "route": "naked",
        "url": "https://www.google.com/generate_204",
        "expect": "timeout-or-blocked"
    },
    {
        "id": "unified-http-google",
        "route": "proxy",
        "proxy": "http://127.0.0.1:18180",
        "url": "https://www.google.com/generate_204",
        "expect": "204"
    },
    {
        "id": "unified-http-chatgpt-trace",
        "route": "proxy",
        "proxy": "http://127.0.0.1:18180",
        "url": "https://chatgpt.com/cdn-cgi/trace",
        "expect": "trace-us"
    },
]

if LAN_PROXY_URL:
    PROBES.append({
        "id": "lan-proxy-google",
        "route": "proxy",
        "proxy": LAN_PROXY_URL,
        "url": "https://www.google.com/generate_204",
        "expect": "204"
    })


def opener_for(probe):
    if probe["route"] == "naked":
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    proxy = probe["proxy"]
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    )


def parse_trace(body):
    trace = {}
    for line in body.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in {"ip", "loc", "colo", "http", "tls"}:
                trace[key] = value
    return trace


def run_probe(probe):
    started = time.monotonic()
    result = {
        "id": probe["id"],
        "route": probe["route"],
        "proxy": probe.get("proxy", ""),
        "url": probe["url"],
        "expect": probe["expect"],
        "ok": False,
        "status": "error",
        "httpCode": 0,
        "elapsedSeconds": 0.0,
        "trace": {}
    }
    try:
        request = urllib.request.Request(
            probe["url"],
            headers={"User-Agent": "proxy-gateway-network-smoke/1.0"}
        )
        with opener_for(probe).open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(8192).decode("utf-8", "replace")
            result["httpCode"] = response.status
            result["trace"] = parse_trace(body)
            result["status"] = "pass"
            result["ok"] = True
    except urllib.error.HTTPError as error:
        result["httpCode"] = error.code
        result["status"] = "http-error"
    except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError) as error:
        result["status"] = type(error).__name__
        result["error"] = str(error)[:240]
    finally:
        result["elapsedSeconds"] = round(time.monotonic() - started, 3)
    return result


def classify(results):
    blockers = []
    by_id = {item["id"]: item for item in results}
    if by_id["unified-http-google"]["httpCode"] != 204:
        blockers.append("unified-http-google")
    if "lan-proxy-google" in by_id and by_id["lan-proxy-google"]["httpCode"] != 204:
        blockers.append("lan-proxy-google")
    trace = by_id["unified-http-chatgpt-trace"]["trace"]
    if trace.get("loc") != "US":
        blockers.append("unified-http-chatgpt-trace-us-exit")
    return {
        "ok": not blockers,
        "blockers": blockers,
        "summary": "network smoke passed" if not blockers else "network smoke has blockers"
    }


def main():
    results = [run_probe(probe) for probe in PROBES]
    payload = {
        "schema": "proxy-gateway-network-smoke.v1",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "results": results,
        "classification": classify(results)
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
