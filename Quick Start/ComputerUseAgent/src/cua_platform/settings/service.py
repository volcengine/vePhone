import json
from typing import Any

from cua_platform.settings.audit import add_runner_settings_audit
from cua_platform.settings.repository import SettingRepository
from cua_platform.settings.schemas import (
    RunnerConfig,
    RunnerSettingsUpdate,
    validate_request_headers,
)
from cua_platform.business.models import DEFAULT_BUSINESS_ID

_FIELDS = (
    "access_key_id",
    "secret_access_key",
    "product_id",
    "account_id",
    "sts_role_trn",
    "stream_token_ttl_seconds",
    "pod_id",
    "ark_api_key",
    "tos_bucket",
    "tos_endpoint",
    "tos_region",
    "use_base64_screenshot",
    "max_step",
    "timeout_seconds",
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
_REQUIRED_COMPUTER_USE_FIELDS = (
    "access_key_id",
    "secret_access_key",
    "account_id",
)
_CLEARABLE_COMPUTER_USE_FIELDS = {
    "callback_info",
    "output_schema",
    "system_prompt",
    "mcp_json",
    "max_output_tokens",
    "request_headers",
}


class RunnerSettingsValidationError(ValueError):
    def __init__(self, code: str, details: dict[str, Any]) -> None:
        super().__init__(code)
        self.code = code
        self.details = details


class SettingsService:
    def __init__(self, repository: SettingRepository) -> None:
        self.repository = repository

    def get_runner_config(self, business_id: str | None = None) -> RunnerConfig:
        mode = (
            self._get_setting("runner.mode", business_id)
            or "mobile_use"
        )
        values = {
            field: _deserialize_field(
                field,
                self._get_setting(f"runner.mobile_use.{field}", business_id),
            )
            for field in _FIELDS
        }
        return RunnerConfig(
            mode=mode,
            **{field: value for field, value in values.items() if value is not None},
        )

    def get_public_settings(self, business_id: str | None = None) -> dict[str, Any]:
        config = self.get_runner_config(business_id)
        return {
            "mode": config.mode,
            "mobile_use": {
                "access_key_id": _masked_access_key(config.access_key_id),
                "secret_access_key": {"configured": config.secret_access_key is not None},
                "product_id": config.product_id,
                "account_id": config.account_id,
                "sts_role_trn": config.sts_role_trn,
                "stream_token_ttl_seconds": config.stream_token_ttl_seconds,
                "pod_id": config.pod_id,
                "ark_api_key": {"configured": config.ark_api_key is not None},
                "tos_bucket": config.tos_bucket,
                "tos_endpoint": config.tos_endpoint,
                "tos_region": config.tos_region,
                "use_base64_screenshot": config.use_base64_screenshot,
                "max_step": config.max_step,
                "timeout_seconds": config.timeout_seconds,
                "callback_info": config.callback_info,
                "output_schema": config.output_schema,
                "retry_limit": config.retry_limit,
                "system_prompt": config.system_prompt,
                "screen_record": config.screen_record,
                "mcp_json": config.mcp_json,
                "max_output_tokens": config.max_output_tokens,
                "gps_info": config.gps_info,
                "request_headers": _header_state(config.request_headers),
            },
        }

    def update_runner(
        self,
        payload: RunnerSettingsUpdate,
        actor_user_id: int,
        business_id: str | None = None,
    ) -> dict[str, Any]:
        self.validate_runner(payload, business_id)
        submitted_fields = (
            payload.mobile_use.model_fields_set
            if payload.mobile_use is not None
            else set()
        )
        clear_keys = {
            self._setting_key(f"runner.mobile_use.{field}", business_id)
            for field in submitted_fields
            if getattr(payload.mobile_use, field) is None
            and field in _CLEARABLE_COMPUTER_USE_FIELDS
        }
        changed_values = {
            self._setting_key(f"runner.mobile_use.{field}", business_id): _serialize_field(
                field,
                getattr(payload.mobile_use, field),
            )
            for field in submitted_fields
            if getattr(payload.mobile_use, field) is not None
        }
        self.repository.delete_many(clear_keys)
        self.repository.set_many(
            {
                self._setting_key("runner.mode", business_id): payload.mode,
                **changed_values,
            }
        )
        changed_fields = sorted(
            payload.mobile_use.model_fields_set
            if payload.mobile_use is not None
            else ()
        )
        add_runner_settings_audit(
            self.repository.db,
            actor_user_id=actor_user_id,
            mode=payload.mode,
            changed_fields=changed_fields,
        )
        return self.get_public_settings(business_id)

    def validate_runner(
        self,
        payload: RunnerSettingsUpdate,
        business_id: str | None = None,
    ) -> RunnerConfig:
        config = self.get_runner_config(business_id)
        merged = config.model_dump(exclude={"mode"})

        if payload.mobile_use is not None:
            for field in payload.mobile_use.model_fields_set:
                value = getattr(payload.mobile_use, field)
                if value is None:
                    if field in _CLEARABLE_COMPUTER_USE_FIELDS:
                        merged[field] = None
                        continue
                    raise RunnerSettingsValidationError(
                        "runner_setting_value_invalid",
                        {"field": field},
                    )
                if isinstance(value, str) and not value.strip():
                    raise RunnerSettingsValidationError(
                        "runner_setting_value_invalid",
                        {"field": field},
                    )
                normalized = value.strip() if isinstance(value, str) else value
                if field == "request_headers":
                    try:
                        normalized = validate_request_headers(normalized)
                    except ValueError as exc:
                        raise RunnerSettingsValidationError(
                            "runner_setting_value_invalid",
                            {"field": field},
                        ) from exc
                merged[field] = normalized

        if (
            business_id is not None
            and payload.mobile_use is not None
            and "product_id" in payload.mobile_use.model_fields_set
            and not self.product_id_available(merged["product_id"], business_id)
        ):
            raise RunnerSettingsValidationError(
                "runner_product_id_conflict",
                {"field": "product_id"},
            )

        if payload.mode == "mobile_use":
            missing_fields = [
                field for field in _REQUIRED_COMPUTER_USE_FIELDS if not merged[field]
            ]
            if missing_fields:
                raise RunnerSettingsValidationError(
                    "runner_settings_incomplete",
                    {"missing_fields": missing_fields},
                )

        return RunnerConfig(mode=payload.mode, **merged)

    def product_id_available(
        self,
        product_id: str,
        business_id: str | None = None,
    ) -> bool:
        normalized = product_id.strip()
        if not normalized:
            return False

        legacy_product_id = self.repository.get("runner.mobile_use.product_id")
        if (
            legacy_product_id == normalized
            and business_id not in {None, DEFAULT_BUSINESS_ID}
        ):
            return False

        for key, value in self.repository.list_decrypted().items():
            owner = _product_id_owner(key)
            if owner is None or owner == business_id:
                continue
            if value.strip() == normalized:
                return False
        return True

    def _setting_key(self, key: str, business_id: str | None) -> str:
        if business_id is None:
            return key
        return f"business.{business_id}.{key}"

    def _get_setting(self, key: str, business_id: str | None) -> str | None:
        if business_id is None:
            return self.repository.get(key)
        value = self.repository.get(self._setting_key(key, business_id))
        if value is not None:
            return value
        if business_id == DEFAULT_BUSINESS_ID:
            return self.repository.get(key)
        return None


def _masked_access_key(value: str | None) -> dict[str, bool | str]:
    if value is None:
        return {"configured": False}
    hint = f"{value[:4]}****{value[-4:]}" if len(value) >= 9 else "configured"
    return {"configured": True, "hint": hint}


def _header_state(value: dict[str, str] | None) -> dict[str, bool | list[str]]:
    if not value:
        return {"configured": False, "names": []}
    return {"configured": True, "names": list(value)}


def _deserialize_field(field: str, value: str | None) -> Any:
    if value is None:
        return None
    if field in {"use_base64_screenshot", "screen_record"}:
        return value.lower() == "true"
    if field in {
        "max_step",
        "timeout_seconds",
        "retry_limit",
        "max_output_tokens",
        "stream_token_ttl_seconds",
    }:
        return int(value)
    if field in {"callback_info", "request_headers"}:
        return json.loads(value)
    return value


def _serialize_field(field: str, value: Any) -> str:
    if value is None:
        raise ValueError("setting_value_must_not_be_none")
    if isinstance(value, str):
        return value.strip()
    if field in {"callback_info", "request_headers"}:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _product_id_owner(key: str) -> str | None:
    if key == "runner.mobile_use.product_id":
        return DEFAULT_BUSINESS_ID
    prefix = "business."
    suffix = ".runner.mobile_use.product_id"
    if key.startswith(prefix) and key.endswith(suffix):
        return key[len(prefix) : -len(suffix)]
    return None
