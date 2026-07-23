"""Tests for Phase 2a Spectral gap rules (S-018..S-035).

Tests create minimal OpenAPI YAML fixtures, run Spectral with the r4 ruleset,
and verify that expected rules fire (or don't fire) on them.  Each test targets
a specific rule by checking for its rule code in the Spectral JSON output.

Requires: Node.js + Spectral CLI (installed via validation/package.json).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths & helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RULESET = _REPO_ROOT / "linting" / "config" / ".spectral-r4.yaml"
_NODE_MODULES = _REPO_ROOT / "validation" / "node_modules"


def _run_spectral(yaml_content: str) -> list[dict]:
    """Write *yaml_content* to a temp file, lint it with Spectral, return findings."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        tmp_path = f.name

    env = {
        "PATH": subprocess.os.environ.get("PATH", ""),
        "NODE_PATH": str(_NODE_MODULES),
        "HOME": subprocess.os.environ.get("HOME", ""),
    }
    result = subprocess.run(
        [
            "node",
            str(_NODE_MODULES / ".bin" / "spectral"),
            "lint",
            tmp_path,
            "-r", str(_RULESET),
            "--format", "json",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    Path(tmp_path).unlink(missing_ok=True)
    if result.stdout.strip():
        return json.loads(result.stdout)
    return []


def _codes(findings: list[dict]) -> set[str]:
    """Extract the set of rule codes from Spectral findings."""
    return {f["code"] for f in findings}


def _findings_for(findings: list[dict], code: str) -> list[dict]:
    """Filter findings to a specific rule code."""
    return [f for f in findings if f["code"] == code]


# ---------------------------------------------------------------------------
# Minimal valid spec (passes all rules)
# ---------------------------------------------------------------------------

_VALID_SPEC = """\
openapi: 3.0.3
info:
  title: Test API
  description: A test API
  version: wip
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html
  x-camara-commonalities: 0.7.0
externalDocs:
  description: Product documentation at CAMARA
  url: https://github.com/camaraproject/TestAPI
servers:
  - url: "{apiRoot}/test-api/vwip"
    variables:
      apiRoot:
        default: http://localhost:9091
        description: "API root, defined by the service provider, e.g. `api.example.com` or `api.example.com/somepath`"
tags:
  - name: Test API
security:
  - openId:
    - test-api:read
paths:
  /test:
    get:
      tags:
        - Test API
      summary: Get test
      description: Get test description
      operationId: getTest
      responses:
        "200":
          description: OK
        "401":
          description: Unauthorized
          content:
            application/json:
              schema:
                allOf:
                  - $ref: "#/components/schemas/ErrorInfo"
                  - type: object
                    properties:
                      code:
                        enum:
                          - UNAUTHENTICATED
        "403":
          description: Forbidden
          content:
            application/json:
              schema:
                allOf:
                  - $ref: "#/components/schemas/ErrorInfo"
                  - type: object
                    properties:
                      code:
                        enum:
                          - PERMISSION_DENIED
components:
  securitySchemes:
    openId:
      type: openIdConnect
      openIdConnectUrl: https://example.com/.well-known/openid-configuration
  schemas:
    ErrorInfo:
      type: object
      required:
        - status
        - code
        - message
      properties:
        status:
          type: integer
          format: int32
          minimum: 100
          maximum: 599
          description: HTTP response status code
        code:
          type: string
          maxLength: 96
          description: A human-readable code to describe the error
        message:
          type: string
          maxLength: 512
          description: A human-readable description of what the event represents
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def valid_findings():
    """Findings from the minimal valid spec — baseline for 'no false positives'."""
    return _run_spectral(_VALID_SPEC)


class TestGroupA:
    """Group A: Simple field checks."""

    def test_valid_spec_no_license_findings(self, valid_findings):
        codes = _codes(valid_findings)
        assert "camara-license-name" not in codes
        assert "camara-license-url-value" not in codes

    def test_license_name_wrong(self):
        spec = _VALID_SPEC.replace("name: Apache 2.0", "name: MIT")
        findings = _run_spectral(spec)
        assert "camara-license-name" in _codes(findings)

    def test_license_url_wrong(self):
        spec = _VALID_SPEC.replace(
            "url: https://www.apache.org/licenses/LICENSE-2.0.html",
            "url: https://opensource.org/licenses/MIT",
        )
        findings = _run_spectral(spec)
        assert "camara-license-url-value" in _codes(findings)

    def test_no_contact_passes(self, valid_findings):
        assert "camara-no-contact" not in _codes(valid_findings)

    def test_contact_present_fails(self):
        spec = _VALID_SPEC.replace(
            "  x-camara-commonalities: 0.7.0",
            "  contact:\n    name: Foo\n  x-camara-commonalities: 0.7.0",
        )
        findings = _run_spectral(spec)
        assert "camara-no-contact" in _codes(findings)

    def test_tag_title_case_passes(self, valid_findings):
        assert "camara-tag-name-title-case" not in _codes(valid_findings)

    def test_tag_title_case_fails(self):
        spec = _VALID_SPEC.replace("name: Test API", "name: test api")
        findings = _run_spectral(spec)
        assert "camara-tag-name-title-case" in _codes(findings)

    def test_api_root_default_passes(self, valid_findings):
        assert "camara-api-root-default" not in _codes(valid_findings)

    def test_api_root_default_fails(self):
        spec = _VALID_SPEC.replace(
            "default: http://localhost:9091",
            "default: http://localhost:8080",
        )
        findings = _run_spectral(spec)
        assert "camara-api-root-default" in _codes(findings)

    def test_api_root_description_passes(self, valid_findings):
        assert "camara-api-root-description" not in _codes(valid_findings)

    def test_response_403_passes(self, valid_findings):
        assert "camara-response-403" not in _codes(valid_findings)

    def test_response_403_missing(self):
        # Remove the 403 response block
        spec = _VALID_SPEC.replace(
            '        "403":\n'
            "          description: Forbidden\n"
            "          content:\n"
            "            application/json:\n"
            "              schema:\n"
            "                allOf:\n"
            '                  - $ref: "#/components/schemas/ErrorInfo"\n'
            "                  - type: object\n"
            "                    properties:\n"
            "                      code:\n"
            "                        enum:\n"
            "                          - PERMISSION_DENIED",
            "",
        )
        findings = _run_spectral(spec)
        assert "camara-response-403" in _codes(findings)

    def test_parameter_name_lowerCamelCase_passes(self):
        spec = _VALID_SPEC.replace(
            "      summary: Get test",
            "      parameters:\n"
            "        - name: sessionId\n"
            "          in: query\n"
            "          required: false\n"
            "          schema:\n"
            "            type: string\n"
            "      summary: Get test",
        )
        findings = _run_spectral(spec)
        assert "camara-parameter-name-casing-convention" not in _codes(findings)

    def test_parameter_name_non_lowerCamelCase_fails(self):
        spec = _VALID_SPEC.replace(
            "      summary: Get test",
            "      parameters:\n"
            "        - name: Session_id\n"
            "          in: query\n"
            "          required: false\n"
            "          schema:\n"
            "            type: string\n"
            "      summary: Get test",
        )
        findings = _run_spectral(spec)
        assert "camara-parameter-name-casing-convention" in _codes(findings)

    def test_parameter_name_header_excluded(self):
        # Header parameter names are excluded — HTTP headers are
        # case-insensitive per RFC; CAMARA documents x-correlator etc.
        spec = _VALID_SPEC.replace(
            "      summary: Get test",
            "      parameters:\n"
            "        - name: X-Correlator\n"
            "          in: header\n"
            "          required: false\n"
            "          schema:\n"
            "            type: string\n"
            "      summary: Get test",
        )
        findings = _run_spectral(spec)
        assert "camara-parameter-name-casing-convention" not in _codes(findings)

    @pytest.mark.parametrize("suffix", ["gte", "gt", "lte", "lt"])
    def test_parameter_name_filter_suffix_passes(self, suffix):
        # Design Guide §4.3.2 filtering-operation suffixes must not be flagged.
        spec = _VALID_SPEC.replace(
            "      summary: Get test",
            "      parameters:\n"
            f"        - name: creationDate.{suffix}\n"
            "          in: query\n"
            "          required: false\n"
            "          schema:\n"
            "            type: string\n"
            "      summary: Get test",
        )
        findings = _run_spectral(spec)
        assert "camara-parameter-name-casing-convention" not in _codes(findings)

    def test_parameter_name_unrecognized_suffix_fails(self):
        # Only the four documented filter suffixes are exempted.
        spec = _VALID_SPEC.replace(
            "      summary: Get test",
            "      parameters:\n"
            "        - name: creationDate.foo\n"
            "          in: query\n"
            "          required: false\n"
            "          schema:\n"
            "            type: string\n"
            "      summary: Get test",
        )
        findings = _run_spectral(spec)
        assert "camara-parameter-name-casing-convention" in _codes(findings)

    def test_parameter_name_bad_base_with_valid_suffix_fails(self):
        # A valid filter suffix does not excuse a badly-cased base name.
        spec = _VALID_SPEC.replace(
            "      summary: Get test",
            "      parameters:\n"
            "        - name: CreationDate.gte\n"
            "          in: query\n"
            "          required: false\n"
            "          schema:\n"
            "            type: string\n"
            "      summary: Get test",
        )
        findings = _run_spectral(spec)
        assert "camara-parameter-name-casing-convention" in _codes(findings)


class TestGroupB:
    """Group B: Error code checks."""

    def test_valid_error_codes_pass(self, valid_findings):
        codes = _codes(valid_findings)
        assert "camara-error-code-not-numeric" not in codes
        assert "camara-error-code-screaming-snake-case" not in codes
        assert "camara-error-code-api-specific-format" not in codes

    def test_numeric_error_code_fails(self):
        # Must quote the value so YAML parses it as a string, not integer
        spec = _VALID_SPEC.replace("- UNAUTHENTICATED", '- "401"')
        findings = _run_spectral(spec)
        assert "camara-error-code-not-numeric" in _codes(findings)

    def test_non_screaming_snake_case_fails(self):
        spec = _VALID_SPEC.replace("- UNAUTHENTICATED", "- unauthenticated")
        findings = _run_spectral(spec)
        assert "camara-error-code-screaming-snake-case" in _codes(findings)

    def test_api_specific_code_valid(self):
        spec = _VALID_SPEC.replace(
            "- PERMISSION_DENIED", "- TEST_API.PERMISSION_DENIED"
        )
        findings = _run_spectral(spec)
        assert "camara-error-code-api-specific-format" not in _codes(findings)

    def test_api_specific_code_bad_format(self):
        spec = _VALID_SPEC.replace(
            "- PERMISSION_DENIED", "- test.permission_denied"
        )
        findings = _run_spectral(spec)
        assert "camara-error-code-api-specific-format" in _codes(findings)


class TestGroupC:
    """Group C: Subscription schema checks."""

    _SUBSCRIPTION_SPEC = """\
    openapi: 3.0.3
    info:
      title: Test Subscriptions
      description: Test
      version: wip
      license:
        name: Apache 2.0
        url: https://www.apache.org/licenses/LICENSE-2.0.html
      x-camara-commonalities: 0.7.0
    externalDocs:
      description: Product documentation at CAMARA
      url: https://github.com/camaraproject/TestAPI
    servers:
      - url: "{apiRoot}/test-subscriptions/vwip"
        variables:
          apiRoot:
            default: http://localhost:9091
            description: "API root, defined by the service provider, e.g. `api.example.com` or `api.example.com/somepath`"
    tags:
      - name: Test Subscription
    security:
      - openId:
        - test:read
    paths:
      /subscriptions:
        post:
          tags:
            - Test Subscription
          summary: Create subscription
          description: Create a subscription
          operationId: createSubscription
          requestBody:
            required: true
            content:
              application/json:
                schema:
                  $ref: "#/components/schemas/SubscriptionRequest"
          callbacks:
            notifications:
              "{$request.body#/sink}":
                post:
                  summary: Notification callback
                  description: Notification callback
                  operationId: postNotification
                  requestBody:
                    required: true
                    content:
                      application/cloudevents+json:
                        schema:
                          $ref: "#/components/schemas/CloudEvent"
                  responses:
                    "204":
                      description: No Content
                  security:
                    - {}
          responses:
            "201":
              description: Created
            "401":
              description: Unauthorized
            "403":
              description: Forbidden
    components:
      securitySchemes:
        openId:
          type: openIdConnect
          openIdConnectUrl: https://example.com/.well-known/openid-configuration
      schemas:
        Protocol:
          type: string
          enum:
            - HTTP
          description: Delivery protocol
        SubscriptionRequest:
          type: object
          required:
            - sink
            - protocol
          properties:
            protocol:
              $ref: "#/components/schemas/Protocol"
            sink:
              type: string
              format: uri
              maxLength: 2048
              pattern: "^https:\\\\/\\\\/.+$"
              description: The address to which events shall be delivered
        CloudEvent:
          type: object
          required:
            - id
            - source
            - specversion
            - type
            - time
          properties:
            id:
              type: string
              description: Event identifier
              minLength: 1
            source:
              type: string
              format: uri-reference
              minLength: 1
              description: Event source
            type:
              type: string
              description: Event type
              minLength: 1
            specversion:
              type: string
              description: CloudEvents version
              enum:
                - "1.0"
            datacontenttype:
              type: string
              description: Content type
              enum:
                - application/json
            time:
              type: string
              format: date-time
              description: "Timestamp. It must follow [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339#section-5.6) and must have time zone."
            data:
              type: object
              description: Event payload
    """

    def test_specversion_valid(self):
        findings = _run_spectral(self._SUBSCRIPTION_SPEC)
        assert "camara-cloudevent-specversion" not in _codes(findings)

    def test_specversion_wrong(self):
        spec = self._SUBSCRIPTION_SPEC.replace(
            'enum:\n                - "1.0"',
            'enum:\n                - "2.0"',
        )
        findings = _run_spectral(spec)
        assert "camara-cloudevent-specversion" in _codes(findings)

    def test_protocol_http_only_passes(self):
        findings = _run_spectral(self._SUBSCRIPTION_SPEC)
        assert "camara-subscription-protocol-http" not in _codes(findings)

    def test_protocol_non_http_fails(self):
        spec = self._SUBSCRIPTION_SPEC.replace(
            "enum:\n            - HTTP\n          description: Delivery protocol",
            "enum:\n            - HTTP\n            - MQTT3\n          description: Delivery protocol",
        )
        findings = _run_spectral(spec)
        assert "camara-subscription-protocol-http" in _codes(findings)

    def test_sink_https_passes(self):
        findings = _run_spectral(self._SUBSCRIPTION_SPEC)
        assert "camara-subscription-sink-https" not in _codes(findings)

    def test_notification_content_type_passes(self):
        findings = _run_spectral(self._SUBSCRIPTION_SPEC)
        assert "camara-notification-content-type" not in _codes(findings)

    def test_notification_content_type_wrong(self):
        spec = self._SUBSCRIPTION_SPEC.replace(
            "application/cloudevents+json:", "application/json:"
        )
        findings = _run_spectral(spec)
        assert "camara-notification-content-type" in _codes(findings)


class TestGroupD:
    """Group D: Custom JS function rules."""

    def test_datetime_rfc3339_passes(self):
        # 4-space indent puts schema under components.schemas (sibling of ErrorInfo)
        spec = _VALID_SPEC + (
            "    TimestampSchema:\n"
            "      type: object\n"
            "      properties:\n"
            "        createdAt:\n"
            "          type: string\n"
            "          format: date-time\n"
            '          description: "Created timestamp. It must follow [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339#section-5.6) and must have time zone."\n'
        )
        findings = _run_spectral(spec)
        assert "camara-datetime-rfc3339-description" not in _codes(findings)

    def test_datetime_rfc3339_fails(self):
        spec = _VALID_SPEC + (
            "    TimestampSchema:\n"
            "      type: object\n"
            "      properties:\n"
            "        createdAt:\n"
            "          type: string\n"
            "          format: date-time\n"
            '          description: "A timestamp"\n'
        )
        findings = _run_spectral(spec)
        assert "camara-datetime-rfc3339-description" in _codes(findings)

    def test_duration_rfc3339_fails(self):
        spec = _VALID_SPEC + (
            "    DurationSchema:\n"
            "      type: object\n"
            "      properties:\n"
            "        maxDuration:\n"
            "          type: string\n"
            "          format: duration\n"
            '          description: "How long it takes"\n'
        )
        findings = _run_spectral(spec)
        assert "camara-duration-rfc3339-description" in _codes(findings)

    def test_required_properties_pass(self, valid_findings):
        assert "camara-required-properties-exist" not in _codes(valid_findings)

    def test_required_properties_fail(self):
        spec = _VALID_SPEC + (
            "    BadSchema:\n"
            "      type: object\n"
            "      required:\n"
            "        - name\n"
            "        - age\n"
            "        - missing_field\n"
            "      properties:\n"
            "        name:\n"
            "          type: string\n"
            "          description: Name\n"
            "        age:\n"
            "          type: integer\n"
            "          format: int32\n"
            "          minimum: 0\n"
            "          maximum: 200\n"
            "          description: Age\n"
        )
        findings = _run_spectral(spec)
        assert "camara-required-properties-exist" in _codes(findings)

    def test_required_properties_allof_no_false_positive(self):
        """allOf fragments with required but no properties should not fire."""
        spec = _VALID_SPEC + (
            "    ExtendedError:\n"
            "      allOf:\n"
            '        - $ref: "#/components/schemas/ErrorInfo"\n'
            "        - type: object\n"
            "          required:\n"
            "            - detail\n"
            "          properties:\n"
            "            detail:\n"
            "              type: string\n"
            "              description: Additional detail\n"
        )
        findings = _run_spectral(spec)
        allof_findings = [
            f for f in _findings_for(findings, "camara-required-properties-exist")
            if "ExtendedError" in str(f.get("path", []))
        ]
        assert len(allof_findings) == 0

    def test_array_items_description_passes(self):
        spec = _VALID_SPEC + (
            "    ListSchema:\n"
            "      type: object\n"
            "      properties:\n"
            "        items_list:\n"
            "          type: array\n"
            "          description: A list\n"
            "          items:\n"
            "            type: string\n"
            "            description: An item\n"
        )
        findings = _run_spectral(spec)
        items_findings = [
            f for f in _findings_for(findings, "camara-array-items-description")
            if "ListSchema" in str(f.get("path", []))
        ]
        assert len(items_findings) == 0

    def test_array_items_description_fails(self):
        spec = _VALID_SPEC + (
            "    ListSchema:\n"
            "      type: object\n"
            "      properties:\n"
            "        items_list:\n"
            "          type: array\n"
            "          description: A list\n"
            "          items:\n"
            "            type: string\n"
        )
        findings = _run_spectral(spec)
        assert "camara-array-items-description" in _codes(findings)

    def test_array_items_ref_skipped(self):
        """$ref items should be skipped (target schema has own description)."""
        spec = _VALID_SPEC + (
            "    ListSchema:\n"
            "      type: object\n"
            "      properties:\n"
            "        errors:\n"
            "          type: array\n"
            "          description: List of errors\n"
            "          items:\n"
            '            $ref: "#/components/schemas/ErrorInfo"\n'
        )
        findings = _run_spectral(spec)
        items_findings = [
            f for f in _findings_for(findings, "camara-array-items-description")
            if "ListSchema" in str(f.get("path", []))
        ]
        assert len(items_findings) == 0


# ---------------------------------------------------------------------------
# S-037: camara-no-numeric-resource-ids
# ---------------------------------------------------------------------------
# Replaces stock owasp:api1:2023-no-numeric-ids. Walks allOf / anyOf / oneOf
# branches and only fires when the chain terminates at type: integer.

_RULE = "camara-no-numeric-resource-ids"


def _spec_with_id_param(schema_block: str, *, name: str = "widgetId") -> str:
    """Build a minimal spec where /widgets/{name} parameter has the given schema.

    Injects the new path before the `components:` section so it parses under
    `paths`, not `components`. Extra schemas can be appended to the result.
    """
    new_path = (
        f"  /widgets/{{{name}}}:\n"
        "    parameters:\n"
        f"      - name: {name}\n"
        "        in: path\n"
        "        required: true\n"
        "        description: widget id\n"
        f"{schema_block}"
        "    get:\n"
        "      tags:\n"
        "        - Test API\n"
        "      summary: Get widget\n"
        "      description: Get widget description\n"
        "      operationId: getWidget\n"
        "      responses:\n"
        '        "200":\n'
        "          description: OK\n"
    )
    return _VALID_SPEC.replace("components:\n", new_path + "components:\n", 1)


class TestS037NoNumericResourceIds:
    """S-037: replaces owasp:api1:2023-no-numeric-ids."""

    def test_owasp_passthrough_muted(self, valid_findings):
        """The stock OWASP rule must not surface — replaced by camara-no-numeric-resource-ids."""
        assert "owasp:api1:2023-no-numeric-ids" not in _codes(valid_findings)

    def test_inline_string_passes(self):
        schema = (
            "        schema:\n"
            "          type: string\n"
            "          format: uuid\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema))
        assert _RULE not in _codes(findings)

    def test_inline_integer_fires(self):
        schema = (
            "        schema:\n"
            "          type: integer\n"
            "          format: int64\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema))
        assert _RULE in _codes(findings)

    def test_ref_to_string_passes(self):
        """Bare $ref alias resolving to type: string — the common pattern."""
        schema = (
            "        schema:\n"
            '          $ref: "#/components/schemas/UUID"\n'
        )
        components = (
            "    UUID:\n"
            "      type: string\n"
            "      format: uuid\n"
            "      pattern: '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema) + components)
        assert _RULE not in _codes(findings)

    def test_allof_wrapped_string_passes(self):
        """The bug case: allOf wrapper around a $ref to type: string must pass.

        Reproduced from camaraproject/NetworkAccessManagement#137: the stock
        OWASP rule fires here because its JSON Schema check vacuously matches
        a schema with no top-level `type`. The replacement walks combiners
        and recognises the chain terminates at `type: string`.
        """
        schema = (
            "        schema:\n"
            '          $ref: "#/components/schemas/ServiceId"\n'
        )
        components = (
            "    UUID:\n"
            "      type: string\n"
            "      format: uuid\n"
            "    ServiceId:\n"
            "      allOf:\n"
            '        - $ref: "#/components/schemas/UUID"\n'
            "      description: |\n"
            "        A unique identifier for a service. Must be a valid UUID.\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema) + components)
        assert _RULE not in _codes(findings)

    def test_allof_wrapped_integer_fires(self):
        """allOf wrapping type: integer must still fire — chain terminates at integer."""
        schema = (
            "        schema:\n"
            '          $ref: "#/components/schemas/NumericId"\n'
        )
        components = (
            "    NumericId:\n"
            "      allOf:\n"
            "        - type: integer\n"
            "          format: int64\n"
            "      description: numeric id\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema) + components)
        assert _RULE in _codes(findings)

    def test_non_id_parameter_ignored(self):
        """Parameters whose name does not match the id pattern are ignored."""
        schema = (
            "        schema:\n"
            "          type: integer\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema, name="category"))
        assert _RULE not in _codes(findings)


# ---------------------------------------------------------------------------
# S-038: camara-integer-safe-range
# ---------------------------------------------------------------------------

_SAFE_RANGE_RULE = "camara-integer-safe-range"


class TestS038IntegerSafeRange:
    """S-038: integer schema values must stay within the 53-bit integer range."""

    def test_unsafe_int64_maximum_fires(self):
        spec = _VALID_SPEC + (
            "    LargeCounter:\n"
            "      type: integer\n"
            "      format: int64\n"
            "      minimum: 0\n"
            "      maximum: 9223372036854775807\n"
            "      description: Large traffic counter\n"
        )
        findings = _run_spectral(spec)
        s038 = _findings_for(findings, _SAFE_RANGE_RULE)
        assert s038, f"Expected {_SAFE_RANGE_RULE}; got {_codes(findings)}"
        assert any(f.get("path", [])[-1:] == ["maximum"] for f in s038)

    def test_safe_integer_boundaries_pass(self):
        spec = _VALID_SPEC + (
            "    SafeCounter:\n"
            "      type: integer\n"
            "      format: int64\n"
            "      minimum: -9007199254740991\n"
            "      maximum: 9007199254740991\n"
            "      description: Safe traffic counter\n"
        )
        findings = _run_spectral(spec)
        assert _SAFE_RANGE_RULE not in _codes(findings)

    def test_numeric_enum_and_default_outside_safe_range_fire(self):
        spec = _VALID_SPEC + (
            "    CounterState:\n"
            "      type: integer\n"
            "      format: int64\n"
            "      default: 9007199254740993\n"
            "      enum:\n"
            "        - 1\n"
            "        - 9007199254740992\n"
            "      description: Counter state\n"
        )
        findings = _run_spectral(spec)
        s038 = _findings_for(findings, _SAFE_RANGE_RULE)
        assert len(s038) >= 2, f"Expected default and enum findings; got {s038}"
        paths = {tuple(f.get("path", [])) for f in s038}
        assert any(path[-1:] == ("default",) for path in paths)
        assert any("enum" in path for path in paths)

    def test_missing_format_integer_with_unsafe_minimum_fires(self):
        spec = _VALID_SPEC + (
            "    UnformattedInteger:\n"
            "      type: integer\n"
            "      minimum: -9223372036854775808\n"
            "      description: Unformatted integer value\n"
        )
        findings = _run_spectral(spec)
        s038 = _findings_for(findings, _SAFE_RANGE_RULE)
        assert s038, f"Expected {_SAFE_RANGE_RULE}; got {_codes(findings)}"
        assert any(f.get("path", [])[-1:] == ["minimum"] for f in s038)

    def test_inline_parameter_schema_with_unsafe_maximum_fires(self):
        schema = (
            "        schema:\n"
            "          type: integer\n"
            "          format: int64\n"
            "          maximum: 9223372036854775807\n"
        )
        findings = _run_spectral(_spec_with_id_param(schema, name="category"))
        s038 = _findings_for(findings, _SAFE_RANGE_RULE)
        assert s038, f"Expected {_SAFE_RANGE_RULE}; got {_codes(findings)}"
        assert any("parameters" in f.get("path", []) for f in s038)

    def test_large_double_value_passes(self):
        spec = _VALID_SPEC + (
            "    LargeDouble:\n"
            "      type: number\n"
            "      format: double\n"
            "      maximum: 1000000000000000000000000000000\n"
            "      example: 1000000000000000000000000000000\n"
            "      description: Large floating-point value\n"
        )
        findings = _run_spectral(spec)
        assert _SAFE_RANGE_RULE not in _codes(findings)


# ---------------------------------------------------------------------------
# Regression: camara-security-no-secrets must not crash Spectral on null values
#
# The rule's `given` includes a recursive-descent filter
# `$..parameters[?(@.in != 'header')]`.  Without a null-guard, nimma evaluates
# the `@.in` predicate against `null` nodes anywhere in the document and throws
# "Cannot read properties of null (reading 'in')", aborting the whole file
# (Spectral exit 2).  See camaraproject/tooling#322.
# ---------------------------------------------------------------------------

_NO_SECRETS_RULE = "camara-security-no-secrets-in-path-or-query-parameters"


def _run_spectral_raw(yaml_content: str) -> subprocess.CompletedProcess:
    """Run Spectral and return the raw CompletedProcess (to inspect exit code)."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        tmp_path = f.name
    env = {
        "PATH": subprocess.os.environ.get("PATH", ""),
        "NODE_PATH": str(_NODE_MODULES),
        "HOME": subprocess.os.environ.get("HOME", ""),
    }
    try:
        return subprocess.run(
            [
                "node",
                str(_NODE_MODULES / ".bin" / "spectral"),
                "lint", tmp_path, "-r", str(_RULESET), "--format", "json",
            ],
            capture_output=True, text=True, env=env, timeout=30,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# Spec with a non-header query parameter named `phoneNumber` (which the rule
# must flag) AND a literal `null` example value (which previously crashed the
# recursive given).  The param exercises the exact `given` under test.
_NULL_VALUE_SPEC = _VALID_SPEC.replace(
    "      operationId: getTest\n",
    "      operationId: getTest\n"
    "      parameters:\n"
    "        - name: phoneNumber\n"
    "          in: query\n"
    "          schema:\n"
    "            type: string\n"
    "            example: null\n",
)


class TestNoSecretsNullValueRegression:
    """camaraproject/tooling#322 — recursive given must tolerate null nodes."""

    def test_spectral_does_not_crash_on_null_value(self):
        """A spec containing a literal null must not abort Spectral (exit 2)."""
        result = _run_spectral_raw(_NULL_VALUE_SPEC)
        assert result.returncode != 2, (
            "Spectral crashed (exit 2) on a spec containing a null value:\n"
            f"{result.stderr.strip()}"
        )
        assert "Cannot read properties of null" not in result.stderr

    def test_no_secrets_rule_fires_on_phone_number_query_param(self):
        """Positive case: the rule still flags a non-header param named phoneNumber."""
        findings = _run_spectral(_NULL_VALUE_SPEC)
        assert _NO_SECRETS_RULE in _codes(findings)
