from __future__ import annotations

import logging
import os
from typing import Any

from deepagents import create_deep_agent

from .config import Settings
from .tools import list_workspace, read_file, write_file

_agent_instance = None
_logger = logging.getLogger(__name__)


def _build_langfuse_callbacks() -> list[Any]:
    if not Settings.langfuse_enabled:
        return []

    if not (Settings.langfuse_public_key and Settings.langfuse_secret_key):
        _logger.warning("LANGFUSE enabled but missing public/secret keys; skipping traces")
        return []

    os.environ["LANGFUSE_HOST"] = Settings.langfuse_host or "http://langfuse-web:3000"
    os.environ["LANGFUSE_PUBLIC_KEY"] = Settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = Settings.langfuse_secret_key
    os.environ["LANGFUSE_DEBUG"] = "true" if Settings.langfuse_debug else "false"

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler

    except Exception:
        _logger.exception("Langfuse callback import failed; skipping traces")
        return []

    try:
        # Create a named Langfuse client up-front so get_client(public_key=...) can
        # resolve the exact project; otherwise CallbackHandler falls back to fake.
        Langfuse(
            public_key=Settings.langfuse_public_key,
            secret_key=Settings.langfuse_secret_key,
            host=Settings.langfuse_host or "http://langfuse-web:3000",
            debug=Settings.langfuse_debug,
        )
        return [CallbackHandler(public_key=Settings.langfuse_public_key)]
    except Exception:
        _logger.exception("Failed to initialize Langfuse callback handler")
        return []


def _build_model() -> Any:
    if not Settings.model.startswith("openai:"):
        return Settings.model

    from langchain.chat_models import init_chat_model

    try:
        return init_chat_model(
            Settings.model,
            use_responses_api=False,
            extra_body={"instructions": Settings.system_prompt},
        )
    except Exception:
        _logger.exception("Failed to initialize explicit OpenAI chat model; falling back to spec-based initialization")
        return Settings.model


def build_agent():
    if Settings.openai_api_base:
        base = Settings.openai_api_base.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        os.environ["OPENAI_API_BASE"] = base

    return create_deep_agent(
        model=_build_model(),
        tools=[list_workspace, read_file, write_file],
        system_prompt=Settings.system_prompt,
    )


def get_agent():
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = build_agent()
    return _agent_instance


def extract_response(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("output", "result", "final", "content"):
            value = result.get(key)
            if isinstance(value, str):
                return value
        messages = result.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[-1], dict):
            content = messages[-1].get("content")
            if isinstance(content, str):
                return content
    return str(result)
