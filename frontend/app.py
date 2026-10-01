"""
FounderAI Streamlit UI (v5.1.0 — consome REST + WebSocket).

Fluxo: seleciona modo + prompt → submete via /api/v1/interact → acompanha
status → visualiza/baixa artefatos. Narrowing explícito (sem depender de
st.stop() ser NoReturn) para tipagem estática limpa.
"""

from __future__ import annotations

from typing import Any, Optional

import requests
import streamlit as st

API_BASE: str = st.secrets.get("FOUNDERAI_API_BASE", "http://localhost:8000")
WS_BASE: str = st.secrets.get("FOUNDERAI_WS_BASE", "ws://localhost:8000").rstrip("/")

st.set_page_config(page_title="FounderAI", page_icon="🏛", layout="wide")
st.title("🏛 FounderAI — AI Project Operating System")


def _call_health() -> Optional[dict[str, Any]]:
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _submit_interact(
    mode: str, prompt: str, options: Optional[dict[str, Any]] = None
) -> Optional[dict[str, Any]]:
    try:
        r = requests.post(
            f"{API_BASE}/api/v1/interact",
            json={
                "source": "web",
                "target_mode": mode,
                "prompt": prompt,
                "options": options or {},
            },
            timeout=300,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _fetch_mission(mid: str) -> Optional[dict[str, Any]]:
    try:
        r = requests.get(f"{API_BASE}/api/v1/missions/{mid}", timeout=10)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def _fetch_artifact(mid: str, fname: str) -> Optional[str]:
    try:
        r = requests.get(f"{API_BASE}/api/v1/artifacts/{mid}/{fname}", timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        content = data.get("content")
        return content if isinstance(content, str) else None
    except Exception:
        return None


# ── Sidebar: health + WS ──
with st.sidebar:
    st.markdown("### 🩺 API Status")
    health = _call_health()
    if health is not None:
        st.success(f"{health['status']} · v{health['version']}")
        st.caption(f"Provedores: {', '.join(health['active_providers'])}")
    else:
        st.error("API offline. Rode: uvicorn backend.api.app:app --reload")
    st.markdown("### 📡 WebSocket")
    st.caption(f"`{WS_BASE}/ws/v1/missions/{{id}}/stream`")

# ── Formulário principal ──
mode = st.selectbox(
    "Modo da missão",
    ["discover", "validate", "build", "validate_and_build", "self_audit", "golden"],
    index=0,
)
prompt = st.text_area(
    "Prompt / Ideia / Tema", height=120,
    placeholder="Ex: Quero um sistema de agendamento para barbearias",
)

options: dict[str, Any] = {}
with st.expander("⚙️ Opções avançadas"):
    if mode == "build":
        options["project_type"] = st.selectbox(
            "Tipo", ["WEB_APP", "GAME", "INTERNAL_SYSTEM"])
        options["name"] = st.text_input("Nome do projeto", "BarbeariaApp")
    elif mode == "discover":
        options["max"] = st.slider("Max oportunidades", 3, 12, 6)
    elif mode == "self_audit":
        options["max_per_mode"] = st.slider("Max por modo", 1, 5, 1)
        options["adversarial"] = False
    elif mode == "validate_and_build":
        options["auto_build"] = True
        options["no_build"] = False

run = st.button("🚀 Executar missão", type="primary", use_container_width=True)

if run and prompt.strip():
    response: Optional[dict[str, Any]] = None
    with st.status("Executando missão...", expanded=True) as status:
        st.write("📨 Enviando para a API...")
        response = _submit_interact(mode, prompt, options)
        if response is None:
            status.update(label="❌ Falha ao submeter", state="error")
        else:
            st.write(f"✅ Missão aceita: `{response['mission_id']}`")
            st.write(f"📦 Status: **{response['status']}**")
            status.update(
                label=f"✅ Missão concluída ({response['status']})", state="complete"
            )

    # Narrowing explícito: só acessa campos se response não é None
    if response is not None:
        mid = response["mission_id"]
        st.divider()
        st.subheader("📋 Resumo")
        st.write(response.get("summary", "—"))

        mission_info = _fetch_mission(mid) if mid else None
        if mission_info is not None:
            artifacts = mission_info.get("artifacts", [])
            if artifacts:
                st.subheader("📂 Artefatos disponíveis")
                for art in artifacts:
                    col_view, col_dl = st.columns([3, 1])
                    with col_view:
                        view_key = f"view-{mid}-{art}"
                        if st.button(f"👁 {art}", key=f"btn-{mid}-{art}"):
                            st.session_state[view_key] = not bool(
                                st.session_state.get(view_key, False)
                            )
                        if st.session_state.get(view_key):
                            content = _fetch_artifact(mid, art)
                            if content is not None:
                                st.code(content[:5000])
                    with col_dl:
                        dl = _fetch_artifact(mid, art)
                        if dl is not None:
                            st.download_button(
                                "⬇️", dl, file_name=art, key=f"dl-{mid}-{art}"
                            )
        st.caption(
            f"💡 Streaming em tempo real: `{WS_BASE}/ws/v1/missions/{mid}/stream?mode={mode}`"
        )
elif run:
    st.warning("Preencha o prompt para executar.")