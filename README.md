# 🚀 AI Multi-Agent Trading System (24/7 Investment Intelligence Engine)

## 🧠 Overview

This project implements a **multi-agent AI system** for stock market analysis and decision-making.

It combines:
- Technical analysis
- News intelligence
- Sentiment analysis
- Risk evaluation

To generate:

👉 **BUY / SELL / HOLD decisions with confidence and explanation**

---

## 🎯 Key Features

- 💬 Chat-based interface (OpenClaw-style)
- 🔁 24/7 background monitoring
- 🧠 Multi-agent architecture
- 📊 Real-time stock data (yfinance)
- 📰 News analysis (NewsAPI)
- 🤖 LLM-powered reasoning
- ⚠️ Risk-aware decision making
- 🔐 User authentication & authorization (JWT)
- 💰 Tiered access (Free: 3 prompts, Paid: $10/month)
- 🛡️ Admin panel for user management
- 📱 Mobile-responsive UI (Android & iOS)
- ☁️ Deployable to Vercel (API) + Streamlit Cloud (UI)

---

## 🏗️ Architecture

User (Chat UI)
↓
FastAPI Gateway
↓
Orchestrator Agent
├── Market Analyst Agent
├── News Analyst Agent
├── Sentiment Agent
├── Risk Manager Agent
└── Decision Agent
↓
Memory (Postgres + Vector DB)
↓
Scheduler (24/7 loop)


---

## 🤖 Agents Description

### 1. 🟢 Orchestrator Agent
- Parses user input
- Coordinates all agents
- Aggregates results

---

### 2. 📊 Market Analyst Agent
- Fetches stock data
- Computes:
  - Moving averages (MA20, MA50)
  - RSI
  - Trend detection

---

### 3. 📰 News Analyst Agent
- Fetches latest news using API
- Filters relevant headlines

---

### 4. 💬 Sentiment Agent
- Uses LLM to analyze:
  - News sentiment
  - Market tone
- Outputs:
  - positive / negative / neutral
  - impact level

---

### 5. ⚠️ Risk Manager Agent
- Evaluates:
  - volatility
  - overbought/oversold (RSI)
- Adds constraints:
  - prevents risky trades

---

### 6. 🎯 Decision Agent
- Combines all signals
- Produces:
  - BUY / SELL / HOLD
  - Confidence score
- Uses hybrid:
  - rule-based + LLM explanation

---

## 📁 Project Structure

```
multiagent-trading-system/
│
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI entrypoint + lifespan
│   └── routes/
│       ├── __init__.py
│       └── analysis.py      # /analyze, /history, /health endpoints
│
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py      # Coordinates all agents
│   ├── market_agent.py      # Technical analysis (MA, RSI, trend)
│   ├── news_agent.py        # News fetching + filtering
│   ├── sentiment_agent.py   # LLM-powered sentiment analysis
│   ├── risk_agent.py        # Risk scoring + constraints
│   └── decision_agent.py    # Final BUY/SELL/HOLD decision
│
├── tools/
│   ├── __init__.py
│   ├── stock_api.py         # yfinance data fetcher
│   └── news_api.py          # NewsAPI client
│
├── core/
│   ├── __init__.py
│   ├── config.py            # Environment-based settings
│   ├── llm.py               # OpenAI chat/json wrappers
│   └── logging_config.py    # Structured logging setup
│
├── scheduler/
│   ├── __init__.py
│   └── worker.py            # 24/7 background analysis loop
│
├── memory/
│   ├── __init__.py
│   ├── db.py                # SQLAlchemy async models + queries
│   └── vector_store.py      # In-memory vector store (embeddings)
│
├── ui/
│   ├── __init__.py
│   └── streamlit_app.py     # Chat-based Streamlit frontend
│
├── tests/
│   ├── __init__.py
│   ├── test_market_agent.py
│   ├── test_risk_agent.py
│   └── test_orchestrator.py
│
├── .env.example             # Template for environment variables
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🔧 Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| PostgreSQL | 16+ | Persistent storage |
| Redis | 7+ | Caching (optional) |
| Docker + Docker Compose | Latest | Containerized deployment |

---

## 🔑 Required API Keys

You only need **2 API keys** to run the entire system:

| Key | Where to Get | Free Tier |
|-----|-------------|-----------|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | Pay-as-you-go |
| `NEWS_API_KEY` | https://newsapi.org/register | ✅ 100 requests/day |

---

## 🚀 Development Setup (Step-by-Step)

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd multiagent-trading-system
```

