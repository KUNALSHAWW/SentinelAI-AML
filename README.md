<p align="center">
  <img src="assets/banner.png" alt="SentinelAI Banner" width="800"/>
</p>

<h1 align="center">🛡️ SentinelAI</h1>
<h3 align="center">AI-Powered Anti-Money Laundering & Fraud Detection Platform</h3>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI"/></a>
  <a href="https://www.langchain.com/"><img src="https://img.shields.io/badge/LangChain-RAG-1C3C3C?style=for-the-badge&logo=chainlink&logoColor=white" alt="LangChain"/></a>
  <a href="https://neo4j.com/"><img src="https://img.shields.io/badge/Neo4j-Graph_DB-008CC1?style=for-the-badge&logo=neo4j&logoColor=white" alt="Neo4j"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License: MIT"/></a>
</p>

<p align="center">
  <a href="#-the-problem">The Problem</a> •
  <a href="#-the-solution">The Solution</a> •
  <a href="#-key-features">Key Features</a> •
  <a href="#-installation">Installation</a> •
  <a href="#-api-documentation">API Docs</a> •
  <a href="#-deployment">Deployment</a>
</p>

---

## 🎯 The Problem

Traditional Anti-Money Laundering (AML) systems are fundamentally broken:

| ❌ Traditional AML | Impact |
|-------------------|--------|
| **Static Rules** | Cannot adapt to new laundering techniques |
| **80%+ False Positives** | Compliance teams drown in alerts |
| **Siloed Analysis** | Misses complex multi-entity schemes |
| **No Context** | Ignores real-world news about entities |
| **Black Box Decisions** | Auditors can't explain why alerts triggered |

Money launderers exploit these weaknesses daily—structuring transactions just under thresholds, using shell companies, and leveraging geographic complexity. **Rule-based systems cannot keep up.**

---

## 💡 The Solution

**SentinelAI** combines three cutting-edge technologies to create an intelligent, adaptive AML system:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                          SentinelAI Architecture                           │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   ┌─────────────┐    ┌─────────────────┐    ┌─────────────────────────┐   │
│   │   Frontend  │───▶│  FastAPI        │───▶│    RAG Pipeline         │   │
│   │  Dashboard  │    │  REST API       │    │  (Web Search + Context) │   │
│   └─────────────┘    └─────────────────┘    └───────────┬─────────────┘   │
│                                                         │                  │
│   ┌─────────────────────────────────────────────────────▼──────────────┐  │
│   │                      LLM Analysis Engine                            │  │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │  │
│   │  │ Zephyr-7B /  │  │  Chain-of-   │  │  Structured Risk         │  │  │
│   │  │ Llama-3 LLM  │  │  Thought     │  │  Assessment (JSON)       │  │  │
│   │  └──────────────┘  └──────────────┘  └──────────────────────────┘  │  │
│   └─────────────────────────────────────────────────────┬──────────────┘  │
│                                                         │                  │
│   ┌─────────────────────────────────────────────────────▼──────────────┐  │
│   │                     Neo4j Graph Database                            │  │
│   │  • Detect hidden entity relationships                               │  │
│   │  • Identify shell company networks                                  │  │
│   │  • Track fund flows across accounts                                 │  │
│   └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### How It Works

1. **RAG (Retrieval-Augmented Generation)**: When analyzing a corporate entity, SentinelAI searches the web for real-time adverse media, sanctions mentions, and business information.

2. **LLM Analysis**: A specialized financial crime LLM (Zephyr-7B or Llama-3) analyzes the transaction with full context, using Chain-of-Thought reasoning to explain every risk factor.

3. **Graph Intelligence**: Neo4j detects hidden patterns that rules miss—circular transactions, shell company networks, and structuring schemes across multiple entities.

---

## ✨ Key Features

### 🚀 Hybrid Analysis Engine
Combines rule-based speed with AI depth. Rule engine handles high-volume screening; LLM investigates flagged cases with full reasoning.

