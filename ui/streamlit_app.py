"""Streamlit UI — TradingEdge Australia: AI-Powered Global Trading Advisory Platform."""

from __future__ import annotations

import json
import os
import httpx
import streamlit as st


def _get_secret(key: str, default: str = "") -> str:
    """Read a config value from Streamlit secrets (Cloud) or env vars (Docker/local)."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_BASE = _get_secret("API_BASE_URL", "http://localhost:8000") + "/api/v1"
_VERCEL_BYPASS = _get_secret("VERCEL_AUTOMATION_BYPASS_SECRET")

# ---------------------------------------------------------------------------
# Australian Broker Registry
# ---------------------------------------------------------------------------
AUSTRALIAN_BROKERS = {
    "CommSec": {
        "url": "https://www.commsec.com.au",
        "icon": "🏦",
        "desc": "Australia's #1 online broker by Commonwealth Bank",
        "markets": ["ASX", "US", "UK"],
        "type": "Full Service",
    },
    "CMC Markets": {
        "url": "https://www.cmcmarkets.com/en-au",
        "icon": "📊",
        "desc": "CFDs & stockbroking with advanced platform",
        "markets": ["ASX", "US", "UK", "EU", "Asia"],
        "type": "CFD & Stocks",
    },
    "IG Markets": {
        "url": "https://www.ig.com/au",
        "icon": "📈",
        "desc": "World's #1 CFD provider with share trading",
        "markets": ["ASX", "US", "UK", "EU", "Asia", "Forex"],
        "type": "CFD & Stocks",
    },
    "Stake": {
        "url": "https://hellostake.com/au",
        "icon": "🚀",
        "desc": "Commission-free US & ASX share trading",
        "markets": ["ASX", "US"],
        "type": "Commission-Free",
    },
    "SelfWealth": {
        "url": "https://www.selfwealth.com.au",
        "icon": "💰",
        "desc": "Flat-fee ASX trading with community insights",
        "markets": ["ASX", "US"],
        "type": "Flat Fee",
    },
    "Interactive Brokers": {
        "url": "https://www.interactivebrokers.com.au",
        "icon": "🌐",
        "desc": "Global markets access with lowest margin rates",
        "markets": ["ASX", "US", "UK", "EU", "Asia", "Forex", "Options"],
        "type": "Global",
    },
    "Westpac Online Investing": {
        "url": "https://www.westpac.com.au/personal-banking/share-trading",
        "icon": "🏛️",
        "desc": "Share trading by Westpac Banking Corp",
        "markets": ["ASX"],
        "type": "Bank-Backed",
    },
    "nabtrade": {
        "url": "https://www.nabtrade.com.au",
        "icon": "🔷",
        "desc": "NAB's online trading platform for ASX & global",
        "markets": ["ASX", "US", "UK"],
        "type": "Bank-Backed",
    },
    "ANZ Share Investing": {
        "url": "https://www.anz.com.au/personal/investing/online-share-trading",
        "icon": "🔵",
        "desc": "ANZ's share trading platform",
        "markets": ["ASX"],
        "type": "Bank-Backed",
    },
    "Superhero": {
        "url": "https://www.superhero.com.au",
        "icon": "⚡",
        "desc": "Low-cost ASX & US share trading platform",
        "markets": ["ASX", "US", "ETFs"],
        "type": "Low Cost",
    },
    "Saxo Markets": {
        "url": "https://www.home.saxo/en-au",
        "icon": "💹",
        "desc": "Multi-asset trading with professional tools",
        "markets": ["ASX", "US", "UK", "EU", "Asia", "Forex", "Options", "Bonds"],
        "type": "Multi-Asset",
    },
    "eToro Australia": {
        "url": "https://www.etoro.com/en-au",
        "icon": "🌍",
        "desc": "Social trading & copy trading platform",
        "markets": ["ASX", "US", "UK", "EU", "Crypto"],
        "type": "Social Trading",
    },
}

# ASX Top Stocks for quick access
ASX_TOP_STOCKS = ["BHP", "CBA", "CSL", "NAB", "WBC", "ANZ", "FMG", "WES", "MQG", "RIO",
                   "TLS", "WOW", "ALL", "GMG", "TCL", "COL", "STO", "WDS", "JHX", "REA"]

US_TOP_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "AMD"]


st.set_page_config(
    page_title="TradingEdge Australia — AI Trading Advisory",
    page_icon="🦘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Premium eToro/AvaTrade-inspired Dark Theme
# ---------------------------------------------------------------------------
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    :root {
        --bg-primary: #060b14;
        --bg-secondary: #0c1220;
        --bg-card: #111827;
        --bg-card-hover: #162032;
        --border-primary: #1e2d3d;
        --border-accent: #2563eb;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --accent-green: #10b981;
        --accent-red: #ef4444;
        --accent-blue: #3b82f6;
        --accent-yellow: #f59e0b;
        --accent-cyan: #06b6d4;
        --accent-purple: #8b5cf6;
        --gradient-hero: linear-gradient(135deg, #0c1220 0%, #1a1a3e 40%, #0f172a 100%);
        --gradient-card: linear-gradient(135deg, #111827 0%, #0f172a 100%);
        --gradient-accent: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%);
        --shadow-glow: 0 0 40px rgba(59, 130, 246, 0.1);
    }

    .stApp { background-color: var(--bg-primary); font-family: 'Inter', sans-serif; }

    /* ===== HERO SECTION ===== */
    .hero-section {
        background: var(--gradient-hero);
        border-radius: 20px;
        padding: 48px 40px;
        margin-bottom: 24px;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(59, 130, 246, 0.15);
        box-shadow: var(--shadow-glow);
    }
    .hero-section::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-section::after {
        content: '';
        position: absolute;
        bottom: -30%;
        left: -10%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(6,182,212,0.06) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
    }
    .hero-logo {
        font-size: 2.2rem;
        line-height: 1;
    }
    .hero-brand-text {
        font-size: 1.1rem;
        font-weight: 800;
        color: var(--text-primary);
        letter-spacing: -0.02em;
    }
    .hero-brand-sub {
        font-size: 0.7rem;
        color: var(--accent-cyan);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 900;
        color: var(--text-primary);
        margin: 16px 0 12px 0;
        line-height: 1.15;
        letter-spacing: -0.03em;
    }
    .hero-title span { 
        background: var(--gradient-accent);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero-subtitle {
        color: var(--text-secondary);
        font-size: 1.05rem;
        line-height: 1.6;
        max-width: 680px;
        margin-bottom: 24px;
    }
    .hero-badges {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 20px;
    }
    .hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(59, 130, 246, 0.1);
        border: 1px solid rgba(59, 130, 246, 0.2);
        color: var(--accent-blue);
        padding: 6px 14px;
        border-radius: 24px;
        font-size: 0.78rem;
        font-weight: 600;
    }
    .hero-disclaimer {
        color: var(--text-muted);
        font-size: 0.7rem;
        margin-top: 16px;
        padding-top: 12px;
        border-top: 1px solid rgba(255,255,255,0.05);
        line-height: 1.5;
    }

    /* ===== MAIN HEADER ===== */
    .main-header {
        background: var(--gradient-card);
        border: 1px solid var(--border-primary);
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 20px;
        box-shadow: var(--shadow-glow);
    }
    .main-header h1 { color: var(--text-primary); margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }
    .main-header p { color: var(--text-secondary); margin: 4px 0 0 0; font-size: 0.85rem; }

    /* ===== FEATURE CARDS ===== */
    .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    .feature-card {
        background: var(--gradient-card);
        border: 1px solid var(--border-primary);
        border-radius: 14px;
        padding: 24px;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    .feature-card:hover {
        border-color: var(--border-accent);
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(59,130,246,0.1);
    }
    .feature-icon {
        font-size: 2rem;
        margin-bottom: 12px;
        display: block;
    }
    .feature-title {
        color: var(--text-primary);
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .feature-desc {
        color: var(--text-secondary);
        font-size: 0.82rem;
        line-height: 1.5;
    }

    /* ===== METRIC CARDS ===== */
    .metric-card {
        background: var(--gradient-card);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
        padding: 16px 18px;
        text-align: center;
        transition: border-color 0.2s;
    }
    .metric-card:hover { border-color: rgba(59,130,246,0.3); }
    .metric-label { color: var(--text-muted); font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 1.4rem; font-weight: 700; margin-top: 4px; }
    .metric-sub { color: var(--text-muted); font-size: 0.75rem; margin-top: 2px; }
    .metric-green { color: var(--accent-green); }
    .metric-red { color: var(--accent-red); }
    .metric-yellow { color: var(--accent-yellow); }
    .metric-blue { color: var(--accent-blue); }
    .metric-white { color: var(--text-primary); }

    /* ===== BROKER CARDS ===== */
    .broker-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 14px;
        margin: 16px 0;
    }
    .broker-card {
        background: var(--gradient-card);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
        padding: 18px;
        transition: all 0.3s ease;
        cursor: pointer;
        text-decoration: none;
        display: block;
    }
    .broker-card:hover {
        border-color: var(--accent-cyan);
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(6,182,212,0.1);
    }
    .broker-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
    }
    .broker-icon { font-size: 1.5rem; }
    .broker-name { color: var(--text-primary); font-size: 0.95rem; font-weight: 700; }
    .broker-type {
        background: rgba(6,182,212,0.12);
        color: var(--accent-cyan);
        font-size: 0.65rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 10px;
        margin-left: auto;
    }
    .broker-desc { color: var(--text-secondary); font-size: 0.78rem; line-height: 1.4; margin-bottom: 8px; }
    .broker-markets {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
    }
    .broker-market-tag {
        background: rgba(59,130,246,0.1);
        color: var(--accent-blue);
        font-size: 0.65rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 8px;
        border: 1px solid rgba(59,130,246,0.15);
    }

    /* ===== DECISION BADGES ===== */
    .decision-badge {
        display: inline-block;
        padding: 8px 24px;
        border-radius: 8px;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .badge-buy { background: rgba(16,185,129,0.15); color: var(--accent-green); border: 1px solid var(--accent-green); }
    .badge-sell { background: rgba(239,68,68,0.15); color: var(--accent-red); border: 1px solid var(--accent-red); }
    .badge-hold { background: rgba(245,158,11,0.15); color: var(--accent-yellow); border: 1px solid var(--accent-yellow); }

    /* ===== AGENT PANELS ===== */
    .agent-panel {
        background: var(--bg-card);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .agent-panel h4 { color: var(--text-primary); margin: 0 0 8px 0; font-size: 0.9rem; font-weight: 600; }
    .agent-panel p { color: var(--text-secondary); font-size: 0.82rem; line-height: 1.5; margin: 0; word-wrap: break-word; overflow-wrap: break-word; }

    /* ===== SIGNAL TAGS ===== */
    .signal-tag {
        display: inline-block;
        background: rgba(59,130,246,0.12);
        color: #60a5fa;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 500;
        margin: 2px 3px;
        border: 1px solid rgba(59,130,246,0.25);
    }
    .signal-tag-warn {
        background: rgba(245,158,11,0.12);
        color: var(--accent-yellow);
        border-color: rgba(245,158,11,0.25);
    }
    .signal-tag-bad {
        background: rgba(239,68,68,0.12);
        color: var(--accent-red);
        border-color: rgba(239,68,68,0.25);
    }

    /* ===== NEWS ITEMS ===== */
    .news-item {
        background: var(--bg-card);
        border: 1px solid var(--border-primary);
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
        transition: border-color 0.2s;
    }
    .news-item:hover { border-color: rgba(59,130,246,0.3); }
    .news-item h5 { color: var(--text-primary); margin: 0 0 4px 0; font-size: 0.82rem; font-weight: 500; }
    .news-item p { color: var(--text-secondary); font-size: 0.75rem; margin: 0; line-height: 1.4; word-wrap: break-word; }
    .news-meta { color: var(--text-muted); font-size: 0.68rem; margin-top: 4px; }

    /* ===== RISK BAR ===== */
    .risk-bar-bg { background: var(--border-primary); border-radius: 4px; height: 8px; width: 100%; }
    .risk-bar { border-radius: 4px; height: 8px; transition: width 0.3s; }

    /* ===== SECTION TITLE ===== */
    .section-title { color: var(--text-secondary); font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin: 18px 0 10px 0; }

    /* ===== SIDEBAR ===== */
    div[data-testid="stSidebar"] { background: var(--bg-secondary); border-right: 1px solid var(--border-primary); }
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 { color: var(--text-primary); }

    /* ===== STAT BAR ===== */
    .stat-bar {
        display: flex;
        justify-content: center;
        gap: 32px;
        padding: 14px 0;
        margin-bottom: 20px;
        background: var(--gradient-card);
        border: 1px solid var(--border-primary);
        border-radius: 12px;
    }
    .stat-item { text-align: center; }
    .stat-number { color: var(--text-primary); font-size: 1.3rem; font-weight: 800; }
    .stat-label { color: var(--text-muted); font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }

    /* ===== ADVISORY DISCLAIMER BAR ===== */
    .advisory-bar {
        background: rgba(245,158,11,0.08);
        border: 1px solid rgba(245,158,11,0.2);
        border-radius: 10px;
        padding: 12px 18px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .advisory-bar-icon { font-size: 1.1rem; }
    .advisory-bar-text { color: var(--accent-yellow); font-size: 0.78rem; line-height: 1.4; }

    /* ===== TABS STYLING ===== */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: var(--bg-card);
        border-radius: 8px;
        border: 1px solid var(--border-primary);
        color: var(--text-secondary);
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(59,130,246,0.15) !important;
        border-color: var(--accent-blue) !important;
        color: var(--accent-blue) !important;
    }

    /* ===== MOBILE RESPONSIVE ===== */
    @media (max-width: 768px) {
        .hero-section { padding: 28px 20px; border-radius: 14px; }
        .hero-title { font-size: 1.6rem; }
        .hero-subtitle { font-size: 0.9rem; }
        .hero-badges { gap: 8px; }
        .hero-badge { font-size: 0.7rem; padding: 4px 10px; }
        .feature-grid { grid-template-columns: 1fr; gap: 10px; }
        .broker-grid { grid-template-columns: 1fr; }

        .main-header { padding: 14px 16px; margin-bottom: 12px; border-radius: 10px; }
        .main-header h1 { font-size: 1.15rem; }
        .main-header p { font-size: 0.75rem; }

        .metric-card { padding: 10px 8px; border-radius: 8px; }
        .metric-label { font-size: 0.62rem; letter-spacing: 0.5px; }
        .metric-value { font-size: 1rem; }
        .metric-sub { font-size: 0.65rem; }

        .decision-badge { padding: 5px 14px; font-size: 0.9rem; }

        .agent-panel { padding: 12px; border-radius: 8px; }
        .agent-panel h4 { font-size: 0.82rem; }
        .agent-panel p { font-size: 0.75rem; }

        .signal-tag { font-size: 0.65rem; padding: 2px 8px; margin: 1px 2px; }

        .news-item { padding: 10px 12px; }
        .news-item h5 { font-size: 0.78rem; }
        .news-item p { font-size: 0.7rem; }

        .section-title { font-size: 0.7rem; margin: 12px 0 8px 0; }

        .stat-bar { flex-wrap: wrap; gap: 16px; padding: 10px; }
        .stat-number { font-size: 1rem; }

        section[data-testid="stSidebar"] { min-width: 260px !important; max-width: 280px !important; }
        .stChatInput textarea { font-size: 16px !important; }
        .stButton > button { min-height: 44px; font-size: 0.85rem; }
        div[data-testid="column"] { padding-left: 4px !important; padding-right: 4px !important; }
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1rem !important; }
    }

    @media (max-width: 480px) {
        .hero-section { padding: 20px 14px; }
        .hero-title { font-size: 1.3rem; }
        .main-header { padding: 12px 12px; }
        .main-header h1 { font-size: 1rem; }
        .metric-value { font-size: 0.9rem; }
        .metric-label { font-size: 0.58rem; }
        .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "session_cost" not in st.session_state:
    st.session_state.session_cost = {
        "total_cost_usd": 0.0,
        "total_tokens": 0,
        "total_prompt_tokens": 0,
        "total_completion_tokens": 0,
        "total_llm_calls": 0,
        "prompt_count": 0,
    }
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False
if "show_brokers" not in st.session_state:
    st.session_state.show_brokers = False
if "active_page" not in st.session_state:
    st.session_state.active_page = "dashboard"

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _auth_headers() -> dict:
    headers: dict[str, str] = {}
    if st.session_state.auth_token:
        headers["Authorization"] = f"Bearer {st.session_state.auth_token}"
    if _VERCEL_BYPASS:
        headers["x-vercel-protection-bypass"] = _VERCEL_BYPASS
    return headers


def _bypass_headers() -> dict:
    """Return only the Vercel bypass header (for unauthenticated calls)."""
    if _VERCEL_BYPASS:
        return {"x-vercel-protection-bypass": _VERCEL_BYPASS}
    return {}


def _api_register(email: str, name: str, password: str) -> dict:
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{API_BASE}/auth/register", json={
                "email": email, "name": name, "password": password,
            }, headers=_bypass_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        try:
            return {"error": exc.response.json().get("detail", str(exc))}
        except Exception:
            return {"error": str(exc)}
    except Exception as exc:
        return {"error": str(exc)}


def _api_login(email: str, password: str) -> dict:
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{API_BASE}/auth/login", json={
                "email": email, "password": password,
            }, headers=_bypass_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as exc:
        try:
            return {"error": exc.response.json().get("detail", str(exc))}
        except Exception:
            return {"error": str(exc)}
    except Exception as exc:
        return {"error": str(exc)}


def _api_get_profile() -> dict | None:
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{API_BASE}/auth/me", headers=_auth_headers())
            resp.raise_for_status()
            return resp.json().get("user")
    except Exception:
        return None


def _call_api(message: str) -> dict:
    """Call the /chat endpoint — OpenClaw-style natural language."""
    try:
        with httpx.Client(timeout=180) as client:
            resp = client.post(
                f"{API_BASE}/chat",
                json={"message": message},
                headers=_auth_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"error": "Cannot connect to API server. Check that the backend is deployed and API_BASE_URL is correct."}
    except httpx.ReadTimeout:
        return {"error": "Request timed out. The analysis is taking too long — try a simpler query or single stock."}
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = f"HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        return {"error": detail}
    except Exception as exc:
        return {"error": f"Unexpected error: {exc}"}


def _fmt_number(n, decimals=2) -> str:
    if n is None:
        return "N/A"
    return f"{n:,.{decimals}f}"


def _fmt_pct(n) -> str:
    if n is None:
        return "N/A"
    return f"{n:+.2f}%"


def _fmt_large(n) -> str:
    if n is None:
        return "N/A"
    if isinstance(n, str):
        return n
    if n >= 1e12:
        return f"${n/1e12:.1f}T"
    if n >= 1e9:
        return f"${n/1e9:.1f}B"
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    return f"${n:,.0f}"


def _render_global_macro_card(macro: dict):
    """Render a compact global macro overview card."""
    regime = macro.get("global_regime", "unknown").replace("_", " ").title()
    bias = macro.get("overall_bias", "neutral").replace("_", " ").title()
    cycle = macro.get("market_cycle_phase", "uncertain").replace("_", " ").title()
    vix_assessment = macro.get("vix_assessment", "unknown").replace("_", " ").title()
    cross = macro.get("cross_market_signals", {})
    vix_level = cross.get("vix_level", "N/A")
    guidance = macro.get("buy_sell_guidance", {})
    action_bias = guidance.get("action_bias", "stay_selective").replace("_", " ").title()
    sizing = guidance.get("position_sizing", "reduced").title()
    recommended = macro.get("recommended_sectors", [])
    avoid = macro.get("avoid_sectors", [])

    # Color coding
    bias_color = "#22c55e" if "bullish" in bias.lower() else ("#ef4444" if "bearish" in bias.lower() else "#f59e0b")
    regime_color = "#22c55e" if regime.lower() == "risk on" else ("#ef4444" if regime.lower() == "risk off" else "#f59e0b")

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 100%);border:1px solid #334155;border-radius:12px;padding:20px;margin:16px 0;">
        <div style="display:flex;align-items:center;margin-bottom:12px;">
            <span style="font-size:1.3em;margin-right:8px;">🌍</span>
            <span style="font-size:1.1em;font-weight:700;color:#e2e8f0;">Global Macro Overlay</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px;">
            <div style="text-align:center;">
                <div style="color:#94a3b8;font-size:0.75em;">Regime</div>
                <div style="color:{regime_color};font-weight:700;">{regime}</div>
            </div>
            <div style="text-align:center;">
                <div style="color:#94a3b8;font-size:0.75em;">Bias</div>
                <div style="color:{bias_color};font-weight:700;">{bias}</div>
            </div>
            <div style="text-align:center;">
                <div style="color:#94a3b8;font-size:0.75em;">VIX</div>
                <div style="color:#e2e8f0;font-weight:700;">{vix_level} ({vix_assessment})</div>
            </div>
            <div style="text-align:center;">
                <div style="color:#94a3b8;font-size:0.75em;">Cycle</div>
                <div style="color:#e2e8f0;font-weight:700;">{cycle}</div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
            <div style="text-align:center;">
                <div style="color:#94a3b8;font-size:0.75em;">Action Bias</div>
                <div style="color:#60a5fa;font-weight:700;">{action_bias}</div>
            </div>
            <div style="text-align:center;">
                <div style="color:#94a3b8;font-size:0.75em;">Position Sizing</div>
                <div style="color:#60a5fa;font-weight:700;">{sizing}</div>
            </div>
        </div>
        {"<div style='margin-top:12px;'><span style=\"color:#94a3b8;font-size:0.75em;\">Recommended: </span><span style=\"color:#22c55e;font-size:0.85em;\">" + ', '.join(recommended) + "</span></div>" if recommended else ""}
        {"<div><span style='color:#94a3b8;font-size:0.75em;'>Avoid: </span><span style='color:#ef4444;font-size:0.85em;'>" + ', '.join(avoid) + "</span></div>" if avoid else ""}
    </div>
    """, unsafe_allow_html=True)


