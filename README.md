# 🛡️ SentinelAI - Enterprise AML Detection Platform

<div align="center">

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-v0.2+-green.svg)](https://github.com/langchain-ai/langgraph)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-teal.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)

**Production-grade Anti-Money Laundering detection system powered by LangGraph, Chain-of-Thought reasoning, and ReAct prompting patterns.**

[Features](#-features) •
[Architecture](#-architecture) •
[Quick Start](#-quick-start) •
[API Documentation](#-api-documentation) •
[Deployment](#-deployment)

</div>

---

## 🎯 Overview

**SentinelAI** is an enterprise-grade AML detection platform that transforms traditional rule-based compliance into intelligent, AI-driven risk assessment. Built on LangGraph's powerful workflow orchestration, it employs advanced reasoning techniques including Chain-of-Thought (CoT) and ReAct patterns to provide explainable, auditable compliance decisions.

### Why SentinelAI?

| Traditional AML | SentinelAI |
|----------------|------------|
| Rule-based detection | AI-powered pattern recognition |
| High false positive rates | Intelligent risk scoring |
| Manual SAR generation | Automated SAR drafting |
| Siloed analysis | Unified multi-factor assessment |
| Black-box decisions | Explainable CoT reasoning |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SentinelAI Platform                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────────────────────────────────────────┐    │
│  │   FastAPI   │────▶│              LangGraph Orchestrator             │   │
│  │   Gateway   │     │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │    │
│  └─────────────┘     │  │ CoT     │ │ ReAct   │ │ Multi   │ │ State  │ │    │
│         │            │  │ Prompts │ │ Agents  │ │ Agent   │ │ Graph  │ │    │
│         ▼            │  └─────────┘ └─────────┘ └─────────┘ └────────┘ │    │
│  ┌─────────────┐     └─────────────────────────────────────────────────┘    │
│  │   Redis     │                           │                                │
│  │   Cache     │◀──────────────────────────┘                               │
│  └─────────────┘                           │                                │
│         │            ┌─────────────────────▼────────────────────────┐       │
│         ▼            │              Specialized Agents               │      │
│  ┌─────────────┐     │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │       │
│  │ PostgreSQL  │     │  │Transaction│ │   PEP    │ │  Sanctions   │  │      │
│  │  Database   │◀────│  │ Analysis  │ │Screening │ │  Screening   │  │      │
│  └─────────────┘     │  └──────────┘ └──────────┘ └──────────────┘  │       │
│                      │  ┌──────────┐ ┌──────────┐ ┌──────────────┐  │       │
│  ┌─────────────┐     │  │ Network  │ │Behavioral│ │   Crypto     │  │       │
│  │ Prometheus  │     │  │ Analysis │ │ Analysis │ │ Risk Agent   │  │       │
│  │  + Grafana  │     │  └──────────┘ └──────────┘ └──────────────┘  │       │
│  └─────────────┘     └──────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **API Gateway** | FastAPI | REST API with OpenAPI docs, rate limiting |
| **Orchestrator** | LangGraph | Workflow coordination, state management |
| **Agents** | Groq LLM (Llama3-70B) | Specialized analysis with CoT/ReAct |
| **Database** | PostgreSQL | Transaction, case, and audit storage |
| **Cache** | Redis | LLM response caching, session management |
| **Monitoring** | Prometheus + Grafana | Metrics, alerting, dashboards |

---

## ✨ Features

### 🔍 Intelligent Analysis Agents

- **Transaction Analysis Agent** - Deep pattern analysis with Chain-of-Thought reasoning
- **PEP Screening Agent** - Politically Exposed Persons identification with fuzzy matching
- **Sanctions Agent** - Real-time screening against OFAC, EU, UN lists
- **Network Analysis Agent** - Entity relationship and shell company detection
- **Behavioral Analysis Agent** - Anomaly detection and velocity checks
- **Crypto Risk Agent** - Mixer detection, darknet association, cross-chain analysis
- **Geographic Risk Agent** - Jurisdiction risk scoring and tax haven detection
- **Document Analysis Agent** - Trade document verification and fraud detection

### 🧠 Advanced AI Capabilities

- **Chain-of-Thought (CoT) Prompting** - Step-by-step reasoning for explainable decisions
- **ReAct Pattern** - Reason-Act-Observe loops for complex investigations
- **Multi-Agent Orchestration** - Parallel and conditional agent execution
- **Context-Aware Analysis** - Historical pattern consideration
- **Explainable AI** - Full reasoning trace for audit compliance

### 📊 Enterprise Features

- **RESTful API** - Full CRUD operations with OpenAPI documentation
- **Batch Processing** - Analyze thousands of transactions efficiently
- **Case Management** - End-to-end investigation workflow
- **SAR Generation** - Automated Suspicious Activity Report drafting
- **Audit Trail** - Complete action logging for compliance
- **Real-time Alerts** - Configurable risk-based notifications
- **Docker Deployment** - Production-ready containerization
- **Prometheus Metrics** - Comprehensive observability

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)
- Groq API Key

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/KUNALSHAWW/SentinelAI-AML.git
cd SentinelAI-AML

# Create environment file
cp .env.example .env
# Edit .env with your GROQ_API_KEY

# Start all services
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -c "from sentinelai.models.database import init_db; import asyncio; asyncio.run(init_db())"

# Start the server
sentinelai serve --reload
```

### Option 3: Using Makefile

```bash
# Install dependencies
make install

# Run development server
make dev

# Run tests
make test

# Build Docker images
make docker-build
```

---

## 📡 API Documentation

### Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/analyze` | Analyze a single transaction |
| `POST` | `/api/v1/batch` | Batch analyze multiple transactions |
| `GET` | `/api/v1/analysis/{id}` | Get analysis results |
| `POST` | `/api/v1/cases` | Create investigation case |
| `GET` | `/api/v1/cases/{id}` | Get case details |
| `PATCH` | `/api/v1/cases/{id}` | Update case status |
| `GET` | `/api/v1/alerts` | List alerts with filtering |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

### Example: Analyze Transaction

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transaction": {
      "amount": 500000,
      "currency": "USD",
      "transaction_type": "WIRE_TRANSFER",
      "origin_country": "RU",
      "destination_country": "KY",
      "parties": ["moscow_trading_llc", "cayman_holdings"]
    },
    "customer": {
      "name": "Moscow Trading LLC",
      "customer_type": "CORPORATE",
      "account_age_days": 30
    }
  }'
```

### Example Response

```json
{
  "analysis_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "overall_risk_score": 87.5,
  "risk_level": "CRITICAL",
  "decision": "BLOCK",
  "requires_sar": true,
  "reasoning": {
    "chain_of_thought": [
      "1. Transaction involves high-risk jurisdiction (Russia)",
      "2. Destination is known tax haven (Cayman Islands)",
      "3. New account with no transaction history",
      "4. Large amount ($500,000) exceeds normal thresholds",
      "5. Combined risk factors indicate potential layering"
    ],
    "conclusion": "High probability of money laundering activity"
  },
  "agent_results": {
    "transaction_analysis": { "score": 85, "flags": ["high_value", "new_account"] },
    "geo_risk": { "score": 95, "flags": ["sanctioned_origin", "tax_haven_dest"] },
    "sanctions": { "score": 75, "flags": ["potential_evasion"] }
  },
  "alerts": [
    { "type": "HIGH_RISK_JURISDICTION", "severity": "HIGH" },
    { "type": "TAX_HAVEN_TRANSFER", "severity": "MEDIUM" }
  ]
}
```

### Interactive Documentation

Once the server is running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for LLM access | Required |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `API_HOST` | API server host | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RISK_THRESHOLD_HIGH` | High risk threshold | `70` |
| `RISK_THRESHOLD_CRITICAL` | Critical risk threshold | `85` |
| `ENABLE_CACHE` | Enable LLM response caching | `true` |
| `CACHE_TTL` | Cache time-to-live (seconds) | `3600` |

### Risk Configuration

```python
# sentinelai/core/config.py

HIGH_RISK_COUNTRIES = ["AF", "IR", "KP", "RU", "SY", "YE", ...]
TAX_HAVENS = ["KY", "VG", "PA", "CH", "LU", "MT", ...]
SANCTIONED_ENTITIES = ["sdgt_list", "ofac_sdn", ...]
```

---

## 🐳 Deployment

### Docker Compose Production

```yaml
# docker-compose.yml includes:
# - SentinelAI API (3 replicas)
# - PostgreSQL 15 with persistence
# - Redis 7 with persistence
# - Prometheus monitoring
# - Grafana dashboards
```

```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# Scale API servers
docker-compose up -d --scale api=5

# View logs
docker-compose logs -f api
```

### Health Monitoring

```bash
# Check all services
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8000/metrics

# Grafana dashboard
open http://localhost:3000
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# Run with coverage
pytest --cov=sentinelai --cov-report=html

# Run specific test file
pytest tests/test_agents.py -v

# Run integration tests
pytest tests/test_api.py -v
```

---

## 📁 Project Structure

```
sentinelai/
├── __init__.py              # Package initialization
├── cli.py                   # Command-line interface
├── core/
│   ├── config.py            # Configuration management
│   └── logging.py           # Structured logging
├── models/
│   ├── database.py          # SQLAlchemy ORM models
│   └── schemas.py           # Pydantic schemas
├── agents/
│   ├── prompts.py           # CoT/ReAct prompt templates
│   ├── base.py              # Base agent class
│   ├── specialized.py       # Domain-specific agents
│   └── orchestrator.py      # LangGraph orchestration
├── services/
│   ├── analysis.py          # Analysis service
│   └── case_management.py   # Case management service
├── api/
│   ├── app.py               # FastAPI application
│   └── routes.py            # API endpoints
└── tests/
    ├── conftest.py          # Test fixtures
    ├── test_agents.py       # Agent tests
    └── test_api.py          # API tests
```

---

## 🔒 Security Considerations

- **API Authentication**: Implement OAuth2/JWT for production
- **Data Encryption**: All PII encrypted at rest and in transit
- **Audit Logging**: Complete action trail for compliance
- **Rate Limiting**: Built-in protection against abuse
- **Input Validation**: Strict Pydantic schema validation

---

## 📈 Roadmap

- [ ] Real-time streaming analysis
- [ ] GraphQL API support
- [ ] Kubernetes Helm charts
- [ ] ML model fine-tuning pipeline
- [ ] Multi-tenancy support
- [ ] Regulatory report automation (CTR, STR)
- [ ] Integration with SWIFT/ISO 20022

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Kunal Shaw**
- GitHub: [@KUNALSHAWW](https://github.com/KUNALSHAWW)

---

<div align="center">

**Built with ❤️ for financial compliance**

[Report Bug](https://github.com/KUNALSHAWW/SentinelAI-AML/issues) • [Request Feature](https://github.com/KUNALSHAWW/SentinelAI-AML/issues)

</div>
