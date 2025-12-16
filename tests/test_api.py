"""
Tests for SentinelAI API
========================

Integration tests for the FastAPI endpoints.
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from sentinelai.api.app import create_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health and status endpoints"""
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "SentinelAI"


class TestAnalysisEndpoints:
    """Tests for analysis endpoints"""
    
    def test_analyze_simple_transaction(self, client):
        """Test simple transaction analysis"""
        request_data = {
            "transaction": {
                "amount": 5000,
                "currency": "USD",
                "transaction_type": "WIRE_TRANSFER",
                "origin_country": "US",
                "destination_country": "CA",
                "parties": ["legitimate_company"],
                "timestamp": datetime.utcnow().isoformat(),
            },
            "customer": {
                "name": "John Doe",
                "customer_type": "INDIVIDUAL",
                "account_age_days": 365,
            },
            "enable_llm_analysis": False,  # Disable LLM for faster tests
        }
        
        response = client.post("/api/v1/analyze", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "risk_assessment" in data
        assert "risk_score" in data["risk_assessment"]
        assert "risk_level" in data["risk_assessment"]
    
    def test_analyze_high_risk_transaction(self, client):
        """Test high-risk transaction analysis"""
        request_data = {
            "transaction": {
                "amount": 500000,
                "currency": "USD",
                "transaction_type": "WIRE_TRANSFER",
                "origin_country": "IR",  # High-risk country
                "destination_country": "KY",  # Tax haven
                "parties": ["suspicious_entity"],
                "timestamp": datetime.utcnow().isoformat(),
            },
            "customer": {
                "name": "Minister Gov Official",  # PEP indicator
                "customer_type": "INDIVIDUAL",
                "account_age_days": 10,
            },
            "enable_llm_analysis": False,
        }
        
        response = client.post("/api/v1/analyze", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have elevated risk
        assert data["risk_assessment"]["risk_score"] > 30
    
    def test_analyze_missing_fields(self, client):
        """Test validation for missing required fields"""
        request_data = {
            "transaction": {
                # Missing amount
                "currency": "USD",
            },
            "customer": {
                "name": "Test",
            },
        }
        
        response = client.post("/api/v1/analyze", json=request_data)
        
        # Should return validation error
        assert response.status_code == 422


class TestCaseEndpoints:
    """Tests for case management endpoints"""
    
    def test_create_case(self, client):
        """Test case creation"""
        request_data = {
            "title": "Test Investigation Case",
            "description": "Test case for unit testing",
            "priority": "MEDIUM",
        }
        
        response = client.post("/api/v1/cases", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "case_number" in data
        assert data["title"] == "Test Investigation Case"
        assert data["status"] == "OPEN"
    
    def test_list_cases(self, client):
        """Test listing cases"""
        # Create a case first
        client.post("/api/v1/cases", json={
            "title": "Test Case",
            "priority": "LOW",
        })
        
        response = client.get("/api/v1/cases")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_cases_with_filters(self, client):
        """Test listing cases with filters"""
        response = client.get("/api/v1/cases", params={
            "status": "OPEN",
            "priority": "HIGH",
            "limit": 10,
        })
        
        assert response.status_code == 200


class TestDashboardEndpoints:
    """Tests for dashboard endpoints"""
    
    def test_dashboard_metrics(self, client):
        """Test dashboard metrics endpoint"""
        response = client.get("/api/v1/dashboard/metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert "open_cases" in data
        assert "pending_review" in data


class TestAnalysisMetrics:
    """Tests for analysis metrics"""
    
    def test_analysis_metrics(self, client):
        """Test analysis metrics endpoint"""
        response = client.get("/api/v1/analyze/metrics")
        
        assert response.status_code == 200
        data = response.json()
        # Should return agent metrics
        assert isinstance(data, dict)
