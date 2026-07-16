"""Unit tests for subscription checks (P-014, P-015, P-016, P-020)."""

from __future__ import annotations

from pathlib import Path

import yaml

from validation.context import ApiContext, ValidationContext
from validation.engines.python_checks.subscription_checks import (
    check_cloudevent_via_ref,
    check_event_type_format,
    check_sinkcredential_secrets_writeonly,
    check_subscription_filename,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(
    api_name: str = "device-status-subscriptions",
    api_pattern: str = "explicit-subscription",
) -> ValidationContext:
    api = ApiContext(
        api_name=api_name,
        target_api_version="0.1.0",
        target_api_status="alpha",
        target_api_maturity="initial",
        api_pattern=api_pattern,
        spec_file=f"code/API_definitions/{api_name}.yaml",
    )
    return ValidationContext(
        repository="TestRepo",
        branch_type="main",
        trigger_type="dispatch",
        profile="advisory",
        stage="enabled",
        target_release_type=None,
        commonalities_release=None,
        commonalities_version=None,
        icm_release=None,
        base_ref=None,
        is_release_review_pr=False,
        release_plan_changed=None,
        pr_number=None,
        apis=(api,),
        workflow_run_url="",
        tooling_ref="",
    )


def _write_spec(
    tmp_path: Path,
    api_name: str = "device-status-subscriptions",
    spec_content: dict | None = None,
) -> None:
    if spec_content is None:
        spec_content = {"openapi": "3.0.3", "info": {"title": "Test", "version": "wip"}, "paths": {}}

    spec_dir = tmp_path / "code" / "API_definitions"
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / f"{api_name}.yaml").write_text(
        yaml.dump(spec_content, default_flow_style=False), encoding="utf-8"
    )


