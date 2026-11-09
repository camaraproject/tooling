"""Tests for the security scheme rules S-041..S-043.

Each test lints a minimal OpenAPI document with the r4 Spectral ruleset and
checks whether the rule code fires.  The shapes mirror the real cases:

- NetworkInsights: security requirements name ``openId`` but no scheme is defined.
- IoTSIMFraudPrevention: ``openId`` is ``type: oauth2`` with a clientCredentials flow.

Requires: Node.js + Spectral CLI (installed via validation/package.json).
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from validation.engines import node_tools

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RULESET = _REPO_ROOT / "linting" / "config" / ".spectral-r4.yaml"

S041 = "camara-security-requirement-defined"
S042 = "camara-security-openid-scheme"
S043 = "camara-security-openid-url"
_ALL = {S041, S042, S043}


def _run_spectral(yaml_content: str) -> list[dict]:
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write(yaml_content)
        tmp_path = f.name
    result = subprocess.run(
        [
            "node",
            str(node_tools.spectral_bin()),
            "lint",
            tmp_path,
            "-r", str(_RULESET),
            "--format", "json",
        ],
        capture_output=True,
        text=True,
        env=node_tools.spectral_env(),
        timeout=30,
    )
    Path(tmp_path).unlink(missing_ok=True)
    return json.loads(result.stdout) if result.stdout.strip() else []


def _hits(findings: list[dict], code: str) -> list[dict]:
    return [f for f in findings if f["code"] == code]


def _fired(findings: list[dict]) -> set[str]:
    return {f["code"] for f in findings} & _ALL


_HEADER = """\
openapi: 3.0.3
info:
  title: Test API
  description: A test API
  version: wip
  license:
    name: Apache 2.0
    url: https://www.apache.org/licenses/LICENSE-2.0.html
servers:
  - url: "{apiRoot}/test-api/vwip"
    variables:
      apiRoot:
        default: http://localhost:9091
tags:
  - name: Test API
"""

_ROOT_SECURITY = """\
security:
  - openId:
    - test-api:read
"""

_PATHS = """\
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
"""

_OPENID_SCHEME = """\
components:
  securitySchemes:
    openId:
      type: openIdConnect
      openIdConnectUrl: https://example.com/.well-known/openid-configuration
"""


def _spec(security: str = _ROOT_SECURITY, paths: str = _PATHS, components: str = _OPENID_SCHEME) -> str:
    return _HEADER + security + paths + components


@pytest.fixture(scope="module")
def valid_findings():
    return _run_spectral(_spec())


class TestValidShapes:
    """The rules stay silent on conforming shapes."""

    def test_inline_openid_connect(self, valid_findings):
        assert _fired(valid_findings) == set()

    def test_ref_form(self):
        components = """\
components:
  securitySchemes:
    openId:
      $ref: "../common/CAMARA_common.yaml#/components/securitySchemes/openId"
"""
        assert _fired(_run_spectral(_spec(components=components))) == set()

    def test_operation_level_security(self):
        paths = _PATHS.replace(
            "      operationId: getTest\n",
            "      operationId: getTest\n      security:\n        - openId:\n          - test-api:read\n",
        )
        assert _fired(_run_spectral(_spec(security="", paths=paths))) == set()

    def test_unsecured_spec_is_not_this_rules_business(self):
        """No security anywhere and no schemes: S-303/S-308 own that case."""
        assert _fired(_run_spectral(_spec(security="", components="components: {}\n"))) == set()

    def test_empty_requirement_alone(self):
        security = "security:\n  - {}\n"
        assert _fired(_run_spectral(_spec(security=security, components="components: {}\n"))) == set()

    def test_callback_with_empty_alternative_and_notifications_bearer(self):
        paths = _PATHS.replace(
            "      responses:\n",
            """\
      callbacks:
        onEvent:
          "{$request.body#/sink}":
            post:
              summary: notify
              operationId: onEvent
              security:
                - {}
                - notificationsBearerAuth: []
              responses:
                "204":
                  description: OK
      responses:
""",
        )
        components = _OPENID_SCHEME + """\
    notificationsBearerAuth:
      type: http
      scheme: bearer
      bearerFormat: "{$request.body#/sinkCredential.credentialType}"
"""
        assert _fired(_run_spectral(_spec(paths=paths, components=components))) == set()

    def test_receiver_side_endpoint_does_not_demand_openid(self):
        """Commonalities sample-notification.yaml: root security names only notificationsBearerAuth."""
        security = "security:\n  - notificationsBearerAuth: []\n  - {}\n"
        components = """\
components:
  securitySchemes:
    notificationsBearerAuth:
      type: http
      scheme: bearer
      bearerFormat: "{$request.body#/sinkCredential.credentialType}"
