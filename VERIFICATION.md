# SentinelAI - Deployment Verification Guide

## Phase 3: Post-Deployment Verification

### 1. Health Check Verification

```bash
# Replace YOUR_APP_URL with your actual deployment URL
# For Render: https://sentinelai-api.onrender.com

# Basic health check
curl -X GET https://YOUR_APP_URL/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "3.0.0",
#   "environment": "production",
#   "timestamp": "2024-12-12T10:30:00Z",
#   "dependencies": {
#     "llm_provider": "groq",
#     "database": "connected",
#     "cache": "available"
#   }
# }
```

### 2. RAG Pipeline Verification

```bash
# Test RAG-powered analysis with a corporate entity
curl -X POST https://YOUR_APP_URL/api/v1/analyze/rag \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key" \
  -d '{
    "transaction": {
      "amount": 250000,
      "currency": "USD",
      "origin_country": "US",
      "destination_country": "KY",
      "transaction_type": "WIRE_TRANSFER",
      "timestamp": "2024-12-12T10:00:00Z"
    },
    "customer": {
      "name": "Global Consulting Partners LLC",
      "customer_type": "CORPORATE",
      "account_age_days": 30
    },
    "enable_rag": true,
    "enable_llm": true
  }'
```

### 3. Verification Checklist

Use this checklist to confirm the RAG pipeline is fully operational:

#### ✅ API Health
- [ ] `/health` endpoint returns `status: healthy`
- [ ] Response time < 5 seconds
- [ ] `environment` shows `production`

#### ✅ RAG Web Search
- [ ] Response contains `rag_analysis` object
- [ ] `rag_analysis.entity_searched` matches customer name
- [ ] `rag_analysis.sources_analyzed` > 0
- [ ] No errors in `rag_analysis.summary`

#### ✅ LLM Analysis
- [ ] Response contains `llm_analysis` object
- [ ] `llm_analysis.reasoning` is non-empty
- [ ] `llm_analysis.confidence_score` is between 0-1
- [ ] `llm_analysis.recommendation` is one of: APPROVE, REVIEW, ESCALATE, BLOCK

#### ✅ Risk Assessment
- [ ] `risk_assessment.risk_score` is 0-100
- [ ] `risk_assessment.risk_level` is one of: LOW, MEDIUM, HIGH, CRITICAL
- [ ] `risk_assessment.risk_factors` array is populated
- [ ] `decision_path` shows RAG and LLM steps

#### ✅ Environment Variables (Check in Render Dashboard)
- [ ] `GROQ_API_KEY` or `HUGGINGFACE_API_KEY` is set
- [ ] `SENTINEL_DB_NEO4J_URI` points to AuraDB (not localhost)
- [ ] `SENTINEL_DB_NEO4J_PASSWORD` is set
- [ ] `TAVILY_API_KEY` is set (optional but recommended)

### 4. Troubleshooting

#### RAG Not Returning Results
1. Check if `TAVILY_API_KEY` is set
2. If not, system falls back to DuckDuckGo (may have rate limits)
3. Verify entity name contains corporate indicators (LLC, Inc, Corp, etc.)

#### LLM Analysis Empty
1. Verify `GROQ_API_KEY` or `HUGGINGFACE_API_KEY` is valid
2. Check Render logs for API errors
3. System should fall back to rule-based analysis if LLM fails

#### Neo4j Connection Errors
1. Ensure using AuraDB URI format: `neo4j+s://xxxxx.databases.neo4j.io`
2. Verify password is correct in Render environment
3. Check if AuraDB instance is running (not paused)

### 5. Test Script (Python)

Save this as `verify_deployment.py`:

```python
import requests
import json
import sys

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

def test_health():
    print(f"Testing health endpoint: {BASE_URL}/health")
    resp = requests.get(f"{BASE_URL}/health", timeout=10)
    data = resp.json()
    assert data["status"] == "healthy", f"Health check failed: {data}"
    print("✅ Health check passed")
    return True

def test_rag_analysis():
    print(f"\nTesting RAG analysis: {BASE_URL}/api/v1/analyze/rag")
    payload = {
        "transaction": {
            "amount": 150000,
            "currency": "USD",
            "origin_country": "US",
            "destination_country": "CH",
            "transaction_type": "WIRE_TRANSFER"
        },
        "customer": {
            "name": "Alpine Investment Holdings AG",
            "customer_type": "CORPORATE",
            "account_age_days": 45
        },
        "enable_rag": True,
        "enable_llm": True
    }
    
    resp = requests.post(
        f"{BASE_URL}/api/v1/analyze/rag",
        json=payload,
        headers={"Content-Type": "application/json", "X-API-Key": "demo-key"},
        timeout=120
    )
    
    data = resp.json()
    
    # Verify response structure
    assert "risk_assessment" in data, "Missing risk_assessment"
    assert "llm_analysis" in data, "Missing llm_analysis"
    
    print(f"✅ Risk Score: {data['risk_assessment']['risk_score']}")
    print(f"✅ Risk Level: {data['risk_assessment']['risk_level']}")
    print(f"✅ RAG Enabled: {data.get('_rag_enabled', False)}")
    print(f"✅ Recommendation: {data['recommended_action']}")
    
    if data.get("rag_analysis"):
        print(f"✅ Entity Searched: {data['rag_analysis']['entity_searched']}")
        print(f"✅ Sources Analyzed: {data['rag_analysis']['sources_analyzed']}")
    
    return True

if __name__ == "__main__":
    try:
        test_health()
        test_rag_analysis()
        print("\n🎉 All verification tests passed!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
```

Run with:
```bash
python verify_deployment.py https://your-app.onrender.com
```
