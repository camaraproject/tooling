"""Tests for Node tool resolution (CAMARA_NODE_MODULES -> PATH -> repo default)."""

from __future__ import annotations

from pathlib import Path

import pytest

from validation.engines import node_tools

_REPO_DEFAULT = Path(node_tools.__file__).resolve().parent.parent / "node_modules"


def _make_install(root: Path) -> Path:
    """Create a fake ``node_modules`` with a ``.bin/spectral`` entry."""
    node_modules = root / "node_modules"
    (node_modules / ".bin").mkdir(parents=True)
    (node_modules / ".bin" / "spectral").write_text("", encoding="utf-8")
    return node_modules


class TestNodeModulesDir:
    def test_env_variable_wins(self, tmp_path, monkeypatch):
        install = _make_install(tmp_path / "env")
        other = _make_install(tmp_path / "path")
        monkeypatch.setenv("CAMARA_NODE_MODULES", str(install))
        monkeypatch.setenv("PATH", str(other / ".bin"))

        assert node_tools.node_modules_dir() == install

    def test_path_lookup_when_env_unset(self, tmp_path, monkeypatch):
        install = _make_install(tmp_path)
        (install / ".bin" / "spectral").chmod(0o755)
        monkeypatch.delenv("CAMARA_NODE_MODULES", raising=False)
        monkeypatch.setenv("PATH", str(install / ".bin"))

        assert node_tools.node_modules_dir() == install

    def test_path_hit_outside_bin_dir_is_ignored(self, tmp_path, monkeypatch):
        stray = tmp_path / "usr" / "local" / "sbin"
        stray.mkdir(parents=True)
        (stray / "spectral").write_text("", encoding="utf-8")
        (stray / "spectral").chmod(0o755)
        monkeypatch.delenv("CAMARA_NODE_MODULES", raising=False)
        monkeypatch.setenv("PATH", str(stray))

        assert node_tools.node_modules_dir() == _REPO_DEFAULT

    def test_repo_default_when_nothing_else_resolves(self, monkeypatch):
        monkeypatch.delenv("CAMARA_NODE_MODULES", raising=False)
        monkeypatch.setenv("PATH", "")

        assert node_tools.node_modules_dir() == _REPO_DEFAULT

    def test_blank_env_variable_is_ignored(self, monkeypatch):
        monkeypatch.setenv("CAMARA_NODE_MODULES", "  ")
        monkeypatch.setenv("PATH", "")

        assert node_tools.node_modules_dir() == _REPO_DEFAULT


class TestSpectralHelpers:
    def test_spectral_bin_is_under_resolved_install(self, tmp_path, monkeypatch):
        install = _make_install(tmp_path)
        monkeypatch.setenv("CAMARA_NODE_MODULES", str(install))

        assert node_tools.spectral_bin() == install / ".bin" / "spectral"

    def test_spectral_env_exposes_node_path(self, tmp_path, monkeypatch):
        install = _make_install(tmp_path)
        monkeypatch.setenv("CAMARA_NODE_MODULES", str(install))

        env = node_tools.spectral_env()

        assert env["NODE_PATH"] == str(install)
        assert set(env) == {"PATH", "NODE_PATH", "HOME"}

    def test_bin_dir_is_under_resolved_install(self, tmp_path, monkeypatch):
        install = _make_install(tmp_path)
        monkeypatch.setenv("CAMARA_NODE_MODULES", str(install))

        assert node_tools.bin_dir() == install / ".bin"
