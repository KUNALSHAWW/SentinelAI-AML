"""
SentinelAI Test Configuration
=============================

Pytest fixtures and configuration.
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from sentinelai.core.config import Settings
from sentinelai.agents.specialized import AMLState


@pytest.fixture
def sample_transaction() -> Dict[str, Any]:
    """Sample transaction for testing"""
    return {
        "amount": 9500,
        "currency": "USD",
        "transaction_type": "WIRE_TRANSFER",
        "origin_country": "US",
        "destination_country": "CA",
        "parties": ["retail_chain_inc"],
        "timestamp": datetime.utcnow(),
        "documents": ["Invoice #SMF-4587"],
    }


@pytest.fixture
def sample_customer() -> Dict[str, Any]:
    """Sample customer for testing"""
    return {
        "name": "James Smith",
        "customer_type": "INDIVIDUAL",
        "account_age_days": 120,
        "country_of_residence": "US",
        "transaction_history": [
            {
                "amount": 9200,
                "timestamp": datetime.utcnow() - timedelta(hours=2),
            },
            {
                "amount": 9350,
                "timestamp": datetime.utcnow() - timedelta(hours=4),
            },
        ],
    }


@pytest.fixture
def high_risk_transaction() -> Dict[str, Any]:
    """High-risk transaction for testing"""
    return {
        "amount": 500000,
        "currency": "USD",
        "transaction_type": "WIRE_TRANSFER",
        "origin_country": "IR",  # Iran - high risk
        "destination_country": "DE",
        "parties": ["tehran_exporters"],
        "timestamp": datetime.utcnow(),
        "documents": ["Trade Agreement #IR-789"],
    }


@pytest.fixture
def pep_customer() -> Dict[str, Any]:
    """PEP customer for testing"""
    return {
        "name": "Minister Adebayo Gov",
        "customer_type": "INDIVIDUAL",
        "account_age_days": 10,
        "country_of_residence": "NG",
        "transaction_history": [],
    }


@pytest.fixture
def crypto_transaction() -> Dict[str, Any]:
    """Crypto transaction for testing"""
    return {
        "amount": 150000,
        "currency": "USD",
        "transaction_type": "CRYPTO",
        "asset_type": "CRYPTO",
        "timestamp": datetime.utcnow(),
        "crypto_details": {
            "wallet_age_days": 3,
            "mixer_used": True,
            "cross_chain_swaps": 4,
        },
    }


@pytest.fixture
def sanctions_transaction() -> Dict[str, Any]:
    """Transaction with sanctioned entity"""
    return {
        "amount": 2000000,
        "currency": "USD",
        "transaction_type": "WIRE_TRANSFER",
        "origin_country": "RU",
        "destination_country": "IN",
        "parties": ["sanctioned_russian_bank", "intermediary_ae"],
        "intermediate_countries": ["AE", "TR"],
        "timestamp": datetime.utcnow(),
        "documents": [],
    }


@pytest.fixture
def initial_state(sample_transaction, sample_customer) -> AMLState:
    """Initial AML state for testing"""
    return AMLState.create_initial(sample_transaction, sample_customer)


@pytest.fixture
def test_settings() -> Settings:
    """Test settings configuration"""
    return Settings(
        environment="development",
        llm={"provider": "groq"},
    )
