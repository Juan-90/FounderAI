"""
Testes do smoke de release + consistência dos endpoints de infra (v5.5.0).

Carrega scripts/smoke_release.py dinamicamente (importlib) e valida:
  • run_smoke(config) com todos os passos OK (health/version/projeto/feedback/
    timeline-OBSERVED/IMPROVE dry-run);
  • main(config) retorna exit code 0;
  • consistência de /health, /api/v1/version e validação 422 de /interact.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.api.app import create_app  # noqa: E402
from backend.core.config import Settings  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "smoke_release", _REPO / "scripts" / "smoke_release.py")
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["smoke_release"] = mod  # essencial p/ @dataclass resolver anotacoes
_spec.loader.exec_module(mod)


def _cfg(tmp_path: Path) -> Settings:
    return Settings(
        PROJECT_MEMORY_DIR=str(tmp_path / "projects"),
        VALIDATE_ARTIFACTS_DIR=str(tmp_path / "validate"),
        BUILD_ARTIFACTS_DIR=str(tmp_path / "build"),
        VAB_ARTIFACTS_DIR=str(tmp_path / "vab"),
        OBSERVE_FEEDBACK_ENABLED=True,
        OBSERVE_FEEDBACK_MAX_NOTE_CHARS=2000,
    )


# ─────────────────────────────────────────────────────────────
# Smoke de release
# ─────────────────────────────────────────────────────────────

def test_smoke_run_ok(tmp_path: Path) -> None:
    report = mod.run_smoke(config=_cfg(tmp_path))
    failing = [(s.name, s.detail) for s in report.steps if not s.ok]
    assert report.ok, failing
    assert any("OBSERVED" in s.name for s in report.steps)
    assert any("IMPROVE" in s.name for s in report.steps)
    assert len(report.steps) == 6


def test_smoke_main_retorna_zero(tmp_path: Path) -> None:
    assert mod.main(config=_cfg(tmp_path)) == 0


def test_smoke_report_passos_detalhados(tmp_path: Path) -> None:
    report = mod.run_smoke(config=_cfg(tmp_path))
    names = [s.name for s in report.steps]
    assert "GET /health" in names
    assert "GET /api/v1/version" in names
    assert "Cria projeto de teste" in names
    assert "POST feedback humano" in names
    assert "GET timeline (OBSERVED)" in names
    assert "IMPROVE dry-run" in names
    for s in report.steps:
        assert s.detail, f"passo '{s.name}' sem detalhe"


# ─────────────────────────────────────────────────────────────
# Consistência dos endpoints de infraestrutura
# ─────────────────────────────────────────────────────────────

def test_endpoints_infra_consistentes(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    client = TestClient(create_app(config=cfg, engine=mod.NoopEngine(cfg)))

    h = client.get("/health")
    assert h.status_code == 200
    hd = h.json()
    assert {"status", "version", "environment", "active_providers"} <= set(hd)

    v = client.get("/api/v1/version")
    assert v.status_code == 200
    vd = v.json()
    assert vd["name"] == "FounderAI"
    assert vd["version"] == hd["version"]  # mesma versão entre endpoints

    bad = client.post(
        "/api/v1/interact",
        json={"source": "cli", "target_mode": "nao_existe", "prompt": "x"},
    )
    assert bad.status_code == 422  # validação pydantic, nunca 500