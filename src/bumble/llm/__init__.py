"""LLM-Layer — provider-agnostisch (§15). Der Rest der Codebase kennt nur ``LLMClient``."""

from .client import (
    LLMAuthError,
    LLMBackendCrash,
    LLMClient,
    LLMError,
    LLMRequestError,
    build_client,
    verify_openrouter_key,
)

__all__ = ["LLMClient", "LLMError", "LLMAuthError", "LLMRequestError", "LLMBackendCrash",
           "build_client", "verify_openrouter_key"]
