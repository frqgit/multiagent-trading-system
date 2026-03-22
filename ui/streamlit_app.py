"""Streamlit UI — Professional AI Trading Dashboard."""

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

st.set_page_config(
    page_title="AI Multi-Agent Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Professional Dark Theme
# ---------------------------------------------------------------------------
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp { background-color: #0a0e17; font-family: 'Inter', sans-serif; }

    .main-header {
        background: linear-gradient(135deg, #0f1923 0%, #1a2332 100%);
        border: 1px solid #1e2d3d;
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 20px;
    }
    .main-header h1 { color: #e1e8f0; margin: 0; font-size: 1.6rem; font-weight: 700; }
    .main-header p { color: #7a8fa6; margin: 4px 0 0 0; font-size: 0.85rem; }

    .metric-card {
        background: linear-gradient(135deg, #111827 0%, #151f2e 100%);
        border: 1px solid #1e2d3d;
        border-radius: 10px;
        padding: 16px 18px;
        text-align: center;
    }
    .metric-label { color: #7a8fa6; font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
    .metric-value { font-size: 1.4rem; font-weight: 700; margin-top: 4px; }
    .metric-sub { color: #7a8fa6; font-size: 0.75rem; margin-top: 2px; }
    .metric-green { color: #00d26a; }
    .metric-red { color: #ff4757; }
    .metric-yellow { color: #ffa502; }
    .metric-blue { color: #3b82f6; }
    .metric-white { color: #e1e8f0; }

    .decision-badge {
        display: inline-block;
        padding: 6px 20px;
        border-radius: 6px;
        font-size: 1.1rem;
        font-weight: 700;
        letter-spacing: 1px;
    }
    .badge-buy { background: rgba(0,210,106,0.15); color: #00d26a; border: 1px solid #00d26a; }
    .badge-sell { background: rgba(255,71,87,0.15); color: #ff4757; border: 1px solid #ff4757; }
    .badge-hold { background: rgba(255,165,2,0.15); color: #ffa502; border: 1px solid #ffa502; }

    .agent-panel {
        background: #111827;
        border: 1px solid #1e2d3d;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .agent-panel h4 { color: #e1e8f0; margin: 0 0 8px 0; font-size: 0.9rem; font-weight: 600; }
    .agent-panel p { color: #9ca3af; font-size: 0.82rem; line-height: 1.5; margin: 0; word-wrap: break-word; overflow-wrap: break-word; }

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
        background: rgba(255,165,2,0.12);
        color: #ffa502;
        border-color: rgba(255,165,2,0.25);
    }
    .signal-tag-bad {
        background: rgba(255,71,87,0.12);
        color: #ff4757;
        border-color: rgba(255,71,87,0.25);
    }

    .news-item {
        background: #111827;
        border: 1px solid #1e2d3d;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 8px;
    }
    .news-item h5 { color: #e1e8f0; margin: 0 0 4px 0; font-size: 0.82rem; font-weight: 500; }
    .news-item p { color: #7a8fa6; font-size: 0.75rem; margin: 0; line-height: 1.4; word-wrap: break-word; }
    .news-meta { color: #4b5563; font-size: 0.68rem; margin-top: 4px; }

    .risk-bar-bg { background: #1e2d3d; border-radius: 4px; height: 8px; width: 100%; }
    .risk-bar { border-radius: 4px; height: 8px; transition: width 0.3s; }

    .section-title { color: #9ca3af; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin: 18px 0 10px 0; }

    div[data-testid="stSidebar"] { background: #0f1520; }
    div[data-testid="stSidebar"] .stMarkdown h1,
    div[data-testid="stSidebar"] .stMarkdown h2,
    div[data-testid="stSidebar"] .stMarkdown h3 { color: #e1e8f0; }

    /* ===== MOBILE RESPONSIVE ===== */
    @media (max-width: 768px) {
        .main-header { padding: 14px 16px; margin-bottom: 12px; border-radius: 8px; }
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

        /* Streamlit overrides for mobile */
        section[data-testid="stSidebar"] { min-width: 260px !important; max-width: 280px !important; }
        .stChatInput textarea { font-size: 16px !important; }
        .stButton > button { min-height: 44px; font-size: 0.85rem; }
        div[data-testid="column"] { padding-left: 4px !important; padding-right: 4px !important; }
        .block-container { padding-left: 1rem !important; padding-right: 1rem !important; padding-top: 1rem !important; }
    }

    @media (max-width: 480px) {
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
        with httpx.Client(timeout=15) as client:
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
        with httpx.Client(timeout=15) as client:
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
        with httpx.Client(timeout=10) as client:
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
        return {"error": "Cannot connect to API server. Ensure it's running."}
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", str(exc))
        except Exception:
            detail = str(exc)
        return {"error": detail}
    except Exception as exc:
        return {"error": str(exc)}


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
def _render_auth_screen():
    st.markdown("""
    <div class="main-header" style="text-align:center">
        <h1>📊 AI Multi-Agent Trading System</h1>
        <p>Sign in or create an account to get started</p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔑 Login", "📝 Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pw")
            submitted = st.form_submit_button("Login", use_container_width=True)
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
            reg_name = st.text_input("Full Name", key="reg_name")
            reg_email = st.text_input("Email", key="reg_email")
            reg_pw = st.text_input("Password", type="password", key="reg_pw")
            reg_pw2 = st.text_input("Confirm Password", type="password", key="reg_pw2")
            st.markdown("""
            <div style="color:#7a8fa6;font-size:0.8rem;margin:8px 0">
                <b>Free tier:</b> 3 prompts for testing<br>
                <b>Paid tier:</b> $10/month — token costs deducted from balance
            </div>
            """, unsafe_allow_html=True)
            submitted = st.form_submit_button("Create Account", use_container_width=True)
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
                        st.success("Account created! You have 3 free prompts.")
                        st.rerun()


# ---------------------------------------------------------------------------
# If not authenticated, show login screen
# ---------------------------------------------------------------------------
if not st.session_state.auth_token:
    _render_auth_screen()
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
    <div style="text-align:center;padding:10px 0 20px 0">
        <h2 style="color:#e1e8f0;margin:0">📊 AI Trading Agent</h2>
        <p style="color:#7a8fa6;font-size:0.8rem;margin:4px 0 0 0">Multi-Agent Investment Intelligence</p>
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
        bar_color = "#00d26a" if remaining > 1 else ("#ffa502" if remaining == 1 else "#ff4757")
        st.markdown(f"""
        <div style="margin-bottom:12px">
            <div style="color:#7a8fa6;font-size:0.72rem;margin-bottom:4px">Free Prompts: {remaining}/3 remaining</div>
            <div class="risk-bar-bg"><div class="risk-bar" style="width:{bar_pct}%;background:{bar_color}"></div></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:12px">
            <div class="metric-label">Balance</div>
            <div class="metric-value {'metric-green' if user['balance_usd'] > 2 else 'metric-red'}">${user['balance_usd']:.4f}</div>
            <div class="metric-sub">of $10.00 subscription</div>
        </div>
        """, unsafe_allow_html=True)

    # Admin + Logout buttons
    btn_cols = st.columns(2 if user["role"] == "admin" else 1)
    if user["role"] == "admin":
        if btn_cols[0].button("🔧 Admin", use_container_width=True):
            st.session_state.show_admin = not st.session_state.show_admin
            st.rerun()
    logout_col = btn_cols[-1] if user["role"] == "admin" else btn_cols[0]
    if logout_col.button("🚪 Logout", use_container_width=True):
        st.session_state.auth_token = None
        st.session_state.auth_user = None
        st.session_state.messages = []
        st.session_state.show_admin = False
        st.rerun()

    st.divider()

    st.markdown("### ⚡ Quick Analyze")
    quick_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META", "AMD"]
    cols = st.columns(4)
    for idx, sym in enumerate(quick_symbols):
        if cols[idx % 4].button(sym, key=f"quick_{sym}", use_container_width=True):
            st.session_state["quick_input"] = f"Analyze {sym}"
            st.session_state.show_admin = False

    st.divider()

    # ── Session Cost Tracker ──
    st.markdown("### 💰 Session Costs")
    sc = st.session_state.session_cost
    if sc["prompt_count"] > 0:
        st.markdown(f"""
        <div class="metric-card" style="margin-bottom:8px">
            <div class="metric-label">Total Spent</div>
            <div class="metric-value metric-yellow">${sc['total_cost_usd']:.4f}</div>
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
    for _attempt in range(3):
        try:
            with httpx.Client(timeout=5) as client:
                health = client.get(f"{API_BASE}/health", headers=_bypass_headers()).json()
            st.success(f"API Online • Memory: {health.get('vector_store_count', 0)} entries")
            _health_ok = True
            break
        except Exception:
            import time as _time
            _time.sleep(1)
    if not _health_ok:
        st.error("API Offline")

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
        '<p style="color:#4b5563;font-size:0.7rem;text-align:center">'
        'Powered by OpenAI • yfinance • NewsAPI<br>Multi-Agent Architecture</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main area — Admin or Chat
# ---------------------------------------------------------------------------
if st.session_state.show_admin and user["role"] == "admin":
    _render_admin_panel()
else:
    # ---------------------------------------------------------------------------
    # Main area — Chat + Dashboard hybrid
    # ---------------------------------------------------------------------------
    st.markdown("""
    <div class="main-header">
        <h1>💬 AI Trading Assistant</h1>
        <p>Ask me anything — stock prices, analysis, news, comparisons, or general market questions</p>
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
    prompt = st.chat_input("Ask anything — e.g. 'CBA stock price', 'Compare AAPL vs MSFT', 'Analyze TSLA'") or quick

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
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": json.dumps(response["analyses"]),
                        "summary": f"📊 {summary_text}",
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