"""
        assert _fired(_run_spectral(_spec(security=security, components=components))) == set()

    def test_callback_only_security_does_not_demand_openid(self):
        """S-042 looks at non-callback operations; a callback requirement alone is S-041 territory."""
        paths = _PATHS.replace(
            "      responses:\n",
            """\
      callbacks:
        onEvent:
          "{$request.body#/sink}":
            post:
              summary: notify
              operationId: onEvent
              security:
                - notificationsBearerAuth: []
              responses:
                "204":
                  description: OK
      responses:
""",
        )
        components = """\
components:
  securitySchemes:
    notificationsBearerAuth:
      type: http
      scheme: bearer
"""
        assert S042 not in _fired(_run_spectral(_spec(security="", paths=paths, components=components)))


class TestS041RequirementDefined:
    def test_networkinsights_shape(self):
        findings = _run_spectral(_spec(components="components: {}\n"))
        hits = _hits(findings, S041)
        assert len(hits) == 1
        assert hits[0]["severity"] == 0  # error
        assert "'openId'" in hits[0]["message"]
        assert "(root)" in hits[0]["message"]
        assert "not defined in components.securitySchemes" in hits[0]["message"]

    def test_operation_names_undefined_scheme(self):
        paths = _PATHS.replace(
            "      operationId: getTest\n",
            "      operationId: getTest\n      security:\n        - openIdX:\n          - test-api:read\n",
        )
        hits = _hits(_run_spectral(_spec(paths=paths)), S041)
        assert len(hits) == 1
        assert "'openIdX' (GET /test)" in hits[0]["message"]

    def test_callback_names_undefined_scheme(self):
        paths = _PATHS.replace(
            "      responses:\n",
            """\
      callbacks:
        onEvent:
          "{$request.body#/sink}":
            post:
              summary: notify
              operationId: onEvent
              security:
                - {}
                - notificationsBearerAuth: []
              responses:
                "204":
                  description: OK
      responses:
""",
        )
        hits = _hits(_run_spectral(_spec(paths=paths)), S041)
        assert len(hits) == 1
        assert "'notificationsBearerAuth'" in hits[0]["message"]
        assert "callback" in hits[0]["message"]

    def test_defined_names_do_not_fire(self, valid_findings):
        assert not _hits(valid_findings, S041)


class TestS042OpenIdScheme:
    def test_no_openid_entry_while_secured(self):
        findings = _run_spectral(_spec(components="components: {}\n"))
        hits = _hits(findings, S042)
        assert len(hits) == 1
        assert hits[0]["severity"] == 0
        assert "openId" in hits[0]["message"]

    def test_iotsimfraudprevention_shape(self):
        components = """\
components:
  securitySchemes:
    openId:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: http://10.0.0.1/token
          scopes:
            test-api:read: read
"""
        hits = _hits(_run_spectral(_spec(components=components)), S042)
        assert len(hits) == 1
        assert "type oauth2" in hits[0]["message"]
        assert "openIdConnect" in hits[0]["message"]
        assert not _hits(_run_spectral(_spec(components=components)), S041)

    def test_oauth2_under_other_name(self):
        components = _OPENID_SCHEME + """\
    OAuth2:
      type: oauth2
      flows:
        clientCredentials:
          tokenUrl: https://example.com/token
          scopes: {}
"""
        hits = _hits(_run_spectral(_spec(components=components)), S042)
        assert len(hits) == 1
        assert "securitySchemes.OAuth2" in hits[0]["message"]

    def test_other_bearer_scheme_still_demands_openid(self):
        """Only notificationsBearerAuth is exempt; a provider API on another bearer scheme fires."""
        security = "security:\n  - bearerAuth: []\n"
        components = """\
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
"""
        hits = _hits(_run_spectral(_spec(security=security, components=components)), S042)
        assert len(hits) == 1
        assert "does not define the 'openId' scheme" in hits[0]["message"]

    def test_openid_with_wrong_type(self):
        components = """\
components:
  securitySchemes:
    openId:
      type: http
      scheme: bearer
"""
        hits = _hits(_run_spectral(_spec(components=components)), S042)
        assert len(hits) == 1
        assert "type http" in hits[0]["message"]


class TestS043OpenIdUrl:
    def test_http_url(self):
        components = _OPENID_SCHEME.replace("https://", "http://")
        findings = _run_spectral(_spec(components=components))
        hits = _hits(findings, S043)
        assert len(hits) == 1
        assert hits[0]["severity"] == 1  # warn
        assert "http://example.com/.well-known/openid-configuration" in hits[0]["message"]
        assert not _hits(findings, S041) and not _hits(findings, S042)

    def test_missing_well_known_suffix(self):
        components = _OPENID_SCHEME.replace("/.well-known/openid-configuration", "/openid")
        assert len(_hits(_run_spectral(_spec(components=components)), S043)) == 1

    def test_valid_url(self, valid_findings):
        assert not _hits(valid_findings, S043)
