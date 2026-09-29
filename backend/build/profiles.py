"""
Project Profiles — especialização do Modo BUILD por tipo de produto (v4.3).

v4.3: GameProfile headless injeta SDL_VIDEODRIVER/AUDIO=dummy + PYTHONUNBUFFERED=1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.enums import ProjectType


class BaseProjectProfile(ABC):
    project_type: ProjectType

    @property
    @abstractmethod
    def stack(self) -> list[str]: ...

    @property
    @abstractmethod
    def file_structure(self) -> list[str]: ...

    @property
    def execution_env(self) -> dict[str, str]:
        return {}

    def test_command(self) -> list[str]:
        return ["pytest", "-q"]

    @abstractmethod
    def requirements_prompt(self, intent: str) -> str: ...

    @abstractmethod
    def architecture_prompt(self, requirements_md: str) -> str: ...

    @abstractmethod
    def implementation_prompt(self, architecture_md: str) -> str: ...


class WebAppProfile(BaseProjectProfile):
    project_type = ProjectType.WEB_APP

    @property
    def stack(self) -> list[str]:
        return ["FastAPI", "SQLite", "Uvicorn", "Pydantic", "Pytest"]

    @property
    def file_structure(self) -> list[str]:
        return ["main.py", "models.py", "schemas.py", "database.py", "test_main.py"]

    def requirements_prompt(self, intent: str) -> str:
        return (
            f"INTENÇÃO DO FUNDADOR:\n{intent}\n\n"
            "Produza um documento Markdown de requisitos para um WEB APP / SAAS com "
            "EXATAMENTE estas seções:\n"
            "# Objetivo\n# Usuários\n# MVP\n"
            "  - Recursos CRUD / APIs\n  - Persistência\n  - Listagem\n  - Exclusão/Cancelamento\n"
            "# Restrições\n# Não-objetivos\n\n"
            "Seja específico e mínimo (MVP)."
        )

    def architecture_prompt(self, requirements_md: str) -> str:
        return (
            "REQUISITOS:\n"
            f"{requirements_md}\n\n"
            "Produza um documento Markdown de arquitetura para WEB APP com EXATAMENTE:\n"
            f"# Stack\n (use: {', '.join(self.stack)})\n"
            "# Arquivos Necessários\n"
            f"  Liste obrigatoriamente: {', '.join(self.file_structure)}\n"
            "# Responsabilidades por Arquivo\n# Fluxo de Dados\n"
        )

    def implementation_prompt(self, architecture_md: str) -> str:
        return (
            "ARQUITETURA:\n"
            f"{architecture_md}\n\n"
            "Gere código FastAPI + SQLite completo e executável, e testes pytest determinísticos.\n"
            'Formato da resposta: {"files": {...}, "test_files": {...}}\n'
            "Regras: código completo, imports coerentes, testes sem rede."
        )


class GameProfile(BaseProjectProfile):
    project_type = ProjectType.GAME

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless

    @property
    def headless(self) -> bool:
        return self._headless

    @property
    def stack(self) -> list[str]:
        return ["pygame", "Pytest"]

    @property
    def file_structure(self) -> list[str]:
        return ["main.py", "game.py", "entities.py"]

    @property
    def execution_env(self) -> dict[str, str]:
        if not self._headless:
            return {}
        return {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "PYTHONUNBUFFERED": "1",
        }

    def requirements_prompt(self, intent: str) -> str:
        return (
            f"INTENÇÃO DO FUNDADOR:\n{intent}\n\n"
            "Produza um documento Markdown de requisitos para um JOGO 2D com EXATAMENTE:\n"
            "# Game Loop\n  (partidas de 30-60 segundos)\n"
            "# Entidades\n  (player, asteroid, projectile)\n"
            "# Controles\n"
            "# Win/Lose Condition\n"
            "# Restrições\n# Não-objetivos\n\n"
            "Mantenha o escopo mínimo e jogável (MVP)."
        )

    def architecture_prompt(self, requirements_md: str) -> str:
        return (
            "REQUISITOS:\n"
            f"{requirements_md}\n\n"
            "Produza um documento Markdown de arquitetura para JOGO 2D com EXATAMENTE:\n"
            f"# Stack\n (use: {', '.join(self.stack)})\n"
            "# Arquivos Necessários\n"
            f"  Liste obrigatoriamente: {', '.join(self.file_structure)}\n"
            "# Separação Lógica vs Renderização\n"
            "  (lógica determinística testável SEM pygame.init; renderização isolada)\n"
            "# Game Loop\n# Colisões e Pontuação\n"
        )

    def implementation_prompt(self, architecture_md: str) -> str:
        return (
            "ARQUITETURA:\n"
            f"{architecture_md}\n\n"
            "Gere código pygame completo e executável, MAIS testes pytest da LÓGICA "
            "(movimento, colisão, pontuação, game over) que NÃO exigem janela/Display.\n"
            'Formato da resposta: {"files": {...}, "test_files": {...}}\n'
            "Regras: lógica determinística separada da renderização; testes headless-safe."
        )


def profile_for(project_type: ProjectType, headless: bool = True) -> BaseProjectProfile:
    if project_type == ProjectType.GAME:
        return GameProfile(headless=headless)
    return WebAppProfile()