### Step 2: Create Environment File

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
OPENAI_API_KEY=sk-your-actual-key-here
NEWS_API_KEY=your-actual-newsapi-key-here
```

### Step 3: Set Up Python Virtual Environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### Step 4: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Start PostgreSQL & Redis

**Option A — Docker (recommended):**

```bash
docker compose up postgres redis -d
```

**Option B — Local install:**

Make sure PostgreSQL is running on `localhost:5432` with:
- User: `trading_user`
- Password: `trading_pass`
- Database: `trading_db`

### Step 6: Start the FastAPI Backend

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

### Step 7: Start the Streamlit UI (in a separate terminal)

```bash
streamlit run ui/streamlit_app.py --server.port 8501
```

Open http://localhost:8501 in your browser.

---

## 🐳 Docker Deployment (Full Stack)

Build and run everything with a single command:

```bash
# 1. Make sure .env is configured
cp .env.example .env
# Edit .env with your API keys

# 2. Build and start all services
docker compose up --build -d streamlit

# 3. View logs
docker compose logs -f api

# 4. Stop everything
docker compose down
```

Services will be available at:
| Service | URL |
|---------|-----|
| FastAPI (backend) | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Streamlit (UI) | http://localhost:8501 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_risk_agent.py -v
```

---

## 📡 API Usage Examples

### Analyze a Stock

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"message": "Analyze AAPL"}'
```

### Analyze Multiple Stocks

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"message": "What do you think about AAPL MSFT TSLA?"}'
```

### Get Analysis History

```bash
curl http://localhost:8000/api/v1/history?symbol=AAPL&limit=10
```

### Semantic Memory Search

```bash
curl -X POST "http://localhost:8000/api/v1/search-memory?query=AAPL%20bullish"
```

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

---

## 🔄 Agent Pipeline Flow

```
User Input: "Analyze AAPL"
       │
       ▼
┌─────────────────────┐
│  Orchestrator Agent  │  ← Parses symbols, coordinates pipeline
└──────┬──────────────┘
       │
       ├──────────────────────────┐ (parallel)
       ▼                          ▼
┌──────────────┐       ┌──────────────┐
│ Market Agent │       │  News Agent  │
│ (yfinance)   │       │ (NewsAPI)    │
└──────┬───────┘       └──────┬───────┘
       │                      │
       │               ┌──────▼───────┐
       │               │  Sentiment   │
       │               │  Agent (LLM) │
       │               └──────┬───────┘
       │                      │
       ├──────────────────────┘
       ▼
┌──────────────┐
│ Risk Manager │  ← Evaluates risk from market + sentiment
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Decision    │  ← Hybrid rule-based + LLM reasoning
│  Agent       │
└──────┬───────┘
       │
       ▼
  BUY / SELL / HOLD
  + Confidence Score
  + Explanation
```

---

## ⚙️ Configuration Reference