def _render_analysis(r: dict):
    """Render a full professional analysis dashboard for one symbol."""
    decision = r.get("decision", {})
    market = r.get("market_data", {})
    sentiment = r.get("sentiment", {})
    risk = r.get("risk", {})
    articles = r.get("news_articles", [])

    action = decision.get("action", "HOLD")
    confidence = decision.get("confidence", 0)
    badge_class = {"BUY": "badge-buy", "SELL": "badge-sell"}.get(action, "badge-hold")

    symbol = r.get("symbol", "?")
    company = market.get("company_name", symbol)
    sector = market.get("sector", "")

    # ============ HEADER ============
    st.markdown(f"""
    <div class="main-header">
        <h1>📊 {company} ({symbol})</h1>
        <p>{sector} &nbsp;•&nbsp; Analysis completed in {r.get('elapsed_seconds', 0):.1f}s</p>
    </div>
    """, unsafe_allow_html=True)

    # ============ DECISION BANNER ============
    col_dec, col_conf, col_horizon = st.columns([2, 1, 1])
    with col_dec:
        st.markdown(f'<div class="decision-badge {badge_class}">{action}</div>', unsafe_allow_html=True)
    with col_conf:
        conf_color = "metric-green" if confidence >= 0.7 else ("metric-yellow" if confidence >= 0.4 else "metric-red")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Confidence</div>
            <div class="metric-value {conf_color}">{confidence:.0%}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_horizon:
        horizon = decision.get("time_horizon", "N/A")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Time Horizon</div>
            <div class="metric-value metric-blue">{horizon}</div>
        </div>
        """, unsafe_allow_html=True)

    # ============ KEY METRICS ROW ============
    price = market.get("price")
    change = market.get("price_change_pct", 0)
    change_color = "metric-green" if change and change >= 0 else "metric-red"

    cols = st.columns(6)
    metrics = [
        ("Price", f"${_fmt_number(price)}", change_color),
        ("Change", _fmt_pct(change), change_color),
        ("RSI", _fmt_number(market.get("rsi"), 1), "metric-yellow" if market.get("rsi") and (market["rsi"] > 70 or market["rsi"] < 30) else "metric-white"),
        ("P/E Ratio", _fmt_number(market.get("pe_ratio"), 1), "metric-white"),
        ("Market Cap", market.get("market_cap_formatted", "N/A"), "metric-blue"),
        ("Beta", _fmt_number(market.get("beta")), "metric-white"),
    ]
    for col, (label, value, color) in zip(cols, metrics):
        col.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value {color}">{value}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # ============ PRICE CHART ============
    price_history = market.get("price_history_30d", [])
    if price_history:
        import pandas as pd
        df = pd.DataFrame(price_history)
        if "date" in df.columns and "close" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            st.markdown('<div class="section-title">📈 30-Day Price History</div>', unsafe_allow_html=True)
            st.line_chart(df.set_index("date")["close"], use_container_width=True)

    # ============ TWO-COLUMN LAYOUT: Technical + Fundamentals ============
    left_col, right_col = st.columns(2)

    with left_col:
        st.markdown('<div class="section-title">⚡ Technical Indicators</div>', unsafe_allow_html=True)
        tech_lines = []
        for label, key in [("MA20", "ma20"), ("MA50", "ma50"), ("MA200", "ma200")]:
            v = market.get(key)
            if v:
                tech_lines.append(f"**{label}:** ${_fmt_number(v)}")
        for label, key in [("EMA12", "ema12"), ("EMA26", "ema26")]:
            v = market.get(key)
            if v:
                tech_lines.append(f"**{label}:** ${_fmt_number(v)}")
        macd_val = market.get("macd")
        macd_sig = market.get("macd_signal")
        if macd_val is not None:
            tech_lines.append(f"**MACD:** {macd_val:.3f} | **Signal:** {macd_sig:.3f}")
        tech_lines.append(f"**Volatility:** {_fmt_number(market.get('volatility'), 1)}%")
        w52h = market.get("week52_high")
        w52l = market.get("week52_low")
        if w52h and w52l:
            tech_lines.append(f"**52-Week Range:** ${_fmt_number(w52l)} — ${_fmt_number(w52h)}")

        st.markdown(f"""<div class="agent-panel"><p>{'<br>'.join(tech_lines)}</p></div>""", unsafe_allow_html=True)

        # Signals
        signals = market.get("signals", [])
        if signals:
            tags_html = "".join(f'<span class="signal-tag">{s}</span>' for s in signals)
            st.markdown(f'<div style="margin-bottom:12px">{tags_html}</div>', unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="section-title">🏢 Fundamentals</div>', unsafe_allow_html=True)
        fund_lines = []
        if market.get("eps"):
            fund_lines.append(f"**EPS:** ${_fmt_number(market['eps'])}")
        if market.get("pe_ratio"):
            fund_lines.append(f"**P/E Ratio:** {_fmt_number(market['pe_ratio'], 1)}")
        if market.get("dividend_yield"):
            fund_lines.append(f"**Dividend Yield:** {market['dividend_yield']:.2%}")
        if market.get("market_cap_formatted"):
            fund_lines.append(f"**Market Cap:** {market['market_cap_formatted']}")
        if market.get("beta"):
            fund_lines.append(f"**Beta:** {_fmt_number(market['beta'])}")
        vol = market.get("volume")
        avg_vol = market.get("avg_volume")
        if vol:
            fund_lines.append(f"**Volume:** {vol:,.0f}")
        if avg_vol:
            fund_lines.append(f"**Avg Volume:** {avg_vol:,.0f}")
        if not fund_lines:
            fund_lines.append("No fundamental data available")

        st.markdown(f"""<div class="agent-panel"><p>{'<br>'.join(fund_lines)}</p></div>""", unsafe_allow_html=True)

        # Suggested levels
        entry = decision.get("suggested_entry")
        sl = decision.get("suggested_stop_loss")
        tp = decision.get("target_price")
        if any([entry, sl, tp]):
            st.markdown('<div class="section-title">🎯 Price Targets</div>', unsafe_allow_html=True)
            level_lines = []
            if entry:
                level_lines.append(f"**Entry:** ${_fmt_number(entry)}")
            if sl:
                level_lines.append(f"**Stop Loss:** ${_fmt_number(sl)}")
            if tp:
                level_lines.append(f"**Target:** ${_fmt_number(tp)}")
            st.markdown(f"""<div class="agent-panel"><p>{'<br>'.join(level_lines)}</p></div>""", unsafe_allow_html=True)

    # ============ RISK ASSESSMENT ============
    st.markdown('<div class="section-title">🛡️ Risk Assessment</div>', unsafe_allow_html=True)
    risk_score = risk.get("risk_score", 0)
    risk_level = risk.get("risk_level", "unknown")
    risk_color = {"low": "#00d26a", "medium": "#ffa502", "high": "#ff4757"}.get(risk_level, "#7a8fa6")
    risk_width = max(risk_score * 10, 5)

    st.markdown(f"""
    <div class="agent-panel">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <span style="color:#e1e8f0;font-weight:600">Risk Score: {risk_score}/10</span>
            <span style="color:{risk_color};font-weight:600;text-transform:uppercase">{risk_level}</span>
        </div>
        <div class="risk-bar-bg"><div class="risk-bar" style="width:{risk_width}%;background:{risk_color}"></div></div>
    </div>
    """, unsafe_allow_html=True)

    warnings = risk.get("warnings", [])
    if warnings:
        warn_html = "".join(f'<span class="signal-tag signal-tag-warn">⚠ {w}</span>' for w in warnings)
        st.markdown(f'<div style="margin-bottom:12px">{warn_html}</div>', unsafe_allow_html=True)

    constraints = risk.get("constraints", [])
    if constraints:
        con_html = "".join(f'<span class="signal-tag signal-tag-bad">🚫 {c}</span>' for c in constraints)
        st.markdown(f'<div style="margin-bottom:12px">{con_html}</div>', unsafe_allow_html=True)

    # ============ SENTIMENT ============
    st.markdown('<div class="section-title">💭 News Sentiment</div>', unsafe_allow_html=True)
    sent = sentiment.get("sentiment", "neutral")
    sent_conf = sentiment.get("confidence", 0)
    sent_icon = {"strongly_positive": "🟢", "positive": "🟢", "neutral": "⚪", "negative": "🔴", "strongly_negative": "🔴", "mixed": "🟡"}.get(sent, "⚪")
    media_tone = sentiment.get("media_tone", "")
    sent_reasoning = sentiment.get("reasoning", "")
    themes = sentiment.get("key_themes", [])
    catalysts = sentiment.get("catalysts", [])

    st.markdown(f"""
    <div class="agent-panel">
        <h4>{sent_icon} {sent.replace('_', ' ').title()} (confidence: {sent_conf:.0%})</h4>
        <p>{sent_reasoning}</p>
    </div>
    """, unsafe_allow_html=True)

    if themes:
        theme_html = "".join(f'<span class="signal-tag">{t}</span>' for t in themes)
        st.markdown(f'<div style="margin-bottom:4px"><strong style="color:#7a8fa6;font-size:0.72rem">THEMES:</strong> {theme_html}</div>', unsafe_allow_html=True)
    if catalysts:
        cat_html = "".join(f'<span class="signal-tag signal-tag-warn">{c}</span>' for c in catalysts)
        st.markdown(f'<div style="margin-bottom:12px"><strong style="color:#7a8fa6;font-size:0.72rem">CATALYSTS:</strong> {cat_html}</div>', unsafe_allow_html=True)

    # ============ DECISION REASONING ============
    st.markdown('<div class="section-title">🧠 AI Analysis</div>', unsafe_allow_html=True)
    reasoning = decision.get("reasoning", "No reasoning provided.")
    key_factors = decision.get("key_factors", [])

    st.markdown(f"""
    <div class="agent-panel">
        <p>{reasoning}</p>
    </div>
    """, unsafe_allow_html=True)

    if key_factors:
        factors_html = "".join(f'<span class="signal-tag">{f}</span>' for f in key_factors)
        st.markdown(f'<div style="margin-bottom:12px"><strong style="color:#7a8fa6;font-size:0.72rem">KEY FACTORS:</strong> {factors_html}</div>', unsafe_allow_html=True)

    # ============ WEB RESEARCH INTELLIGENCE ============
    research = r.get("research", {})
    research_summary = research.get("research_summary", "")
    if research_summary and research_summary not in ("", "No web research data available", "unknown"):
        st.markdown('<div class="section-title">🔍 Web Research Intelligence</div>', unsafe_allow_html=True)

        res_left, res_right = st.columns(2)
        with res_left:
            consensus = research.get("analyst_consensus", "unknown")
            consensus_color = {"buy": "metric-green", "strong_buy": "metric-green", "sell": "metric-red", "strong_sell": "metric-red"}.get(consensus, "metric-yellow")
            avg_target = research.get("average_price_target")
            target_range = research.get("price_target_range", {})

            lines = [f"**Analyst Consensus:** <span class='{consensus_color}'>{consensus.replace('_', ' ').upper()}</span>"]
            if avg_target:
                lines.append(f"**Avg Price Target:** ${_fmt_number(avg_target)}")
            if target_range.get("low") and target_range.get("high"):
                lines.append(f"**Target Range:** ${_fmt_number(target_range['low'])} — ${_fmt_number(target_range['high'])}")
            earnings = research.get("recent_earnings_surprise", "unknown")
            if earnings != "unknown":
                earn_icon = {"beat": "🟢", "miss": "🔴", "inline": "🟡"}.get(earnings, "⚪")
                lines.append(f"**Earnings:** {earn_icon} {earnings.title()}")
            rev = research.get("revenue_trend", "unknown")
            if rev != "unknown":
                lines.append(f"**Revenue Trend:** {rev.title()}")

            st.markdown(f"""<div class="agent-panel"><p>{'<br>'.join(lines)}</p></div>""", unsafe_allow_html=True)

        with res_right:
            lines2 = []
            comp = research.get("competitive_position", "unknown")
            if comp != "unknown":
                lines2.append(f"**Competitive Position:** {comp.title()}")
            insider = research.get("insider_activity", "unknown")
            if insider != "unknown":
                lines2.append(f"**Insider Activity:** {insider.title()}")
            sources = research.get("sources_searched", 0)
            pages = research.get("pages_analyzed", 0)
            lines2.append(f"**Sources:** {sources} searched, {pages} pages analyzed")
            if not lines2:
                lines2.append("No additional research data")
            st.markdown(f"""<div class="agent-panel"><p>{'<br>'.join(lines2)}</p></div>""", unsafe_allow_html=True)

        # Key developments
        devs = research.get("key_developments", [])
        if devs:
            dev_html = "".join(f'<span class="signal-tag">{d}</span>' for d in devs)
            st.markdown(f'<div style="margin-bottom:4px"><strong style="color:#7a8fa6;font-size:0.72rem">KEY DEVELOPMENTS:</strong> {dev_html}</div>', unsafe_allow_html=True)

        opps = research.get("opportunities_from_research", [])
        if opps:
            opp_html = "".join(f'<span class="signal-tag">{o}</span>' for o in opps)
            st.markdown(f'<div style="margin-bottom:4px"><strong style="color:#7a8fa6;font-size:0.72rem">OPPORTUNITIES:</strong> {opp_html}</div>', unsafe_allow_html=True)

        risks_r = research.get("risks_from_research", [])
        if risks_r:
            risk_html = "".join(f'<span class="signal-tag signal-tag-warn">{rr}</span>' for rr in risks_r)
            st.markdown(f'<div style="margin-bottom:4px"><strong style="color:#7a8fa6;font-size:0.72rem">RESEARCH RISKS:</strong> {risk_html}</div>', unsafe_allow_html=True)

        st.markdown(f"""<div class="agent-panel"><p>{research_summary}</p></div>""", unsafe_allow_html=True)

    # ============ NEWS FEED ============
    if articles:
        st.markdown(f'<div class="section-title">📰 Recent News ({r.get("news_article_count", len(articles))} articles)</div>', unsafe_allow_html=True)
        for a in articles[:8]:
            title = a.get("title", "Untitled")
            desc = a.get("description", "")[:200]
            source = a.get("source", "Unknown")
            pub = (a.get("published") or "")[:10]
            url = a.get("url", "")
            title_display = f'<a href="{url}" target="_blank" style="color:#60a5fa;text-decoration:none">{title}</a>' if url else title
            st.markdown(f"""
            <div class="news-item">
                <h5>{title_display}</h5>
                <p>{desc}</p>
                <div class="news-meta">{source} &nbsp;•&nbsp; {pub}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")