### 🕸️ Graph Intelligence (Neo4j)
- **Ring Detection**: Identifies circular fund flows (A→B→C→A)
- **Shell Company Networks**: Maps beneficial ownership structures
- **Structuring Detection**: Finds smurfing patterns across accounts
- **Entity Resolution**: Links aliases and related parties

### 🧠 Adaptive AI with RAG
- **Real-Time Web Search**: Fetches adverse media, sanctions lists, news
- **Entity Intelligence**: Gathers business registration, key personnel
- **Context Injection**: LLM sees full entity background before analysis
- **Multi-Provider Support**: Tavily, SerpAPI, or DuckDuckGo (free)

### 📊 Enterprise Features
- **RESTful API**: Full OpenAPI documentation at `/docs`
- **Case Management**: End-to-end investigation workflow
- **SAR Generation**: Automated Suspicious Activity Report drafting
- **Audit Trail**: Complete logging for regulatory compliance
- **Docker Ready**: Production-grade containerization

---

## 📸 Screenshots

<p align="center">
  <img src="assets/screenshot-dashboard.png" alt="Dashboard" width="80%"/>
  <br/>
  <em>Transaction Analysis Dashboard</em>
</p>

<p align="center">
  <img src="assets/screenshot-analysis.png" alt="Analysis" width="80%"/>
  <br/>
  <em>AI-Powered Risk Analysis with RAG Context</em>
</p>

---

## 🛠️ Installation

### Prerequisites

- **Python 3.11+**
- **Neo4j** (Desktop or AuraDB Cloud)
- **API Keys**: Groq or HuggingFace (required), Tavily (optional)

### Step 1: Clone & Setup

```bash
# Clone the repository
git clone https://github.com/KUNALSHAWW/SentinelAI-AML.git
cd SentinelAI-AML

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Neo4j (Critical!)

**Option A: Neo4j Desktop (Local Development)**
1. Download [Neo4j Desktop](https://neo4j.com/download/)
2. Create a new project and database
3. Start the database (default: `neo4j://localhost:7687`)
4. Set password (e.g., `neo4j123`)

**Option B: Neo4j AuraDB (Production/Cloud)**
1. Create free account at [Neo4j AuraDB](https://neo4j.com/cloud/aura-free/)
2. Create a new instance
3. Copy connection URI: `neo4j+s://xxxxx.databases.neo4j.io`
4. Save credentials

### Step 3: Environment Configuration

```bash
# Create .env from template
cp .env.example .env
```

Edit `.env` with your values:

```env
# Required: LLM Provider
SENTINEL_LLM_PROVIDER=huggingface
HUGGINGFACE_API_KEY=hf_your_key_here
# OR use Groq (faster)
# SENTINEL_LLM_PROVIDER=groq
# GROQ_API_KEY=gsk_your_key_here

# Required: Neo4j
SENTINEL_DB_NEO4J_URI=neo4j://localhost:7687
SENTINEL_DB_NEO4J_USER=neo4j
SENTINEL_DB_NEO4J_PASSWORD=your_password

# Optional: RAG Web Search (improves corporate entity analysis)
TAVILY_API_KEY=tvly-your_key_here
```

### Step 4: Run the Server

```bash
# Development mode (with auto-reload)
uvicorn sentinelai.api.app:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn sentinelai.api.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Step 5: Access the Application

- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

## 📚 API Documentation

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `POST` | `/api/v1/analyze/rag` | **RAG-powered analysis** (recommended) |
| `POST` | `/api/v1/analyze/rules` | Rule-based analysis (fast fallback) |
| `POST` | `/api/v1/analyze` | Legacy LLM analysis |
| `GET` | `/api/v1/cases` | List investigation cases |
| `POST` | `/api/v1/cases` | Create new case |

### Example: Analyze Transaction

```bash
curl -X POST http://localhost:8000/api/v1/analyze/rag \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key" \
  -d '{
    "transaction": {
      "amount": 500000,
      "currency": "USD",
      "origin_country": "US",
      "destination_country": "KY",
      "transaction_type": "WIRE_TRANSFER"
    },
    "customer": {
      "name": "Oceanic Holdings Ltd",
      "customer_type": "CORPORATE",
      "account_age_days": 45
    },
    "enable_rag": true,
    "enable_llm": true
  }'
