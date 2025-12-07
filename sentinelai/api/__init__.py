"""
SentinelAI API Module
=====================

FastAPI-based REST API for the SentinelAI platform.
"""

from sentinelai.api.app import create_app
from sentinelai.api.routes import router

__all__ = ["create_app", "router"]
