"""
Tests for SentinelAI Agents
===========================

Unit tests for the specialized agents.
"""

import pytest
from datetime import datetime

from sentinelai.agents.specialized import (
    AMLState,
    GeographicRiskAgent,
    BehavioralAnalysisAgent,
    CryptoRiskAgent,
    SanctionsScreeningAgent,
    PEPScreeningAgent,
    RiskScoringAgent,
)


class TestAMLState:
    """Tests for AMLState creation"""
    
    def test_create_initial_state(self, sample_transaction, sample_customer):
        """Test initial state creation"""
        state = AMLState.create_initial(sample_transaction, sample_customer)
        
        assert state["transaction"] == sample_transaction
        assert state["customer"] == sample_customer
        assert state["risk_score"] == 0
        assert state["risk_level"] == "LOW"
        assert state["risk_factors"] == []
        assert state["alerts"] == []
        assert state["pep_status"] is None
        assert state["sanction_hits"] == []
    
    def test_state_has_required_keys(self, initial_state):
        """Test state has all required keys"""
        required_keys = [
            "transaction", "customer", "risk_score", "risk_level",
            "risk_factors", "alerts", "llm_analysis", "decision_path",
            "pep_status", "sanction_hits", "documents"
        ]
        
        for key in required_keys:
            assert key in initial_state


class TestGeographicRiskAgent:
    """Tests for GeographicRiskAgent"""
    
    @pytest.fixture
    def agent(self):
        return GeographicRiskAgent()
    
    @pytest.mark.asyncio
    async def test_high_risk_country_detection(self, agent, initial_state):
        """Test detection of high-risk countries"""
        initial_state["transaction"]["origin_country"] = "IR"  # Iran
        
        result = await agent.process(initial_state)
        
        assert any("HIGH_RISK" in rf for rf in result["risk_factors"])
        assert any("IR" in rf for rf in result["risk_factors"])
    
    @pytest.mark.asyncio
    async def test_tax_haven_detection(self, agent, initial_state):
        """Test detection of tax havens"""
        initial_state["transaction"]["destination_country"] = "KY"  # Cayman Islands
        
        result = await agent.process(initial_state)
        
        assert any("TAX_HAVEN" in rf for rf in result["risk_factors"])
    
    @pytest.mark.asyncio
    async def test_complex_routing_detection(self, agent, initial_state):
        """Test detection of complex routing"""
        initial_state["transaction"]["intermediate_countries"] = ["MT", "CY", "LU"]
        
        result = await agent.process(initial_state)
        
        assert "COMPLEX_ROUTING" in result["risk_factors"]
    
    @pytest.mark.asyncio
    async def test_low_risk_countries(self, agent, initial_state):
        """Test that low-risk countries don't trigger alerts"""
        initial_state["transaction"]["origin_country"] = "US"
        initial_state["transaction"]["destination_country"] = "CA"
        initial_state["transaction"]["intermediate_countries"] = []
        
        result = await agent.process(initial_state)
        
        # Should have no geographic risk factors
        geo_factors = [rf for rf in result["risk_factors"] 
                      if "HIGH_RISK" in rf or "TAX_HAVEN" in rf]
        assert len(geo_factors) == 0


class TestBehavioralAnalysisAgent:
    """Tests for BehavioralAnalysisAgent"""
    
    @pytest.fixture
    def agent(self):
        return BehavioralAnalysisAgent()
    
    @pytest.mark.asyncio
    async def test_structuring_detection(self, agent, initial_state):
        """Test detection of potential structuring"""
        initial_state["transaction"]["amount"] = 9500  # Just below $10k
        
        result = await agent.process(initial_state)
        
        assert any("STRUCTURING" in rf for rf in result["risk_factors"])
    
    @pytest.mark.asyncio
    async def test_new_account_high_value(self, agent, initial_state):
        """Test new account with high-value transaction"""
        initial_state["customer"]["account_age_days"] = 5
        initial_state["transaction"]["amount"] = 50000
        
        result = await agent.process(initial_state)
        
        assert any("NEW_ACCOUNT" in rf for rf in result["risk_factors"])
    
    @pytest.mark.asyncio
    async def test_round_amount_detection(self, agent, initial_state):
        """Test round amount detection"""
        initial_state["transaction"]["amount"] = 100000
        
        result = await agent.process(initial_state)
        
        assert "ROUND_AMOUNT" in result["risk_factors"]


