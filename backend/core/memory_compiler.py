"""
Shim de compatibilidade (v5.5.0).

O MemoryContextCompiler canônico vive em backend/core/memory/compiler.py.
Este módulo apenas re-exporta para não quebrar imports legados
(memory_hooks, pipelines, testes).
"""

from backend.core.memory.compiler import MemoryContextCompiler  # noqa: F401

__all__ = ["MemoryContextCompiler"]