def _subscription_spec_with_events(
    api_name: str,
    event_types: list[str],
) -> dict:
    """Build a minimal subscription spec with event type enums."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test", "version": "wip"},
        "paths": {"/subscriptions": {"post": {"responses": {"201": {}}}}},
        "components": {
            "schemas": {
                "SubscriptionEventType": {
                    "type": "string",
                    "enum": event_types,
                }
            }
        },
    }


def _subscription_spec_with_response(
    response_properties: dict,
) -> dict:
    """Build a subscription spec with a response schema."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test", "version": "wip"},
        "paths": {
            "/subscriptions": {
                "post": {
                    "responses": {
                        "201": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/Subscription"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Subscription": {
                    "type": "object",
                    "properties": response_properties,
                }
            }
        },
    }


# ---------------------------------------------------------------------------
# P-014: check-subscription-filename
# ---------------------------------------------------------------------------


class TestCheckSubscriptionFilename:
    def test_explicit_with_suffix_ok(self, tmp_path: Path):
        ctx = _make_context(api_name="device-status-subscriptions")
        assert check_subscription_filename(tmp_path, ctx) == []

    def test_explicit_without_suffix_warn(self, tmp_path: Path):
        ctx = _make_context(api_name="device-status")
        findings = check_subscription_filename(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "warn"
        assert "-subscriptions" in findings[0]["message"]

    def test_implicit_no_suffix_ok(self, tmp_path: Path):
        ctx = _make_context(api_name="device-status", api_pattern="implicit-subscription")
        assert check_subscription_filename(tmp_path, ctx) == []

    def test_request_response_skip(self, tmp_path: Path):
        ctx = _make_context(api_name="device-status", api_pattern="request-response")
        assert check_subscription_filename(tmp_path, ctx) == []


# ---------------------------------------------------------------------------
# P-015: check-event-type-format
# ---------------------------------------------------------------------------


class TestCheckEventTypeFormat:
    def test_valid_event_types(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _subscription_spec_with_events(api_name, [
            f"org.camaraproject.{api_name}.v0.status-changed",
            f"org.camaraproject.{api_name}.v0.subscription-ended",
        ])
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_event_type_format(tmp_path, ctx) == []

    def test_wrong_api_name_error(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _subscription_spec_with_events(api_name, [
            "org.camaraproject.wrong-api.v0.status-changed",
        ])
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_event_type_format(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "error"
        assert "does not match" in findings[0]["message"]

    def test_missing_version_error(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _subscription_spec_with_events(api_name, [
            f"org.camaraproject.{api_name}.status-changed",
        ])
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_event_type_format(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "error"

    def test_invalid_version_format_error(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _subscription_spec_with_events(api_name, [
            f"org.camaraproject.{api_name}.version1.status-changed",
        ])
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_event_type_format(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "error"

    def test_non_subscription_skip(self, tmp_path: Path):
        ctx = _make_context(api_pattern="request-response")
        assert check_event_type_format(tmp_path, ctx) == []

    def test_no_event_types_hint(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        _write_spec(tmp_path, api_name=api_name)
        ctx = _make_context(api_name=api_name)
        findings = check_event_type_format(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "hint"

    def test_mixed_valid_invalid(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _subscription_spec_with_events(api_name, [
            f"org.camaraproject.{api_name}.v0.status-changed",
            "invalid-event-type",
        ])
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_event_type_format(tmp_path, ctx)
        assert len(findings) == 1  # Only the invalid one
        assert "invalid-event-type" in findings[0]["message"]

    def test_implicit_subscription_checked(self, tmp_path: Path):
        api_name = "device-status"
        spec = _subscription_spec_with_events(api_name, [
            f"org.camaraproject.{api_name}.v0.status-changed",
        ])
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name, api_pattern="implicit-subscription")
        assert check_event_type_format(tmp_path, ctx) == []

    def test_missing_spec_file(self, tmp_path: Path):
        ctx = _make_context()
        assert check_event_type_format(tmp_path, ctx) == []


# ---------------------------------------------------------------------------
# P-016: check-sinkcredential-secrets-writeonly
# ---------------------------------------------------------------------------


def _sinkcredential_family_spec(
    access_token_writeonly: bool | None = True,
    access_token_type_writeonly: bool | None = True,
    client_id_writeonly: bool | None = True,
    token_uri_writeonly: bool | None = True,
) -> dict:
    """Build a spec with the full SinkCredential discriminator family.

    A ``None`` value omits the field's ``writeOnly`` key entirely
    (missing); a bool value sets it explicitly (including ``False``,
    present-but-wrong).
    """

    def _field(base: dict, writeonly: bool | None) -> dict:
        if writeonly is not None:
            base = {**base, "writeOnly": writeonly}
        return base

    return {
        "openapi": "3.0.3",
        "info": {"title": "Test", "version": "wip"},
        "paths": {},
        "components": {
            "schemas": {
                "SinkCredential": {
                    "type": "object",
                    "properties": {"credentialType": {"type": "string"}},
                    "discriminator": {"propertyName": "credentialType"},
                },
                "AccessTokenCredential": {
                    "allOf": [
                        {"$ref": "#/components/schemas/SinkCredential"},
                        {
                            "type": "object",
                            "properties": {
                                "accessToken": _field(
                                    {"type": "string"}, access_token_writeonly
                                ),
                                "accessTokenExpiresUtc": {
                                    "type": "string",
                                    "format": "date-time",
                                },
                                "accessTokenType": _field(
                                    {"type": "string"}, access_token_type_writeonly
                                ),
                            },
                        },
                    ]
                },
                "PrivateKeyJWTCredential": {
                    "allOf": [
                        {"$ref": "#/components/schemas/SinkCredential"},
                        {
                            "type": "object",
                            "properties": {
                                "clientId": _field(
                                    {"type": "string"}, client_id_writeonly
                                ),
                                "tokenUri": _field(
                                    {"type": "string"}, token_uri_writeonly
                                ),
                                "jwksUri": {
                                    "type": "string",
                                    "readOnly": True,
                                },
                            },
                        },
                    ]
                },
            }
        },
    }


class TestCheckSinkCredentialSecretsWriteOnly:
    def test_clean_subtype_writeonly_present_ok(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _sinkcredential_family_spec()
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_sinkcredential_secrets_writeonly(tmp_path, ctx) == []

    def test_accesstoken_missing_writeonly_one_finding(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _sinkcredential_family_spec(access_token_writeonly=None)
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_sinkcredential_secrets_writeonly(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "warn"
        assert "AccessTokenCredential.accessToken" in findings[0]["message"]

    def test_accesstoken_writeonly_false_still_flagged(self, tmp_path: Path):
        """writeOnly: false is present-but-wrong, not just missing."""
        api_name = "device-status-subscriptions"
        spec = _sinkcredential_family_spec(access_token_writeonly=False)
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_sinkcredential_secrets_writeonly(tmp_path, ctx)
        assert len(findings) == 1
        assert "accessToken" in findings[0]["message"]

    def test_privatekeyjwt_clientid_tokenuri_coverage(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _sinkcredential_family_spec(
            client_id_writeonly=None, token_uri_writeonly=None
        )
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_sinkcredential_secrets_writeonly(tmp_path, ctx)
        messages = {f["message"] for f in findings}
        assert len(findings) == 2
        assert any("PrivateKeyJWTCredential.clientId" in m for m in messages)
        assert any("PrivateKeyJWTCredential.tokenUri" in m for m in messages)

    def test_response_visible_fields_ignored(self, tmp_path: Path):
        """credentialType/accessTokenExpiresUtc/jwksUri are never checked."""
        api_name = "device-status-subscriptions"
        # All secret fields correctly writeOnly; jwksUri stays readOnly,
        # not writeOnly — must not be flagged.
        spec = _sinkcredential_family_spec()
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_sinkcredential_secrets_writeonly(tmp_path, ctx) == []

    def test_common_ref_spec_no_local_subtype_ok(self, tmp_path: Path):
        """sinkCredential via external $ref, no local subtype schema — no findings."""
        api_name = "device-status-subscriptions"
        spec = _subscription_spec_with_response({
            "id": {"type": "string"},
            "sinkCredential": {
                "$ref": "../common/CAMARA_event_common.yaml#/components/schemas/SinkCredential"
            },
        })
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_sinkcredential_secrets_writeonly(tmp_path, ctx) == []

    def test_implicit_subscription_resource_schema_coverage(self, tmp_path: Path):
        """Implicit subscription has no /subscriptions path — detection
        is schema-definition based, so the subtype is still caught."""
        api_name = "device-status"
        spec = _sinkcredential_family_spec(access_token_writeonly=None)
        spec["paths"] = {"/resources": {"get": {"responses": {"200": {}}}}}
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name, api_pattern="implicit-subscription")
        findings = check_sinkcredential_secrets_writeonly(tmp_path, ctx)
        assert len(findings) == 1

    def test_generic_clientid_field_not_subtype_no_false_positive(self, tmp_path: Path):
        """A clientId field on a schema that is not a SinkCredential
        subtype (no allOf $ref to SinkCredential) must not be flagged."""
        api_name = "device-status-subscriptions"
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "wip"},
            "paths": {},
            "components": {
                "schemas": {
                    "OAuthClient": {
                        "type": "object",
                        "properties": {"clientId": {"type": "string"}},
                    },
                }
            },
        }
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_sinkcredential_secrets_writeonly(tmp_path, ctx) == []

    def test_non_subscription_skip(self, tmp_path: Path):
        ctx = _make_context(api_pattern="request-response")
        assert check_sinkcredential_secrets_writeonly(tmp_path, ctx) == []

    def test_missing_spec_file(self, tmp_path: Path):
        ctx = _make_context()
        assert check_sinkcredential_secrets_writeonly(tmp_path, ctx) == []


# ---------------------------------------------------------------------------
# P-020: check-cloudevent-via-ref
# ---------------------------------------------------------------------------


def _spec_with_cloudevent(cloudevent_schema: dict) -> dict:
    """Build a minimal subscription spec with a CloudEvent schema."""
    return {
        "openapi": "3.0.3",
        "info": {"title": "Test", "version": "wip"},
        "paths": {"/subscriptions": {"post": {"responses": {"201": {}}}}},
        "components": {"schemas": {"CloudEvent": cloudevent_schema}},
    }


class TestCheckCloudEventViaRef:
    def test_inline_cloudevent_warns(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _spec_with_cloudevent({
            "type": "object",
            "required": ["id", "type"],
            "properties": {
                "id": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": [f"org.camaraproject.{api_name}.v0.status-changed"],
                },
            },
        })
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        findings = check_cloudevent_via_ref(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "warn"
        assert findings[0]["engine_rule"] == "check-cloudevent-via-ref"
        assert "inline" in findings[0]["message"]
        assert findings[0]["api_name"] == api_name

    def test_ref_only_cloudevent_ok(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = _spec_with_cloudevent({
            "$ref": "./CAMARA_event_common.yaml#/components/schemas/CloudEvent",
        })
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_cloudevent_via_ref(tmp_path, ctx) == []

    def test_allof_with_ref_ok(self, tmp_path: Path):
        """allOf + $ref migration form has no top-level properties — no finding."""
        api_name = "device-status-subscriptions"
        spec = _spec_with_cloudevent({
            "allOf": [
                {"$ref": "./CAMARA_event_common.yaml#/components/schemas/CloudEvent"},
            ],
        })
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_cloudevent_via_ref(tmp_path, ctx) == []

    def test_no_cloudevent_schema_ok(self, tmp_path: Path):
        api_name = "device-status-subscriptions"
        spec = {
            "openapi": "3.0.3",
            "info": {"title": "Test", "version": "wip"},
            "paths": {"/subscriptions": {"post": {"responses": {"201": {}}}}},
            "components": {"schemas": {"OtherSchema": {"type": "object"}}},
        }
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name)
        assert check_cloudevent_via_ref(tmp_path, ctx) == []

    def test_implicit_subscription_inline_warns(self, tmp_path: Path):
        api_name = "device-status"
        spec = _spec_with_cloudevent({
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["foo"]},
            },
        })
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name, api_pattern="implicit-subscription")
        findings = check_cloudevent_via_ref(tmp_path, ctx)
        assert len(findings) == 1
        assert findings[0]["level"] == "warn"

    def test_request_response_skip(self, tmp_path: Path):
        """Request-response APIs do not define CloudEvent — skip even if inline."""
        api_name = "device-status"
        spec = _spec_with_cloudevent({
            "type": "object",
            "properties": {"type": {"type": "string"}},
        })
        _write_spec(tmp_path, api_name=api_name, spec_content=spec)
        ctx = _make_context(api_name=api_name, api_pattern="request-response")
        assert check_cloudevent_via_ref(tmp_path, ctx) == []

    def test_missing_spec_file(self, tmp_path: Path):
        ctx = _make_context()
        assert check_cloudevent_via_ref(tmp_path, ctx) == []