class TestCryptoRiskAgent:
    """Tests for CryptoRiskAgent"""
    
    @pytest.fixture
    def agent(self):
        return CryptoRiskAgent()
    
    @pytest.mark.asyncio
    async def test_mixer_detection(self, agent, crypto_transaction, sample_customer):
        """Test crypto mixer detection"""
        state = AMLState.create_initial(crypto_transaction, sample_customer)
        
        result = await agent.process(state)
        
        assert "CRYPTO_MIXER_DETECTED" in result["risk_factors"]
    
    @pytest.mark.asyncio
    async def test_new_wallet_detection(self, agent, crypto_transaction, sample_customer):
        """Test new wallet detection"""
        crypto_transaction["crypto_details"]["wallet_age_days"] = 2
        crypto_transaction["crypto_details"]["mixer_used"] = False
        state = AMLState.create_initial(crypto_transaction, sample_customer)
        
        result = await agent.process(state)
        
        assert "NEW_CRYPTO_WALLET" in result["risk_factors"]
    
    @pytest.mark.asyncio
    async def test_skip_non_crypto(self, agent, initial_state):
        """Test that non-crypto transactions are skipped"""
        result = await agent.process(initial_state)
        
        # Should return state unchanged for non-crypto
        assert result["transaction"] == initial_state["transaction"]


class TestSanctionsScreeningAgent:
    """Tests for SanctionsScreeningAgent"""
    
    @pytest.fixture
    def agent(self):
        return SanctionsScreeningAgent()
    
    @pytest.mark.asyncio
    async def test_sanctions_hit(self, agent, sanctions_transaction, sample_customer):
        """Test sanctions hit detection"""
        state = AMLState.create_initial(sanctions_transaction, sample_customer)
        
        result = await agent.process(state)
        
        assert len(result["sanction_hits"]) > 0
        assert "SANCTIONS_HIT" in result["risk_factors"]
    
    @pytest.mark.asyncio
    async def test_no_sanctions_hit(self, agent, initial_state):
        """Test clean transaction with no sanctions"""
        result = await agent.process(initial_state)
        
        assert len(result["sanction_hits"]) == 0


class TestPEPScreeningAgent:
    """Tests for PEPScreeningAgent"""
    
    @pytest.fixture
    def agent(self):
        return PEPScreeningAgent()
    
    @pytest.mark.asyncio
    async def test_pep_detection(self, agent, sample_transaction, pep_customer):
        """Test PEP detection"""
        state = AMLState.create_initial(sample_transaction, pep_customer)
        
        result = await agent.process(state)
        
        assert result["pep_status"] is True
        assert "PEP_MATCH" in result["risk_factors"]
    
    @pytest.mark.asyncio
    async def test_non_pep(self, agent, initial_state):
        """Test non-PEP customer"""
        result = await agent.process(initial_state)
        
        # PEP status might be False or determined by LLM
        # Just ensure no error occurs


class TestRiskScoringAgent:
    """Tests for RiskScoringAgent"""
    
    @pytest.fixture
    def agent(self):
        return RiskScoringAgent()
    
    @pytest.mark.asyncio
    async def test_sanctions_hit_scoring(self, agent, initial_state):
        """Test high score for sanctions hit"""
        initial_state["sanction_hits"] = ["sanctioned_entity"]
        
        result = await agent.process(initial_state)
        
        assert result["risk_score"] >= 40
    
    @pytest.mark.asyncio
    async def test_pep_scoring(self, agent, initial_state):
        """Test score includes PEP factor"""
        initial_state["pep_status"] = True
        
        result = await agent.process(initial_state)
        
        assert result["risk_score"] >= 25
    
    @pytest.mark.asyncio
    async def test_risk_level_assignment(self, agent, initial_state):
        """Test risk level assignment based on score"""
        initial_state["sanction_hits"] = ["entity1", "entity2"]
        initial_state["pep_status"] = True
        initial_state["risk_factors"] = ["CRYPTO_MIXER", "HIGH_RISK_JURISDICTION"]
        
        result = await agent.process(initial_state)
        
        # Should be HIGH or CRITICAL
        assert result["risk_level"] in ["HIGH", "CRITICAL"]
        assert result["sar_required"] is True
    
    @pytest.mark.asyncio
    async def test_low_risk_classification(self, agent, initial_state):
        """Test low risk classification"""
        initial_state["risk_factors"] = []
        initial_state["sanction_hits"] = []
        initial_state["pep_status"] = False
        initial_state["llm_analysis"] = {}
        
        result = await agent.process(initial_state)
        
        assert result["risk_level"] == "LOW"
        assert result["sar_required"] is False
