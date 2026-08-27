import json
from typing import Any, Mapping


_PUBLIC_FIELDS = (
    "business_id",
    "business_name_snapshot",
    "thread_id",
    "account_id",
    "product_id",
    "pod_id",
    "device_strategy",
    "pod_ids",
    "tos_bucket",
    "tos_endpoint",
    "tos_region",
    "timeout_seconds",
    "device_wait_timeout_seconds",
    "use_base64_screenshot",
    "max_step",
    "callback_info",
    "output_schema",
    "retry_limit",
    "system_prompt",
    "screen_record",
    "mcp_json",
    "max_output_tokens",
    "gps_info",
    "request_headers",
)
_JSON_FIELDS = frozenset({"mcp_json", "output_schema"})
_SENSITIVE_KEY_PARTS = (
    "access_key",
    "accesskey",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
)


def public_execution_config(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    values = dict(snapshot or {})
    raw_source = values.get("config_source")
    result: dict[str, Any] = {
        "source": raw_source
        if raw_source in {"global", "custom", "case_default"}
        else "legacy",
    }
    for field in _PUBLIC_FIELDS:
        value = values.get(field)
        if field == "request_headers":
            value = _header_state(value)
        elif field in _JSON_FIELDS:
            value = _sanitize_json_string(value)
        else:
            value = _sanitize_value(value)
        result[field] = value
    return result


def _header_state(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or not value:
        return {"configured": False, "names": [], "items": []}
    items = [
        {
            "name": str(key),
            "value": _sanitize_header_value(str(key), item),
        }
        for key, item in value.items()
    ]
    return {
        "configured": True,
        "names": [item["name"] for item in items],
        "items": items,
    }


def _sanitize_header_value(name: str, value: object) -> str:
    text = str(value)
    if not _is_sensitive_key(name):
        return text
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}***{text[-4:]}"


def _sanitize_json_string(value: object) -> object:
    if not isinstance(value, str) or not value.strip():
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return value
    return json.dumps(
        _sanitize_value(parsed),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _sanitize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "***"
                if _is_sensitive_key(str(key))
                else _sanitize_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)
