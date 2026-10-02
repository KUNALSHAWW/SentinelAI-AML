"""LLM access helpers shared by the research layer."""

from __future__ import annotations

import re
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel

from sentinelai.core.config import settings
from sentinelai.core.logging import get_logger

logger = get_logger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_RESPONSE_MARKER = re.compile(r"\n\s*response\s*\n")


def extract_text(content: Any) -> str:
    """Flatten LangChain message content (str or list of content blocks) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in (None, "text"):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def strip_thinking(text: str) -> str:
    """Remove reasoning preambles emitted by reasoning models.

    Handles ``<think>...</think>`` blocks and the Qwen3-on-Groq layout where
    reasoning precedes a standalone ``response`` marker line.
    """
    if not text:
        return text
    text = _THINK_BLOCK.sub("", text)
    match = _RESPONSE_MARKER.search(text)
    if match:
        text = text[match.end():]
    return text.strip()


class LLMFactory:
    """Lazily builds (and caches) the configured chat model."""

    _instance: Optional[BaseChatModel] = None

    @classmethod
    def available(cls) -> bool:
        return settings.llm.api_key_configured

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @classmethod
    def get_llm(cls, force_new: bool = False) -> BaseChatModel:
        if cls._instance is not None and not force_new:
            return cls._instance
        cfg = settings.llm
        if not cfg.api_key_configured:
            raise RuntimeError(f"No API key configured for LLM provider '{cfg.provider}'")
        if cfg.provider == "groq":
            from langchain_groq import ChatGroq

            cls._instance = ChatGroq(
                model=cfg.groq_model, temperature=cfg.temperature, max_tokens=cfg.max_tokens,
                timeout=cfg.timeout, max_retries=cfg.max_retries, api_key=cfg.groq_api_key.get_secret_value(),
            )
            logger.info("Initialised Groq LLM", extra={"model": cfg.groq_model})
        else:
            try:
                from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
            except ImportError as exc:
                raise RuntimeError(
                    "provider=huggingface requires `pip install sentinelai[huggingface]`"
                ) from exc
            endpoint = HuggingFaceEndpoint(
                repo_id=cfg.huggingface_model, temperature=max(cfg.temperature, 0.01), max_new_tokens=cfg.max_tokens,
                huggingfacehub_api_token=cfg.huggingface_api_key.get_secret_value(),
            )
            cls._instance = ChatHuggingFace(llm=endpoint)
            logger.info("Initialised HuggingFace LLM", extra={"model": cfg.huggingface_model})
        return cls._instance