All settings are managed via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *required* | OpenAI API key |
| `NEWS_API_KEY` | *required* | NewsAPI key |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `LLM_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `LLM_TEMPERATURE` | `0.2` | LLM creativity (0-1) |
| `LLM_MAX_TOKENS` | `2048` | Max response tokens |
| `SCHEDULER_INTERVAL` | `30` | Minutes between auto-analysis cycles |
| `WATCHLIST` | `AAPL,MSFT,GOOGL,AMZN,TSLA` | Stocks for 24/7 monitoring |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `APP_ENV` | `development` | Environment mode |
| `SECRET_KEY` | `change-this-to-a-random-secret-key` | JWT signing key (change in production!) |

---

## 🔐 Authentication & Authorization

The system includes a full auth layer with tiered access control.

### User Tiers

| Tier | Prompt Limit | Cost Model |
|------|-------------|------------|
| **Free** | 3 prompts total | No charge |
| **Paid** | Unlimited | $10.00 balance, deducted per prompt based on token usage |

### Default Admin Account

On first startup, a seed admin is created:

- **Email**: `fhossain@bigpond.net.au`
- **Password**: `admin123`
- **Role**: admin / paid tier / $10 balance

> ⚠️ Change the admin password immediately after first login.

### Auth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register new user (requires admin approval) |
| `/api/v1/auth/login` | POST | Login, returns JWT token |
| `/api/v1/auth/me` | GET | Get current user profile |
| `/api/v1/auth/change-password` | PUT | Change own password |

### Admin Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/admin/users` | GET | List all users |
| `/api/v1/admin/users/{id}` | PUT | Update user (tier, approval, balance) |
| `/api/v1/admin/users/{id}` | DELETE | Delete user |
| `/api/v1/admin/stats` | GET | System statistics |
| `/api/v1/admin/change-password` | PUT | Admin password change |

---

## 📱 Mobile Support

The Streamlit UI is fully responsive for Android and iOS devices:

- **Viewport meta tag** prevents unwanted zoom on mobile
- **768px breakpoint**: Optimized for tablets and large phones (smaller fonts, compact sidebar, touch-friendly 44px buttons)
- **480px breakpoint**: Optimized for small phones (extra compact layout)
- **16px chat input** prevents iOS auto-zoom on focus
- **Word-wrap** on all content panels to prevent horizontal overflow

---

## 🚀 GitHub Setup

### Initialize & Push

```bash
cd multiagent-trading-system
git init
git add .
git commit -m "Initial commit: multi-agent trading system"
```

Create a new repository on [github.com/new](https://github.com/new), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/multiagent-trading-system.git
git branch -M main
git push -u origin main
```

### What's Excluded (.gitignore)

- `.env` (secrets), `.venv/`, `__pycache__/`, `.vscode/`, `*.db`, `.vercel/`

---

## ☁️ Vercel Deployment (API Backend)

The FastAPI backend can be deployed as a Vercel serverless function.

### Prerequisites

1. A [Vercel](https://vercel.com) account
2. A hosted PostgreSQL database ([Neon](https://neon.tech), [Supabase](https://supabase.com), or similar)
3. A hosted Redis instance ([Upstash](https://upstash.com) or similar)

### Deploy Steps

1. **Push to GitHub** (see above)

2. **Import project** on [vercel.com/new](https://vercel.com/new) → select your GitHub repo

3. **Set environment variables** in Vercel dashboard → Settings → Environment Variables:

   | Variable | Value |
   |----------|-------|
   | `OPENAI_API_KEY` | Your OpenAI key |
   | `NEWS_API_KEY` | Your NewsAPI key |
   | `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` (hosted DB) |
   | `REDIS_URL` | `redis://user:pass@host:port` (hosted Redis) |
   | `SECRET_KEY` | A strong random string |

4. **Deploy** — Vercel auto-detects `vercel.json` and builds the Python function

### Vercel Config

The project includes `vercel.json` which routes all requests to the FastAPI app via `vercel_app.py`.

> **Note**: Vercel serverless functions have a 10-second timeout on the free plan (60s on Pro). Complex multi-agent analyses may need the Pro plan.

---

## ☁️ Streamlit Cloud Deployment (Frontend)

For the Streamlit UI, use [Streamlit Cloud](https://streamlit.io/cloud):

1. Push your repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Select your repo, branch `main`, file `ui/streamlit_app.py`
4. Set the **Advanced Settings** environment variable:
   - `API_BASE_URL` = your Vercel deployment URL (e.g., `https://your-app.vercel.app`)
5. Deploy

The `.streamlit/config.toml` in this repo configures the dark theme automatically.

---

## 🐳 Full Docker Deployment (Recommended)

For a self-hosted deployment with all services:

```bash
# Build and start all services
docker compose up --build -d

# Check logs
docker compose logs -f

# Access the app
# Frontend: http://localhost:8501
# API: http://localhost:8000/docs
```

This starts PostgreSQL, Redis, the FastAPI API, and the Streamlit UI together.

---

## 📝 License

MIT