# ---------------------------------------------------------------------------
# Admin Panel
# ---------------------------------------------------------------------------
def _render_admin_panel():
    """Full admin panel for user management."""
    st.markdown("""
    <div class="main-header">
        <h1>🔧 Admin Panel</h1>
        <p>Manage users, approvals, tiers, and system settings</p>
    </div>
    """, unsafe_allow_html=True)

    # Stats overview
    try:
        with httpx.Client(timeout=10) as client:
            stats = client.get(f"{API_BASE}/admin/stats", headers=_auth_headers()).json()
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"""<div class="metric-card"><div class="metric-label">Total Users</div>
            <div class="metric-value metric-blue">{stats.get('total_users', 0)}</div></div>""", unsafe_allow_html=True)
        c2.markdown(f"""<div class="metric-card"><div class="metric-label">Paid Users</div>
            <div class="metric-value metric-green">{stats.get('paid_users', 0)}</div></div>""", unsafe_allow_html=True)
        c3.markdown(f"""<div class="metric-card"><div class="metric-label">Free Users</div>
            <div class="metric-value metric-yellow">{stats.get('free_users', 0)}</div></div>""", unsafe_allow_html=True)
        c4.markdown(f"""<div class="metric-card"><div class="metric-label">Pending Approval</div>
            <div class="metric-value metric-red">{stats.get('pending_approval', 0)}</div></div>""", unsafe_allow_html=True)

        st.markdown("")
        ec1, ec2 = st.columns(2)
        ec1.markdown(f"""<div class="metric-card"><div class="metric-label">Total Prompts</div>
            <div class="metric-value metric-white">{stats.get('total_prompts', 0):,}</div></div>""", unsafe_allow_html=True)
        ec2.markdown(f"""<div class="metric-card"><div class="metric-label">Total API Cost</div>
            <div class="metric-value metric-yellow">${stats.get('total_cost_usd', 0):.4f}</div></div>""", unsafe_allow_html=True)
    except Exception:
        st.warning("Could not load admin stats")

    st.markdown("")
    st.markdown("---")

    # Admin password change
    st.markdown("### 🔑 Change Admin Password")
    with st.form("admin_pw_form"):
        new_pw = st.text_input("New Password", type="password", key="admin_new_pw")
        confirm_pw = st.text_input("Confirm Password", type="password", key="admin_confirm_pw")
        if st.form_submit_button("Change Password", use_container_width=True):
            if not new_pw or len(new_pw) < 6:
                st.error("Password must be at least 6 characters")
            elif new_pw != confirm_pw:
                st.error("Passwords do not match")
            else:
                try:
                    with httpx.Client(timeout=10) as client:
                        resp = client.post(
                            f"{API_BASE}/admin/change-password",
                            json={"new_password": new_pw},
                            headers=_auth_headers(),
                        )
                        resp.raise_for_status()
                    st.success("Admin password changed!")
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown("---")

    # User management table
    st.markdown("### 👥 User Management")
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{API_BASE}/admin/users", headers=_auth_headers())
            resp.raise_for_status()
            users = resp.json().get("users", [])
    except Exception:
        st.error("Could not load users")
        return

    if not users:
        st.info("No users registered yet.")
        return

    for u in users:
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 2])
            with col1:
                role_badge = "🔧" if u["role"] == "admin" else "👤"
                tier_color = "metric-green" if u["tier"] == "paid" else "metric-yellow"
                approved_icon = "✅" if u["is_approved"] else "⏳"
                st.markdown(f"""
                <div class="agent-panel">
                    <h4>{role_badge} {u['name']} {approved_icon}</h4>
                    <p>{u['email']}<br>
                    <span class="{tier_color}">{u['tier'].upper()}</span> •
                    {u['prompt_count']} prompts • ${u['total_cost_usd']:.4f} spent<br>
                    Balance: ${u['balance_usd']:.2f} •
                    Joined: {(u.get('created_at') or '')[:10]}</p>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                uid = u["id"][:8]
                new_tier = st.selectbox(
                    "Tier", ["free", "paid"],
                    index=0 if u["tier"] == "free" else 1,
                    key=f"tier_{uid}",
                )
                new_approved = st.checkbox(
                    "Approved",
                    value=u["is_approved"],
                    key=f"approved_{uid}",
                )
                new_balance = st.number_input(
                    "Balance $",
                    value=float(u["balance_usd"]),
                    min_value=0.0,
                    step=1.0,
                    key=f"bal_{uid}",
                )
            with col3:
                if st.button("💾 Save", key=f"save_{uid}", use_container_width=True):
                    try:
                        with httpx.Client(timeout=10) as client:
                            resp = client.put(
                                f"{API_BASE}/admin/users/{u['id']}",
                                json={
                                    "tier": new_tier,
                                    "is_approved": new_approved,
                                    "balance_usd": new_balance,
                                },
                                headers=_auth_headers(),
                            )
                            resp.raise_for_status()
                        st.success(f"Updated {u['email']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")

                if u["role"] != "admin":
                    if st.button("🗑️ Delete", key=f"del_{uid}", use_container_width=True):
                        try:
                            with httpx.Client(timeout=10) as client:
                                resp = client.delete(
                                    f"{API_BASE}/admin/users/{u['id']}",
                                    headers=_auth_headers(),
                                )
                                resp.raise_for_status()
                            st.success(f"Deleted {u['email']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
            st.markdown("---")


# ---------------------------------------------------------------------------
# Login / Register screen
# ---------------------------------------------------------------------------
def _render_broker_panel():
    """Render the Australian broker integration panel."""
    st.markdown("""
    <div class="main-header">
        <h1>🏦 Australian Broker Partners</h1>
        <p>Execute your trades through Australia's leading stockbrokers — we provide the intelligence, you choose where to trade</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="advisory-bar">
        <span class="advisory-bar-icon">⚡</span>
        <span class="advisory-bar-text">
            <strong>How it works:</strong> TradingEdge provides AI-powered analysis and recommendations.
            When you're ready to act, click through to your preferred broker to execute trades directly.
            We are an advisory service — not a broker or financial intermediary.
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Filter
    filter_col1, filter_col2 = st.columns([2, 3])
    with filter_col1:
        broker_type_filter = st.selectbox(
            "Filter by type",
            ["All", "Full Service", "CFD & Stocks", "Commission-Free", "Flat Fee",
             "Global", "Bank-Backed", "Low Cost", "Multi-Asset", "Social Trading"],
            key="broker_type_filter",
        )
    with filter_col2:
        market_filter = st.selectbox(
            "Filter by market",
            ["All", "ASX", "US", "UK", "EU", "Asia", "Forex", "Options", "Crypto"],
            key="broker_market_filter",
        )

    # Build broker cards HTML
    cards_html = '<div class="broker-grid">'
    for name, info in AUSTRALIAN_BROKERS.items():
        if broker_type_filter != "All" and info["type"] != broker_type_filter:
            continue
        if market_filter != "All" and market_filter not in info["markets"]:
            continue
        markets_html = "".join(
            f'<span class="broker-market-tag">{m}</span>' for m in info["markets"]
        )
        cards_html += f"""
        <a href="{info['url']}" target="_blank" class="broker-card" style="text-decoration:none;">
            <div class="broker-header">
                <span class="broker-icon">{info['icon']}</span>
                <span class="broker-name">{name}</span>
                <span class="broker-type">{info['type']}</span>
            </div>
            <div class="broker-desc">{info['desc']}</div>
            <div class="broker-markets">{markets_html}</div>
        </a>
        """
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    st.markdown("""
    <div class="hero-disclaimer" style="margin-top:24px;">
        ⚠️ <strong>Disclaimer:</strong> TradingEdge Australia is not affiliated with, endorsed by, or a partner of any
        broker listed above. Links are provided for your convenience. Always conduct your own due diligence
        before selecting a broker. Broker availability, fees, and features may change without notice.
        Australian Financial Services Licence (AFSL) requirements apply to all brokers.
    </div>
    """, unsafe_allow_html=True)


def _render_landing_page():
    """Render the eToro/AvaTrade-style landing page for unauthenticated users."""

    # ===== TOP NAVIGATION BAR =====
    st.markdown("""
    <style>
        .top-nav {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 24px;
            background: rgba(6,11,20,0.92);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-primary);
            border-radius: 14px;
            margin-bottom: 20px;
        }
        .top-nav-brand {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .top-nav-logo { font-size: 1.5rem; }
        .top-nav-name { color: var(--text-primary); font-weight: 800; font-size: 1rem; letter-spacing: -0.01em; }
        .top-nav-tag { color: var(--accent-cyan); font-size: 0.6rem; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; }
        .top-nav-actions { display: flex; gap: 10px; align-items: center; }
        .top-nav-btn {
            padding: 8px 22px;
            border-radius: 8px;
            font-size: 0.82rem;
            font-weight: 700;
            cursor: pointer;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            border: none;
        }
        .top-nav-btn-signin {
            background: transparent;
            color: var(--text-primary);
            border: 1px solid var(--border-primary);
        }
        .top-nav-btn-signin:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
        .top-nav-btn-create {
            background: var(--gradient-accent);
            color: #fff;
        }
        .top-nav-btn-create:hover { opacity: 0.9; transform: translateY(-1px); }
        @media (max-width: 600px) {
            .top-nav { padding: 10px 14px; }
            .top-nav-name { font-size: 0.85rem; }
            .top-nav-btn { padding: 6px 14px; font-size: 0.75rem; }
        }
    </style>
    """, unsafe_allow_html=True)

    # Render top nav bar with Streamlit columns for interactive buttons
    nav_left, nav_right_1, nav_right_2 = st.columns([6, 1, 1.5])
    with nav_left:
        st.markdown("""
        <div class="top-nav-brand">
            <span class="top-nav-logo">🦘</span>
            <div>
                <div class="top-nav-name">TradingEdge Australia</div>
                <div class="top-nav-tag">AI Trading Advisory</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with nav_right_1:
        if st.button("🔑 Sign In", key="top_signin", use_container_width=True):
            st.session_state["landing_tab"] = "signin"
    with nav_right_2:
        if st.button("🚀 Create Account", key="top_create", use_container_width=True, type="primary"):
            st.session_state["landing_tab"] = "create"

    # ===== INLINE AUTH FORMS (shown when top nav buttons clicked) =====
    _landing_tab = st.session_state.get("landing_tab")
    if _landing_tab == "signin":
        st.markdown("""
        <div class="main-header">
            <h1>🔑 Sign In to TradingEdge</h1>
            <p>Access your AI trading advisory dashboard</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("top_login_form"):
            top_email = st.text_input("Email", key="top_login_email", placeholder="you@example.com")
            top_password = st.text_input("Password", type="password", key="top_login_pw")
            col_submit, col_cancel = st.columns([3, 1])
            with col_submit:
                submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            with col_cancel:
                cancelled = st.form_submit_button("✕ Close", use_container_width=True)
            if cancelled:
                st.session_state.pop("landing_tab", None)
                st.rerun()
            if submitted:
                if not top_email or not top_password:
                    st.error("Please fill in all fields")
                else:
                    result = _api_login(top_email, top_password)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.auth_token = result["access_token"]
                        st.session_state.auth_user = result["user"]
                        st.session_state.pop("landing_tab", None)
                        st.rerun()

    elif _landing_tab == "create":
        st.markdown("""
        <div class="main-header">
            <h1>🚀 Create Your Free Account</h1>
            <p>Get 3 free AI analysis prompts — no credit card required</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("top_register_form"):
            top_reg_name = st.text_input("Full Name", key="top_reg_name", placeholder="John Smith")
            top_reg_email = st.text_input("Email", key="top_reg_email", placeholder="you@example.com")
            top_reg_pw = st.text_input("Password", type="password", key="top_reg_pw")
            top_reg_pw2 = st.text_input("Confirm Password", type="password", key="top_reg_pw2")
            st.markdown("""
            <div style="color:var(--text-secondary);font-size:0.82rem;margin:8px 0;line-height:1.6;">
                <div style="display:flex;gap:24px;flex-wrap:wrap;">
                    <div>
                        <strong style="color:var(--accent-cyan);">🆓 Free Tier</strong><br>
                        3 AI analysis prompts to explore the platform
                    </div>
                    <div>
                        <strong style="color:var(--accent-green);">💎 Paid Tier — A$15/month</strong><br>
                        Unlimited prompts • Priority AI processing • Advanced agents
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col_submit, col_cancel = st.columns([3, 1])
            with col_submit:
                submitted = st.form_submit_button("Create Free Account", use_container_width=True, type="primary")
            with col_cancel:
                cancelled = st.form_submit_button("✕ Close", use_container_width=True)
            if cancelled:
                st.session_state.pop("landing_tab", None)
                st.rerun()
            if submitted:
                if not top_reg_name or not top_reg_email or not top_reg_pw:
                    st.error("Please fill in all fields")
                elif top_reg_pw != top_reg_pw2:
                    st.error("Passwords do not match")
                elif len(top_reg_pw) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    result = _api_register(top_reg_email, top_reg_name, top_reg_pw)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.auth_token = result["access_token"]
                        st.session_state.auth_user = result["user"]
                        st.session_state.pop("landing_tab", None)
                        st.success("Welcome to TradingEdge! You have 3 free analysis prompts.")
                        st.rerun()

    # ===== HERO SECTION =====
    st.markdown("""
    <div class="hero-section">
        <div class="hero-brand">
            <span class="hero-logo">🦘</span>
            <div>
                <div class="hero-brand-text">TradingEdge Australia</div>
                <div class="hero-brand-sub">AI-Powered Trading Advisory</div>
            </div>
        </div>
        <h1 class="hero-title">
            Smarter Trading Decisions with<br>
            <span>Multi-Agent AI Intelligence</span>
        </h1>
        <p class="hero-subtitle">
            Australia's premier AI trading advisory platform. Get institutional-grade analysis powered by
            15+ specialised AI agents — covering ASX, US, and global markets. Not a broker.
            Pure intelligence to help you trade smarter.
        </p>
        <div class="hero-badges">
            <span class="hero-badge">🤖 15+ AI Agents</span>
            <span class="hero-badge">🇦🇺 ASX & Global Markets</span>
            <span class="hero-badge">📊 Real-Time Analysis</span>
            <span class="hero-badge">🔗 12+ Broker Integrations</span>
            <span class="hero-badge">🛡️ Risk Management</span>
            <span class="hero-badge">📰 News Sentiment AI</span>
        </div>
        <div class="hero-disclaimer">
            ⚠️ <strong>Important:</strong> TradingEdge Australia is a trading advisory and analysis platform — not a broker,
            dealer, or financial intermediary. We do not execute trades, hold funds, or provide personal financial advice.
            All analysis is AI-generated and for informational purposes only. Always consult a licensed financial adviser
            (AFSL holder) before making investment decisions. Past performance is not indicative of future results.
            Trading involves risk of loss. ASIC regulated advisory standards apply.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ===== STATS BAR =====
    st.markdown("""
    <div class="stat-bar">
        <div class="stat-item">
            <div class="stat-number">15+</div>
            <div class="stat-label">AI Agents</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">50+</div>
            <div class="stat-label">Markets Covered</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">12</div>
            <div class="stat-label">AU Broker Links</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">24/7</div>
            <div class="stat-label">AI Analysis</div>
        </div>
        <div class="stat-item">
            <div class="stat-number">&lt;30s</div>
            <div class="stat-label">Deep Analysis</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ===== FEATURE CARDS =====
    st.markdown("""
    <div class="feature-grid">
        <div class="feature-card">
            <span class="feature-icon">🧠</span>
            <div class="feature-title">Multi-Agent AI Engine</div>
            <div class="feature-desc">
                15+ specialised AI agents work together — market analysis, sentiment detection,
                risk assessment, technical strategy, and portfolio optimisation.
                Like having a team of analysts at your fingertips.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🌏</span>
            <div class="feature-title">ASX & Global Markets</div>
            <div class="feature-desc">
                Deep coverage of ASX top 200, US markets (NYSE/NASDAQ), and global exchanges.
                Analyse BHP, CBA, CSL alongside AAPL, TSLA, and NVDA — all in one place.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🏦</span>
            <div class="feature-title">Broker Integration Hub</div>
            <div class="feature-desc">
                Seamlessly connect with 12+ Australian brokers — CommSec, CMC, IG, Stake,
                SelfWealth & more. Get your advisory here, execute trades where you're comfortable.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">📊</span>
            <div class="feature-title">Technical & Fundamental</div>
            <div class="feature-desc">
                Advanced technical indicators (RSI, MACD, Bollinger Bands, MA crossovers)
                combined with fundamental data — P/E, EPS, market cap, dividend yields.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">🛡️</span>
            <div class="feature-title">Risk Intelligence</div>
            <div class="feature-desc">
                AI-powered risk scoring, volatility modelling, correlation analysis, and
                portfolio stress testing. Know your exposure before you commit.
            </div>
        </div>
        <div class="feature-card">
            <span class="feature-icon">📰</span>
            <div class="feature-title">News & Sentiment AI</div>
            <div class="feature-desc">
                Real-time news aggregation with AI sentiment analysis. Understand market mood,
                detect catalysts, and spot risks from 100+ news sources.
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ===== HOW IT WORKS =====
    st.markdown("""
    <div class="main-header" style="text-align:center;">
        <h1>How TradingEdge Works</h1>
        <p style="max-width:600px;margin:8px auto 0 auto;">Three simple steps to institutional-grade trading intelligence</p>
    </div>
    """, unsafe_allow_html=True)

    step_cols = st.columns(3)
    steps = [
        ("1️⃣", "Ask in Plain English",
         "Type any query — 'Analyse CBA', 'Compare BHP vs RIO', 'Global market outlook'. Our AI understands natural language."),
        ("2️⃣", "AI Agents Analyse",
         "15+ specialised agents process market data, news, technicals, risk factors — delivering a comprehensive advisory report."),
        ("3️⃣", "Execute via Your Broker",
         "Review the AI advisory, then execute through your preferred Australian broker. We link you directly — no middleman."),
    ]
    for col, (icon, title, desc) in zip(step_cols, steps):
        col.markdown(f"""
        <div class="metric-card" style="text-align:center;padding:24px 16px;">
            <div style="font-size:2.2rem;margin-bottom:8px;">{icon}</div>
            <div style="color:var(--text-primary);font-weight:700;font-size:0.95rem;margin-bottom:6px;">{title}</div>
            <div style="color:var(--text-secondary);font-size:0.82rem;line-height:1.5;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== SAMPLE BROKERS PREVIEW =====
    st.markdown("""
    <div class="main-header" style="text-align:center;">
        <h1>🏦 Trade Through Australia's Best Brokers</h1>
        <p>We provide the intelligence — execute trades where you're comfortable</p>
    </div>
    """, unsafe_allow_html=True)

    preview_brokers = ["CommSec", "CMC Markets", "IG Markets", "Stake", "SelfWealth", "Interactive Brokers"]
    broker_html = '<div class="broker-grid">'
    for bname in preview_brokers:
        info = AUSTRALIAN_BROKERS[bname]
        markets_html = "".join(f'<span class="broker-market-tag">{m}</span>' for m in info["markets"][:4])
        broker_html += f"""
        <div class="broker-card">
            <div class="broker-header">
                <span class="broker-icon">{info['icon']}</span>
                <span class="broker-name">{bname}</span>
                <span class="broker-type">{info['type']}</span>
            </div>
            <div class="broker-desc">{info['desc']}</div>
            <div class="broker-markets">{markets_html}</div>
        </div>
        """
    broker_html += "</div>"
    st.markdown(broker_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ===== LOGIN / REGISTER =====
    st.markdown("""
    <div class="main-header" style="text-align:center;">
        <h1>🚀 Get Started — Free</h1>
        <p>Create your account and get 3 free AI analysis prompts</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email", placeholder="you@example.com")
            password = st.text_input("Password", type="password", key="login_pw")
            submitted = st.form_submit_button("Sign In to TradingEdge", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.error("Please fill in all fields")
                else:
                    result = _api_login(email, password)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.auth_token = result["access_token"]
                        st.session_state.auth_user = result["user"]
                        st.rerun()

    with tab_register:
        with st.form("register_form"):
            reg_name = st.text_input("Full Name", key="reg_name", placeholder="John Smith")
            reg_email = st.text_input("Email", key="reg_email", placeholder="you@example.com")
            reg_pw = st.text_input("Password", type="password", key="reg_pw")
            reg_pw2 = st.text_input("Confirm Password", type="password", key="reg_pw2")
            st.markdown("""
            <div style="color:var(--text-secondary);font-size:0.82rem;margin:8px 0;line-height:1.6;">
                <div style="display:flex;gap:24px;flex-wrap:wrap;">
                    <div>
                        <strong style="color:var(--accent-cyan);">🆓 Free Tier</strong><br>
                        3 AI analysis prompts to explore the platform
                    </div>
                    <div>
                        <strong style="color:var(--accent-green);">💎 Paid Tier — A$15/month</strong><br>
                        Unlimited prompts • Priority AI processing • Advanced agents
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            submitted = st.form_submit_button("Create Free Account", use_container_width=True)
            if submitted:
                if not reg_name or not reg_email or not reg_pw:
                    st.error("Please fill in all fields")
                elif reg_pw != reg_pw2:
                    st.error("Passwords do not match")
                elif len(reg_pw) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    result = _api_register(reg_email, reg_name, reg_pw)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.session_state.auth_token = result["access_token"]
                        st.session_state.auth_user = result["user"]
                        st.success("Welcome to TradingEdge! You have 3 free analysis prompts.")
                        st.rerun()

    # ===== FOOTER =====
    st.markdown("""
    <div style="text-align:center;margin-top:40px;padding:24px 0;border-top:1px solid rgba(255,255,255,0.05);">
        <div style="color:var(--text-muted);font-size:0.75rem;line-height:1.6;max-width:700px;margin:0 auto;">
            <strong>TradingEdge Australia</strong> — AI-Powered Trading Advisory Platform<br>
            ABN: XX XXX XXX XXX | Not a broker or dealer. Advisory service only.<br>
            All AI-generated analysis is for informational purposes only and does not constitute financial advice.<br>
            © 2026 TradingEdge Australia. All rights reserved. 🇦🇺
        </div>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# If not authenticated, show landing page
# ---------------------------------------------------------------------------
if not st.session_state.auth_token:
    _render_landing_page()
    st.stop()

# Refresh user profile from API (gets up-to-date prompt_count / balance)
_refreshed = _api_get_profile()
if _refreshed:
    st.session_state.auth_user = _refreshed
user = st.session_state.auth_user

# ---------------------------------------------------------------------------
# Sidebar (authenticated)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div style="text-align:center;padding:10px 0 16px 0">
        <div style="font-size:2rem;margin-bottom:4px;">🦘</div>
        <h2 style="color:var(--text-primary);margin:0;font-size:1.1rem;font-weight:800;">TradingEdge Australia</h2>
        <p style="color:var(--accent-cyan);font-size:0.7rem;margin:2px 0 0 0;font-weight:600;letter-spacing:1px;">AI TRADING ADVISORY</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # ── User info ──
    tier_label = "💎 PAID" if user["tier"] == "paid" else "🆓 FREE"
    st.markdown(f"""
    <div class="metric-card" style="margin-bottom:12px">
        <div class="metric-label">Signed In As</div>
        <div class="metric-value metric-blue" style="font-size:1rem">{user['name']}</div>
        <div class="metric-sub">{user['email']}<br>{tier_label} • {user['prompt_count']} prompts used</div>
    </div>
    """, unsafe_allow_html=True)

    if user["tier"] == "free":
        remaining = max(0, 3 - user["prompt_count"])
        bar_pct = min(100, (user["prompt_count"] / 3) * 100)
        bar_color = "var(--accent-green)" if remaining > 1 else ("var(--accent-yellow)" if remaining == 1 else "var(--accent-red)")
        st.markdown(f"""
        <div style="margin-bottom:12px">
            <div style="color:var(--text-muted);font-size:0.72rem;margin-bottom:4px">Free Prompts: {remaining}/3 remaining</div>
            <div class="risk-bar-bg"><div class="risk-bar" style="width:{bar_pct}%;background:{bar_color}"></div></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:12px">
            <div class="metric-label">Balance (AUD)</div>
            <div class="metric-value {'metric-green' if user['balance_usd'] > 2 else 'metric-red'}">A${user['balance_usd']:.4f}</div>
            <div class="metric-sub">of A$15.00 subscription</div>
        </div>
        """, unsafe_allow_html=True)

    # Navigation buttons
    nav_cols = st.columns(3)
    if nav_cols[0].button("📊 Advisory", use_container_width=True,
                          help="AI Trading Advisory"):
        st.session_state.active_page = "dashboard"
        st.session_state.show_admin = False
        st.session_state.show_brokers = False
        st.rerun()
    if nav_cols[1].button("🏦 Brokers", use_container_width=True,
                          help="Australian Broker Hub"):
        st.session_state.active_page = "brokers"
        st.session_state.show_admin = False
        st.session_state.show_brokers = True
        st.rerun()

    btn_cols_extra = []
    if user["role"] == "admin":
        if nav_cols[2].button("🔧 Admin", use_container_width=True):
            st.session_state.show_admin = not st.session_state.show_admin
            st.session_state.show_brokers = False
            st.session_state.active_page = "admin"
            st.rerun()
    else:
        if nav_cols[2].button("🚪 Logout", use_container_width=True):
            st.session_state.auth_token = None
            st.session_state.auth_user = None
            st.session_state.messages = []
            st.session_state.show_admin = False
            st.session_state.show_brokers = False
            st.session_state.active_page = "dashboard"
            st.rerun()

    if user["role"] == "admin":
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.auth_token = None
            st.session_state.auth_user = None
            st.session_state.messages = []
            st.session_state.show_admin = False
            st.session_state.show_brokers = False
            st.session_state.active_page = "dashboard"
            st.rerun()

    st.divider()

    # ===== ASX Quick Analyse =====
    st.markdown("### 🇦🇺 ASX Quick Analyse")
    asx_cols = st.columns(5)
    for idx, sym in enumerate(ASX_TOP_STOCKS[:10]):
        if asx_cols[idx % 5].button(sym, key=f"asx_{sym}", use_container_width=True):
            st.session_state["quick_input"] = f"Analyze {sym}.AX"
            st.session_state.show_admin = False
            st.session_state.show_brokers = False
            st.session_state.active_page = "dashboard"

    st.divider()

    st.markdown("### 🇺🇸 US Quick Analyse")
    us_cols = st.columns(4)
    for idx, sym in enumerate(US_TOP_STOCKS):
        if us_cols[idx % 4].button(sym, key=f"us_{sym}", use_container_width=True):
            st.session_state["quick_input"] = f"Analyze {sym}"
            st.session_state.show_admin = False
            st.session_state.show_brokers = False
            st.session_state.active_page = "dashboard"

    st.divider()

    # ── Session Cost Tracker ──
    st.markdown("### 💰 Session Costs (AUD)")
    sc = st.session_state.session_cost
    if sc["prompt_count"] > 0:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:8px">
            <div class="metric-label">Total Spent</div>
            <div class="metric-value metric-yellow">A${sc['total_cost_usd']:.4f}</div>
            <div class="metric-sub">{sc['prompt_count']} prompt{'s' if sc['prompt_count'] > 1 else ''} • {sc['total_llm_calls']} LLM calls</div>
        </div>
        """, unsafe_allow_html=True)
        col_in, col_out = st.columns(2)
        col_in.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Input Tokens</div>
            <div class="metric-value metric-blue">{sc['total_prompt_tokens']:,}</div>
        </div>
        """, unsafe_allow_html=True)
        col_out.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Output Tokens</div>
            <div class="metric-value metric-green">{sc['total_completion_tokens']:,}</div>
        </div>
        """, unsafe_allow_html=True)
        avg_cost = sc['total_cost_usd'] / sc['prompt_count']
        st.markdown(f"""
        <div style="text-align:center;color:#7a8fa6;font-size:0.72rem;margin-top:4px">
            Avg: ${avg_cost:.4f}/prompt • {sc['total_tokens']:,} total tokens
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#4b5563;font-size:0.8rem">No prompts yet</div>', unsafe_allow_html=True)

    st.divider()

    st.markdown("### 📡 System Status")
    _health_ok = False
    _health_data = {}
    try:
        with httpx.Client(timeout=20) as client:
            health = client.get(f"{API_BASE}/health", headers=_bypass_headers()).json()
        _health_data = health
        _health_ok = True
        llm_ok = health.get("llm_ready", False)
        news_ok = health.get("news_ready", False)
        st.success(f"API Online • Memory: {health.get('vector_store_count', 0)} entries")
        if not llm_ok:
            st.warning("⚠️ LLM not configured — OPENAI_API_KEY missing on backend")
        if not news_ok:
            st.warning("⚠️ News API not configured — NEWS_API_KEY missing on backend")
    except Exception:
        pass
    if not _health_ok:
        st.error("API Offline — check Vercel deployment")

    st.divider()
    st.markdown("### 📜 Recent History")
    if st.button("Load History", use_container_width=True):
        try:
            with httpx.Client(timeout=10) as client:
                hist = client.get(f"{API_BASE}/history", params={"limit": 10}, headers=_auth_headers()).json()
            for rec in hist.get("records", []):
                action = rec.get("action", "HOLD")
                icon = {"BUY": "🟢", "SELL": "🔴"}.get(action, "🟡")
                st.markdown(
                    f"{icon} **{rec['symbol']}** → {action} "
                    f"({rec.get('confidence', 0):.0%}) — {rec.get('created_at', '')[:16]}"
                )
        except Exception:
            st.warning("Could not load history.")

    st.divider()
    st.markdown(
        '<p style="color:var(--text-muted);font-size:0.68rem;text-align:center;line-height:1.5;">'
        '🦘 TradingEdge Australia<br>'
        'AI Advisory Platform — Not a Broker<br>'
        'Powered by OpenAI • yfinance • NewsAPI<br>'
        'Multi-Agent Architecture • ASIC Compliant</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main area — Admin, Brokers, or Advisory Dashboard
# ---------------------------------------------------------------------------
if st.session_state.show_admin and user["role"] == "admin":
    _render_admin_panel()
elif st.session_state.show_brokers:
    _render_broker_panel()
else:
    # ---------------------------------------------------------------------------
    # Main area — AI Advisory Chat + Dashboard hybrid
    # ---------------------------------------------------------------------------

    # Advisory disclaimer banner
    st.markdown("""
    <div class="advisory-bar">
        <span class="advisory-bar-icon">⚠️</span>
        <span class="advisory-bar-text">
            <strong>Advisory Only:</strong> TradingEdge provides AI-generated analysis for informational purposes.
            This is not financial advice. Always consult a licensed adviser (AFSL) before making investment decisions.
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="main-header">
        <h1>🧠 AI Trading Advisory</h1>
        <p>Ask me anything — ASX & global stocks, analysis, news, comparisons, or market outlook. Powered by 15+ AI agents.</p>
    </div>
    """, unsafe_allow_html=True)

    # Display prior chat messages (compact)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                st.markdown(msg.get("summary", msg["content"]))

    # Check for quick-button input
    quick = st.session_state.pop("quick_input", None)
    prompt = st.chat_input("Ask anything — e.g. 'Analyse CBA', 'Compare BHP vs RIO', 'AAPL outlook', 'ASX market sentiment'") or quick

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            resp_type_label = "🤖 Thinking..."
            with st.spinner(resp_type_label):
                response = _call_api(prompt)

            if "error" in response:
                content = f"⚠️ **Error:** {response['error']}"
                st.markdown(content)
                st.session_state.messages.append({"role": "assistant", "content": content, "summary": content})
            else:
                answer = response.get("answer", "")
                resp_type = response.get("type", "unknown")
                elapsed = response.get("elapsed_seconds", 0)

                # Always show the text answer
                if answer:
                    st.markdown(answer)

                # Show cost + timing info
                token_usage = response.get("token_usage", {})
                prompt_cost = token_usage.get("cost_usd", 0)
                total_tok = token_usage.get("total_tokens", 0)
                llm_calls = token_usage.get("llm_calls", 0)

                # Update session totals
                if token_usage:
                    sc = st.session_state.session_cost
                    sc["total_cost_usd"] += prompt_cost
                    sc["total_tokens"] += total_tok
                    sc["total_prompt_tokens"] += token_usage.get("prompt_tokens", 0)
                    sc["total_completion_tokens"] += token_usage.get("completion_tokens", 0)
                    sc["total_llm_calls"] += llm_calls
                    sc["prompt_count"] += 1

                # Inline cost caption
                cost_parts = []
                if elapsed:
                    cost_parts.append(f"⏱️ {elapsed:.1f}s")
                cost_parts.append(resp_type.replace('_', ' ').title())
                if total_tok:
                    cost_parts.append(f"{total_tok:,} tokens")
                if llm_calls:
                    cost_parts.append(f"{llm_calls} LLM call{'s' if llm_calls > 1 else ''}")
                if prompt_cost:
                    cost_parts.append(f"${prompt_cost:.4f}")
                st.caption(" • ".join(cost_parts))

                # For full_analysis, also render the dashboard cards
                if resp_type == "full_analysis" and "analyses" in response:
                    st.session_state.last_results = response["analyses"]
                    summaries = []
                    for r in response["analyses"]:
                        _render_analysis(r)
                        action = r.get("decision", {}).get("action", "HOLD")
                        conf = r.get("decision", {}).get("confidence", 0)
                        sym = r.get("symbol", "?")
                        summaries.append(f"**{sym}**: {action} ({conf:.0%})")
                    summary_text = " | ".join(summaries)

                    # Show global macro overlay if available
                    if "global_macro" in response and response["global_macro"].get("global_regime") != "unknown":
                        _render_global_macro_card(response["global_macro"])

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": json.dumps(response["analyses"]),
                        "summary": f"📊 {summary_text}",
                    })

                # For global outlook, show macro dashboard
                elif resp_type == "global_outlook" and "global_macro" in response:
                    _render_global_macro_card(response["global_macro"])

                    # Also show any referenced stock cards
                    for md in response.get("market_data", []):
                        if isinstance(md, dict) and "price" in md:
                            sym = md.get("symbol", "?")
                            change = md.get("price_change_pct", 0)
                            change_color = "metric-green" if change and change >= 0 else "metric-red"
                            cols = st.columns(5)
                            card_data = [
                                ("Price", f"${_fmt_number(md.get('price'))}", change_color),
                                ("Change", _fmt_pct(change), change_color),
                                ("RSI", _fmt_number(md.get('rsi'), 1), "metric-yellow" if md.get('rsi') and (md['rsi'] > 70 or md['rsi'] < 30) else "metric-white"),
                                ("Trend", md.get('trend', 'N/A').replace('_', ' ').title(), "metric-blue"),
                                ("Market Cap", md.get('market_cap_formatted', 'N/A'), "metric-white"),
                            ]
                            for col, (label, value, color) in zip(cols, card_data):
                                col.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">{label}</div>
                                    <div class="metric-value {color}">{value}</div>
                                </div>
                                """, unsafe_allow_html=True)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "summary": f"🌍 {answer[:200]}" if answer else "Global outlook",
                    })

                # For quick_status with market data, show compact cards
                elif resp_type in ("quick_status", "comparison") and "market_data" in response:
                    for md in response["market_data"]:
                        if isinstance(md, dict) and "price" in md:
                            sym = md.get("symbol", "?")
                            change = md.get("price_change_pct", 0)
                            change_color = "metric-green" if change and change >= 0 else "metric-red"
                            cols = st.columns(5)
                            card_data = [
                                ("Price", f"${_fmt_number(md.get('price'))}", change_color),
                                ("Change", _fmt_pct(change), change_color),
                                ("RSI", _fmt_number(md.get('rsi'), 1), "metric-yellow" if md.get('rsi') and (md['rsi'] > 70 or md['rsi'] < 30) else "metric-white"),
                                ("Trend", md.get('trend', 'N/A').replace('_', ' ').title(), "metric-blue"),
                                ("Market Cap", md.get('market_cap_formatted', 'N/A'), "metric-white"),
                            ]
                            for col, (label, value, color) in zip(cols, card_data):
                                col.markdown(f"""
                                <div class="metric-card">
                                    <div class="metric-label">{label}</div>
                                    <div class="metric-value {color}">{value}</div>
                                </div>
                                """, unsafe_allow_html=True)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "summary": f"📊 {answer[:200]}" if answer else "Quick status",
                    })

                # For news queries, show article cards
                elif resp_type == "news_query" and "articles" in response:
                    for a in response.get("articles", [])[:8]:
                        title = a.get("title", "Untitled")
                        desc = (a.get("description") or "")[:200]
                        source = a.get("source", "Unknown")
                        url = a.get("url", "")
                        title_display = f'<a href="{url}" target="_blank" style="color:#60a5fa;text-decoration:none">{title}</a>' if url else title
                        st.markdown(f"""
                        <div class="news-item">
                            <h5>{title_display}</h5>
                            <p>{desc}</p>
                            <div class="news-meta">{source}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "summary": f"📰 {answer[:200]}" if answer else "News summary",
                    })

                else:
                    # General question or fallback
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "summary": f"💬 {answer[:200]}" if answer else "Response",
                    })
