"""
SentinelAI - explainable Anti-Money-Laundering intelligence platform.

A deterministic detection engine (sanctions/PEP screening, jurisdiction risk,
behavioural typologies, transaction-graph motifs, crypto and trade checks) fused
with an exactly-decomposable noisy-OR score, plus guarded LLM research agents
orchestrated by LangGraph that may raise - never lower - a risk score.
"""

from sentinelai.core.config import settings
from sentinelai.core.logging import setup_logging

__version__ = settings.app_version
__author__ = "Kunal Shaw"
__license__ = "MIT"

setup_logging(settings.monitoring.log_level, settings.monitoring.log_format, settings.monitoring.log_file)

__all__ = ["__version__", "settings"]
