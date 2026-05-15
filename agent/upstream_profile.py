from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from .profile_schema import validate_profile
except ImportError:
    from profile_schema import validate_profile


TAG_PATTERN = re.compile(r"[^a-zA-Z0-9_-]+")


def load_upstream_json(path: str | Path) -> dict[str, Any]:
    try:
        upstream = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError("upstream adapter is missing") from error
    except json.JSONDecodeError as error:
        raise ValueError("upstream adapter is not valid JSON") from error
    if not isinstance(upstream, dict):
        raise ValueError("upstream adapter must be an object")
    return upstream


def upstream_to_profile(upstream: dict[str, Any], name: str = "imported-upstream") -> dict[str, Any]:
    outbounds = upstream.get("outbounds")
    if not isinstance(outbounds, list) or not outbounds:
        raise ValueError("upstream adapter outbounds must be a non-empty list")

    routes: dict[str, dict[str, Any]] = {}
    regions: list[dict[str, str]] = []
    seen: set[str] = set()

    for index, outbound in enumerate(outbounds, start=1):
        if not isinstance(outbound, dict):
            continue
        raw_tag = outbound.get("tag")
        if not isinstance(raw_tag, str) or not raw_tag.strip():
            continue
        route_id = normalize_route_id(raw_tag)
        if not route_id or route_id in seen:
            continue
        seen.add(route_id)
        routes[route_id] = {
            "type": "adapter",
            "adapterKind": "sing-box-outbound",
            "authRef": f"adapter:sing-box:{route_id}",
            "label": raw_tag,
        }
        regions.append({"id": route_id, "label": raw_tag})

    if not routes:
        raise ValueError("upstream adapter has no tagged outbounds")

    final = upstream.get("final")
    default_region = normalize_route_id(final) if isinstance(final, str) else next(iter(routes))
    if default_region not in routes:
        default_region = next(iter(routes))

    profile = {
        "version": 2,
        "name": name,
        "routes": {
            **routes,
            "failover": {
                "type": "failover",
                "order": list(routes.keys())[:2] if len(routes) > 1 else [default_region, default_region],
            },
            "lanProxy": {
                "type": "lanProxy",
                "bind": "dynamic",
                "policy": "cn-private-direct-foreign-proxy",
            },
        },
        "splitRules": {
            "policy": "cn-private-direct-foreign-proxy",
            "domestic": "direct",
            "private": "direct",
            "foreign": default_region,
        },
        "ui": {
            "defaultRegion": default_region,
            "regions": regions,
        },
        "adapterSources": {
            "singBoxUpstream": {
                "outboundCount": len(routes),
                "defaultRoute": default_region,
            },
        },
        "privacy": {
            "logs": "redacted",
            "state": "tmpfs-or-usb",
        },
    }
    return validate_profile(profile)


def normalize_route_id(tag: str) -> str:
    normalized = TAG_PATTERN.sub("-", tag.strip().lower())
    normalized = normalized.strip("-")
    if not normalized:
        return ""
    if normalized[0].isdigit():
        normalized = f"route-{normalized}"
    return normalized[:48]
