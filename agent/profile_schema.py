from __future__ import annotations

from copy import deepcopy
from typing import Any


SUPPORTED_VERSION = 2
ROUTE_TYPES = {"http", "socks", "failover", "lanProxy", "direct", "adapter"}
SPLIT_POLICIES = {"cn-private-direct-foreign-proxy", "all-proxy", "all-direct"}
SECRET_KEYS = {"password", "passwd", "secret", "token", "auth", "credential"}


class ProfileValidationError(ValueError):
    pass


def redacted_profile_template() -> dict[str, Any]:
    return {
        "version": SUPPORTED_VERSION,
        "name": "linux-lan-gateway",
        "routes": {
            "old": {
                "type": "http",
                "endpoint": "http://127.0.0.1:8118",
                "authRef": "usb-profile:old",
            },
            "new": {
                "type": "http",
                "endpoint": "http://127.0.0.1:18122",
                "authRef": "usb-profile:new",
            },
            "failover": {
                "type": "failover",
                "order": ["old", "new"],
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
            "foreign": "new",
        },
        "privacy": {
            "logs": "redacted",
            "state": "tmpfs-or-usb",
        },
    }


def validate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(profile, dict):
        raise ProfileValidationError("profile must be an object")
    if profile.get("version") != SUPPORTED_VERSION:
        raise ProfileValidationError(f"profile version must be {SUPPORTED_VERSION}")

    routes = profile.get("routes")
    if not isinstance(routes, dict) or not routes:
        raise ProfileValidationError("routes must be a non-empty object")

    for route_id, route in routes.items():
        _validate_route(route_id, route, routes)

    split_rules = profile.get("splitRules", {})
    if split_rules:
        _validate_split_rules(split_rules, routes)

    ui = profile.get("ui", {})
    if ui:
        _validate_ui(ui, routes)

    privacy = profile.get("privacy", {})
    if privacy and not isinstance(privacy, dict):
        raise ProfileValidationError("privacy must be an object")

    _reject_inline_secrets(profile)
    return deepcopy(profile)


def migrate_v1_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    profile = redacted_profile_template()
    ports = {item.get("id"): item for item in runtime.get("ports", []) if isinstance(item, dict)}
    old_http = ports.get("old-http", {})
    new_http = ports.get("new-http", {})
    failover = ports.get("failover", {})
    iphone_lan = runtime.get("iphone_lan_proxy", {})

    if old_http.get("host") and old_http.get("port"):
        profile["routes"]["old"]["endpoint"] = f"http://{old_http['host']}:{old_http['port']}"
    if new_http.get("host") and new_http.get("port"):
        profile["routes"]["new"]["endpoint"] = f"http://{new_http['host']}:{new_http['port']}"
    if failover.get("host") and failover.get("port"):
        profile["routes"]["failover"]["endpoint"] = f"http://{failover['host']}:{failover['port']}"
    if iphone_lan.get("setting"):
        profile["routes"]["lanProxy"]["settingHint"] = iphone_lan["setting"]

    return validate_profile(profile)


def _validate_route(route_id: str, route: Any, routes: dict[str, Any]) -> None:
    if not isinstance(route_id, str) or not route_id:
        raise ProfileValidationError("route id must be a non-empty string")
    if not isinstance(route, dict):
        raise ProfileValidationError(f"route {route_id} must be an object")

    route_type = route.get("type")
    if route_type not in ROUTE_TYPES:
        raise ProfileValidationError(f"route {route_id} has unsupported type")

    if route_type in {"http", "socks"}:
        endpoint = route.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith(("http://", "socks5://", "127.0.0.1", "localhost")):
            raise ProfileValidationError(f"route {route_id} endpoint must be local or URL-like")

    if route_type == "failover":
        order = route.get("order")
        if not isinstance(order, list) or len(order) < 2:
            raise ProfileValidationError(f"route {route_id} failover order must contain at least two routes")
        missing = [item for item in order if item not in routes]
        if missing:
            raise ProfileValidationError(f"route {route_id} references missing routes: {', '.join(missing)}")

    if route_type == "lanProxy":
        policy = route.get("policy", "cn-private-direct-foreign-proxy")
        if policy not in SPLIT_POLICIES:
            raise ProfileValidationError(f"route {route_id} policy is unsupported")

    if route_type == "adapter":
        adapter_kind = route.get("adapterKind")
        auth_ref = route.get("authRef")
        if adapter_kind != "sing-box-outbound":
            raise ProfileValidationError(f"route {route_id} adapterKind is unsupported")
        if not isinstance(auth_ref, str) or not auth_ref.startswith("adapter:sing-box:"):
            raise ProfileValidationError(f"route {route_id} adapter authRef is required")


def _validate_split_rules(split_rules: dict[str, Any], routes: dict[str, Any]) -> None:
    policy = split_rules.get("policy", "cn-private-direct-foreign-proxy")
    if policy not in SPLIT_POLICIES:
        raise ProfileValidationError("splitRules policy is unsupported")
    for key in ("domestic", "private", "foreign"):
        target = split_rules.get(key)
        if target and target != "direct" and target not in routes:
            raise ProfileValidationError(f"splitRules {key} references missing route")


def _validate_ui(ui: dict[str, Any], routes: dict[str, Any]) -> None:
    if not isinstance(ui, dict):
        raise ProfileValidationError("ui must be an object")

    default_region = ui.get("defaultRegion")
    if default_region is not None:
        if not isinstance(default_region, str) or default_region not in routes:
            raise ProfileValidationError("ui defaultRegion must reference a route")

    regions = ui.get("regions", [])
    if regions:
        if not isinstance(regions, list):
            raise ProfileValidationError("ui regions must be a list")
        for index, region in enumerate(regions):
            if not isinstance(region, dict):
                raise ProfileValidationError(f"ui region #{index + 1} must be an object")
            region_id = region.get("id")
            label = region.get("label")
            if not isinstance(region_id, str) or region_id not in routes:
                raise ProfileValidationError(f"ui region #{index + 1} id must reference a route")
            if not isinstance(label, str) or not label:
                raise ProfileValidationError(f"ui region #{index + 1} label is required")


def _reject_inline_secrets(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in SECRET_KEYS and child:
                raise ProfileValidationError(f"inline secret field is not allowed: {path}{key}")
            _reject_inline_secrets(child, f"{path}{key}.")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_inline_secrets(child, f"{path}{index}.")
