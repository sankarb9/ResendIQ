"""Shared look-and-feel helpers for every ResendIQ page (CSS, cards, pills, chart theme)."""
from __future__ import annotations

import html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ACCENT = "#2dd4bf"
EVENT_COLORS = {
    "DATA_SENT": "#60a5fa", "DATA_RECEIVED": "#2dd4bf", "ACK_RECEIVED": "#34d399",
    "RETRANSMISSION": "#fbbf24", "TIMEOUT": "#fb923c", "DATA_LOST": "#f87171",
    "ACK_LOST": "#e879f9", "DUPLICATE_SUPPRESSED": "#94a3b8",
    "OUT_OF_ORDER_DISCARDED": "#a78bfa", "RETRY_LIMIT": "#ef4444",
}
PROTOCOL_COLORS = {"Stop-and-Wait": "#60a5fa", "Go-Back-N": "#fbbf24", "Selective Repeat": "#2dd4bf",
                   "Selective-Repeat": "#2dd4bf"}

_CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1250px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.riq-hero {padding: 1.6rem 1.8rem; border-radius: 18px; margin-bottom: 1.2rem;
  background: radial-gradient(1200px 300px at 0% 0%, rgba(45,212,191,.18), transparent 60%),
              linear-gradient(135deg, #121b2e, #0f172a); border: 1px solid #1f2b45;}
.riq-hero h1 {margin: 0 0 .3rem 0; font-size: 2.1rem;}
.riq-hero p {margin: 0; color: #9fb0cc; font-size: 1.02rem;}
.riq-card {background: #121b2e; border: 1px solid #1f2b45; border-radius: 14px; padding: 1rem 1.1rem; height: 100%;}
.riq-card h4 {margin: 0 0 .35rem 0; font-size: 1.02rem;}
.riq-card p {margin: 0; color: #9fb0cc; font-size: .92rem; line-height: 1.45;}
.riq-kpi {background: #121b2e; border: 1px solid #1f2b45; border-radius: 14px; padding: .85rem 1rem;}
.riq-kpi .l {color: #8a9bb8; font-size: .76rem; text-transform: uppercase; letter-spacing: .06em;}
.riq-kpi .v {font-size: 1.6rem; font-weight: 650; line-height: 1.25;}
.riq-kpi .s {color: #8a9bb8; font-size: .78rem;}
.riq-pill {display: inline-block; padding: .18rem .65rem; border-radius: 999px; font-size: .8rem; font-weight: 600;
  border: 1px solid currentColor;}
.riq-step {display: flex; gap: .7rem; align-items: flex-start; margin: .35rem 0;}
.riq-step .n {min-width: 1.7rem; height: 1.7rem; border-radius: 50%; background: #2dd4bf22; color: #2dd4bf;
  display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: .85rem;}
.riq-term {background: #05080f; border: 1px solid #1f2b45; border-radius: 12px; padding: .8rem 1rem; height: 420px;
  overflow-y: auto; display: flex; flex-direction: column-reverse; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: .82rem; line-height: 1.5;}
.riq-term .rx {color: #2dd4bf;} .riq-term .tx {color: #60a5fa;}
.riq-term .bad {color: #f87171;} .riq-term .warn {color: #fbbf24;} .riq-term .ok {color: #34d399;}
.riq-term .dim {color: #64748b;}
[data-testid="stMetric"] {background: #121b2e; border: 1px solid #1f2b45; border-radius: 14px; padding: .7rem .9rem;}
[data-testid="stSidebar"] {border-right: 1px solid #1f2b45;}
button[kind="primary"] {font-weight: 600;}
</style>
"""


def setup_charts() -> None:
    """One consistent Plotly look for every figure."""
    tpl = pio.templates["plotly_dark"].to_plotly_json()
    tpl["layout"].update(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                         font={"family": "Inter, system-ui, sans-serif", "color": "#cbd5e1"},
                         margin={"l": 40, "r": 20, "t": 50, "b": 40})
    pio.templates["resendiq"] = go.layout.Template(tpl)
    pio.templates.default = "resendiq"


def apply() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
    setup_charts()


def hero(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="riq-hero"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>',
                unsafe_allow_html=True)


def card(title: str, body: str) -> None:
    st.markdown(f'<div class="riq-card"><h4>{title}</h4><p>{body}</p></div>', unsafe_allow_html=True)


def kpi(label: str, value, sub: str = "", color: str | None = None) -> None:
    style = f' style="color:{color}"' if color else ""
    st.markdown(f'<div class="riq-kpi"><div class="l">{html.escape(label)}</div>'
                f'<div class="v"{style}>{html.escape(str(value))}</div><div class="s">{html.escape(sub)}</div></div>',
                unsafe_allow_html=True)


def pill(text: str, color: str) -> str:
    return f'<span class="riq-pill" style="color:{color}">{html.escape(text)}</span>'


def step(n: int, html_body: str) -> None:
    st.markdown(f'<div class="riq-step"><div class="n">{n}</div><div>{html_body}</div></div>', unsafe_allow_html=True)