```

### Response Structure

```json
{
  "request_id": "uuid",
  "risk_assessment": {
    "risk_score": 75,
    "risk_level": "HIGH",
    "risk_factors": [...],
    "decision_path": ["entry:screening", "rag:entity_search", "llm:analysis"]
  },
  "llm_analysis": {
    "reasoning": "Chain-of-thought analysis...",
    "confidence_score": 0.87,
    "recommendation": "ESCALATE"
  },
  "rag_analysis": {
    "entity_searched": "Oceanic Holdings Ltd",
    "adverse_media_found": true,
    "sanctions_indicators": ["offshore", "shell company"],
    "key_findings": [...]
  },
  "recommended_action": "ESCALATE",
  "sar_required": true
}
```

---

## 🚀 Deployment

### Deploy to Render.com

1. **Push code to GitHub**
2. **Go to Render Dashboard** → New → Blueprint
3. **Connect your repo** and select `render.yaml`
4. **Set environment variables** in Render Dashboard:
   - `GROQ_API_KEY` or `HUGGINGFACE_API_KEY`
   - `SENTINEL_DB_NEO4J_URI` (use AuraDB for production)
   - `SENTINEL_DB_NEO4J_PASSWORD`
   - `TAVILY_API_KEY` (optional)

### Verify Deployment

```bash
# Health check
curl https://your-app.onrender.com/health

# Expected response
{
  "status": "healthy",
  "version": "3.0.0",
  "environment": "production"
}
```

### RAG Pipeline Verification Checklist

- [ ] `/health` returns `status: healthy`
- [ ] Analyze a corporate entity (e.g., "Acme Trading LLC")
- [ ] Response includes `rag_analysis.entity_searched`
- [ ] Response includes `llm_analysis.reasoning`
- [ ] Check logs for `RAG search completed` message

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Vanilla JavaScript, HTML5, CSS3 |
| **API** | FastAPI, Pydantic, Uvicorn |
| **LLM** | HuggingFace (Zephyr-7B), Groq (Llama-3) |
| **RAG** | Tavily, SerpAPI, DuckDuckGo, LangChain |
| **Graph DB** | Neo4j (AuraDB for cloud) |
| **Database** | PostgreSQL, SQLAlchemy |
| **Cache** | Redis |
| **Deployment** | Docker, Render.com |

---

## 📁 Project Structure

```
SentinelAI-AML/
├── frontend/               # Web dashboard
│   ├── index.html
│   ├── app.js             # Main application logic
│   └── styles.css
├── sentinelai/            # Python backend
│   ├── api/
│   │   ├── app.py         # FastAPI application
│   │   └── routes.py      # API endpoints
│   ├── services/
│   │   ├── rag_service.py      # Web search + RAG
│   │   ├── llm_service.py      # HuggingFace/Groq LLM
│   │   ├── rag_analysis.py     # Orchestration layer
│   │   └── analysis.py         # Rule-based engine
│   ├── core/
│   │   ├── config.py      # Settings management
│   │   └── logging.py     # Structured logging
│   └── models/
│       └── schemas.py     # Pydantic models
├── tests/                 # Unit & integration tests
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── render.yaml           # Render.com deployment
├── Dockerfile            # Container definition
└── docker-compose.yml    # Local multi-service setup
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Disclaimer

This software is for educational and research purposes. It is not a substitute for professional AML compliance systems. Always consult with compliance professionals and legal advisors for production AML implementations.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/KUNALSHAWW">Kunal Shaw</a>
</p>
