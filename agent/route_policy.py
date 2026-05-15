from __future__ import annotations

import ipaddress
from typing import Any


def decide_route(target: str, profile: dict[str, Any]) -> dict[str, Any]:
    split_rules = profile.get("splitRules", {})
    policy = split_rules.get("policy", "cn-private-direct-foreign-proxy")
    if policy == "all-direct":
        return _decision("direct", "policy-all-direct")
    if policy == "all-proxy":
        return _decision(split_rules.get("foreign", "new"), "policy-all-proxy")
    if _is_private_target(target):
        return _decision(split_rules.get("private", "direct"), "private")
    if _is_domestic_hint(target):
        return _decision(split_rules.get("domestic", "direct"), "domestic-hint")
    return _decision(split_rules.get("foreign", "new"), "foreign-default")


def failover_order(profile: dict[str, Any], route_id: str = "failover") -> list[str]:
    route = profile.get("routes", {}).get(route_id, {})
    order = route.get("order", [])
    return list(order) if isinstance(order, list) else []


def _is_private_target(target: str) -> bool:
    host = target.split(":", 1)[0].strip("[]")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return host.endswith(".local") or host == "localhost"
    return ip.is_private or ip.is_loopback or ip.is_link_local


def _is_domestic_hint(target: str) -> bool:
    host = target.split(":", 1)[0].lower()
    return host.endswith(".cn") or host.endswith(".com.cn")


def _decision(route: str, reason: str) -> dict[str, Any]:
    return {
        "route": route,
        "direct": route == "direct",
        "reason": reason,
    }
