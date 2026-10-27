"""Premium dark styling, including the floating copilot drawer."""

from __future__ import annotations

import streamlit as st

PURPLE = "#8B5CF6"
BLUE = "#38BDF8"
MINT = "#34D399"
AMBER = "#FBBF24"
ROSE = "#FB7185"

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
  --sd-bg: #070914;
  --sd-panel: #0f1324;
  --sd-panel-2: #151a30;
  --sd-border: rgba(167, 139, 250, 0.17);
  --sd-purple: #8B5CF6;
  --sd-violet: #A78BFA;
  --sd-blue: #38BDF8;
  --sd-mint: #34D399;
  --sd-amber: #FBBF24;
  --sd-rose: #FB7185;
  --sd-text: #F4F5FF;
  --sd-muted: #9AA3C0;
}

html, body, [class*="css"], [data-testid="stAppViewContainer"] {
  font-family: 'Manrope', 'Segoe UI', sans-serif;
  color: var(--sd-text);
}

.stApp {
  background:
    radial-gradient(1100px 600px at 8% -8%, rgba(139, 92, 246, 0.16), transparent 62%),
    radial-gradient(900px 560px at 100% 0%, rgba(56, 189, 248, 0.10), transparent 60%),
    radial-gradient(800px 700px at 50% 115%, rgba(99, 102, 241, 0.09), transparent 62%),
    var(--sd-bg);
}

[data-testid="stHeader"] {
  background: transparent;
  pointer-events: none;
}

[data-testid="stHeader"] button,
[data-testid="stHeader"] a {
  pointer-events: auto;
}

/* Keep the collapsed-sidebar control usable. Hiding the whole toolbar also
   hides Streamlit's "Expand sidebar" button, which leaves the sidebar closed
   with no way back. Hide only the actions we do not need. */
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"] {
  visibility: hidden;
}

[data-testid="stExpandSidebarButton"] {
  visibility: visible !important;
  pointer-events: auto !important;
}

footer { visibility: hidden; }

[data-testid="stMain"] {
  transition: padding-right 220ms ease;
}

.block-container {
  padding-top: 2.2rem;
  padding-bottom: 6rem;
  max-width: 1280px;
}

h1, h2, h3, h4 {
  font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
  letter-spacing: -0.025em;
}

h1 { font-weight: 700; }
h2 { font-weight: 650; }

p, li, .stMarkdown {
  line-height: 1.62;
}

a { color: var(--sd-violet); }

/* Sidebar ------------------------------------------------------------- */
[data-testid="stSidebar"] {
  background:
    radial-gradient(420px 300px at 0% 0%, rgba(139, 92, 246, 0.13), transparent 70%),
    linear-gradient(180deg, #0b0e1d 0%, #080b17 100%);
  border-right: 1px solid rgba(167, 139, 250, 0.10);
}

[data-testid="stSidebar"] > div {
  background: transparent;
}

[data-testid="stSidebar"] .block-container {
  padding-top: 1.6rem;
}

.sd-brand {
  display: flex;
  align-items: center;
  gap: 0.72rem;
  padding: 0.1rem 0 0.9rem;
}

.sd-brand-mark {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  font-size: 1.25rem;
  background: linear-gradient(145deg, rgba(139, 92, 246, 0.95), rgba(56, 189, 248, 0.85));
  box-shadow: 0 10px 26px rgba(139, 92, 246, 0.32);
}

.sd-brand-name {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.02rem;
  font-weight: 700;
  line-height: 1.18;
  letter-spacing: -0.02em;
}

.sd-brand-sub {
  font-size: 0.66rem;
  color: var(--sd-muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-top: 0.2rem;
}

.sd-sidebar-status {
  margin: 0.4rem 0 0.2rem;
  padding: 0.8rem 0.9rem;
  border: 1px solid var(--sd-border);
  border-radius: 14px;
  background: rgba(21, 26, 48, 0.55);
  font-size: 0.73rem;
  color: var(--sd-muted);
}

.sd-status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 0.45rem;
  background: var(--sd-mint);
  box-shadow: 0 0 12px rgba(52, 211, 153, 0.7);
}

.sd-status-dot.local {
  background: var(--sd-amber);
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.55);
}

/* Sidebar navigation -------------------------------------------------- */
[data-testid="stSidebar"] [role="radiogroup"] {
  gap: 0.38rem;
}

[data-testid="stSidebar"] [role="radiogroup"] label {
  padding: 0.7rem 0.85rem;
  border-radius: 12px;
  border: 1px solid transparent;
  transition: all 160ms ease;
  cursor: pointer;
}

[data-testid="stSidebar"] [role="radiogroup"] label:hover {
  background: rgba(139, 92, 246, 0.10);
  border-color: rgba(167, 139, 250, 0.13);
}

[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: linear-gradient(90deg, rgba(139, 92, 246, 0.20), rgba(56, 189, 248, 0.07));
  border-color: rgba(167, 139, 250, 0.26);
  box-shadow: inset 2px 0 0 var(--sd-violet);
}

[data-testid="stSidebar"] [role="radiogroup"] label p {
  font-weight: 650;
  font-size: 0.88rem;
}

/* Headings and badges ------------------------------------------------- */
.sd-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--sd-violet);
  margin-bottom: 0.65rem;
}

.sd-eyebrow::before {
  content: '';
  width: 20px;
  height: 1px;
  background: linear-gradient(90deg, var(--sd-violet), transparent);
}

.sd-hero-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.9rem, 3.5vw, 3rem);
  line-height: 1.05;
  letter-spacing: -0.045em;
  font-weight: 700;
  margin: 0 0 0.65rem;
}

.sd-hero-sub {
  color: var(--sd-muted);
  max-width: 760px;
  font-size: 0.98rem;
  margin-bottom: 1.5rem;
}

.gradient-text {
  background: linear-gradient(95deg, #f4f1ff 10%, #c4b5fd 48%, #7dd3fc 95%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sd-section-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.08rem;
  font-weight: 650;
  letter-spacing: -0.02em;
  margin: 0.2rem 0 0.65rem;
}

.sd-muted { color: var(--sd-muted); }
.sd-small { font-size: 0.78rem; }

.sd-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(167, 139, 250, 0.22);
  background: rgba(139, 92, 246, 0.10);
  color: #DDD6FE;
  font-size: 0.7rem;
  font-weight: 650;
  line-height: 1.35;
}

.sd-pill.green {
  color: #A7F3D0;
  border-color: rgba(52, 211, 153, 0.26);
  background: rgba(52, 211, 153, 0.10);
}

.sd-pill.amber {
  color: #FDE68A;
  border-color: rgba(251, 191, 36, 0.26);
  background: rgba(251, 191, 36, 0.10);
}

.sd-pill.rose {
  color: #FECDD3;
  border-color: rgba(251, 113, 133, 0.26);
  background: rgba(251, 113, 133, 0.10);
}

.sd-pill.blue {
  color: #BAE6FD;
  border-color: rgba(56, 189, 248, 0.26);
  background: rgba(56, 189, 248, 0.10);
}

/* Metrics ------------------------------------------------------------- */
[data-testid="stMetric"] {
  background: linear-gradient(160deg, rgba(21, 26, 48, 0.84), rgba(15, 19, 36, 0.82));
  border: 1px solid var(--sd-border);
  border-radius: 18px;
  padding: 1rem 1.1rem;
  box-shadow: 0 14px 36px rgba(2, 4, 14, 0.22);
}

[data-testid="stMetricLabel"] p {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--sd-muted);
  font-weight: 650;
  line-height: 1.3;
}

[data-testid="stMetricLabel"] .stMarkdownEllipsis,
[data-testid="stMetricLabel"] p {
  min-width: 0;
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

[data-testid="stMetricValue"] {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.65rem;
  letter-spacing: -0.03em;
}

[data-testid="stMetricDelta"] {
  font-size: 0.74rem;
  align-items: flex-start;
}

[data-testid="stMetricDelta"] .stMarkdownEllipsis {
  min-width: 0;
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

[data-testid="stMetricDelta"] .stMarkdownEllipsis p {
  white-space: normal !important;
}

/* Buttons ------------------------------------------------------------- */
.stButton > button,
[data-testid="stFormSubmitButton"] > button,
.stDownloadButton > button {
  border-radius: 12px;
  border: 1px solid rgba(167, 139, 250, 0.22);
  background: rgba(21, 26, 48, 0.72);
  color: #EDE9FE;
  font-weight: 650;
  font-size: 0.84rem;
  transition: transform 150ms ease, border-color 150ms ease, background 150ms ease, box-shadow 150ms ease;
  min-height: 2.55rem;
}

.stButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover,
.stDownloadButton > button:hover {
  transform: translateY(-1px);
  border-color: rgba(167, 139, 250, 0.55);
  background: rgba(35, 40, 70, 0.9);
  color: #FFFFFF;
  box-shadow: 0 10px 24px rgba(3, 5, 18, 0.3);
}

.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] > button {
  background: linear-gradient(135deg, #7C3AED 0%, #6366F1 52%, #0EA5E9 100%);
  border: 1px solid rgba(196, 181, 253, 0.35);
  color: #FFFFFF;
  box-shadow: 0 10px 26px rgba(99, 102, 241, 0.28);
}

.stButton > button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] > button:hover {
  box-shadow: 0 13px 34px rgba(99, 102, 241, 0.42);
}

.stButton > button:focus-visible,
[data-testid="stFormSubmitButton"] > button:focus-visible {
  outline: 2px solid var(--sd-blue);
  outline-offset: 2px;
}

/* Inputs -------------------------------------------------------------- */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea,
[data-baseweb="select"] > div {
  background: rgba(9, 12, 25, 0.82) !important;
  border-color: rgba(167, 139, 250, 0.20) !important;
  border-radius: 11px !important;
  color: var(--sd-text) !important;
}

[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
  border-color: rgba(167, 139, 250, 0.65) !important;
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.10) !important;
}

[data-testid="stWidgetLabel"] p {
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--sd-muted);
}

/* Expanders, alerts, tabs -------------------------------------------- */
[data-testid="stExpander"] {
  border: 1px solid var(--sd-border);
  border-radius: 14px;
  background: rgba(15, 19, 36, 0.55);
  overflow: hidden;
}

[data-testid="stAlert"] {
  border-radius: 13px;
  border: 1px solid var(--sd-border);
}

.stTabs [data-baseweb="tab-list"] {
  gap: 0.4rem;
}

.stTabs [data-baseweb="tab"] {
  border-radius: 10px;
  padding: 0.5rem 0.95rem;
  font-weight: 600;
}

.stTabs [aria-selected="true"] {
  background: rgba(139, 92, 246, 0.13);
}

/* Product cards ------------------------------------------------------- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.product-card) {
  background:
    radial-gradient(340px 180px at 90% 0%, rgba(139, 92, 246, 0.10), transparent 65%),
    linear-gradient(160deg, rgba(21, 26, 48, 0.92), rgba(11, 14, 29, 0.92));
  border: 1px solid rgba(167, 139, 250, 0.14) !important;
  border-radius: 20px;
  box-shadow: 0 16px 40px rgba(2, 4, 14, 0.22);
  transition: border-color 180ms ease, transform 180ms ease, box-shadow 180ms ease;
}

div[data-testid="stVerticalBlockBorderWrapper"]:has(.product-card):hover {
  border-color: rgba(167, 139, 250, 0.34) !important;
  transform: translateY(-2px);
  box-shadow: 0 22px 48px rgba(2, 4, 14, 0.32);
}

.product-card {
  padding: 0.15rem 0.1rem 0.2rem;
}

.product-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
}

.product-emoji {
  font-size: 1.55rem;
  line-height: 1;
  filter: drop-shadow(0 6px 18px rgba(139, 92, 246, 0.25));
}

.product-name {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 650;
  font-size: 0.98rem;
  letter-spacing: -0.02em;
  margin: 0.55rem 0 0.25rem;
  line-height: 1.3;
}

.product-meta {
  color: var(--sd-muted);
  font-size: 0.72rem;
  margin-bottom: 0.7rem;
}

.product-price-row {
  display: flex;
  align-items: baseline;
  gap: 0.45rem;
  margin: 0.65rem 0 0.1rem;
}

.product-price {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1.32rem;
  font-weight: 700;
  letter-spacing: -0.035em;
}

.product-list-price {
  color: var(--sd-muted);
  font-size: 0.76rem;
  text-decoration: line-through;
}

.product-saving {
  color: var(--sd-mint);
  font-size: 0.73rem;
  font-weight: 650;
}

.score-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  margin: 0.7rem 0 0.35rem;
}

.score-track {
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
  flex: 1;
}

.score-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #8B5CF6, #38BDF8);
}

.score-fill.good { background: linear-gradient(90deg, #34D399, #38BDF8); }
.score-fill.warm { background: linear-gradient(90deg, #FBBF24, #FB7185); }

.score-value {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.82rem;
  font-weight: 700;
  color: #DDD6FE;
  min-width: 54px;
  text-align: right;
}

/* Hero / panels -------------------------------------------------------- */
.sd-hero {
  position: relative;
  border: 1px solid var(--sd-border);
  border-radius: 26px;
  padding: clamp(1.3rem, 3vw, 2.35rem);
  background:
    radial-gradient(520px 280px at 88% 0%, rgba(56, 189, 248, 0.12), transparent 65%),
    radial-gradient(560px 340px at 6% 105%, rgba(139, 92, 246, 0.16), transparent 68%),
    linear-gradient(145deg, rgba(19, 23, 43, 0.92), rgba(9, 12, 25, 0.90));
  overflow: hidden;
  margin-bottom: 1.35rem;
}

.sd-hero::after {
  content: '';
  position: absolute;
  width: 240px;
  height: 240px;
  right: -70px;
  top: -110px;
  border-radius: 50%;
  background: rgba(139, 92, 246, 0.16);
  filter: blur(60px);
  pointer-events: none;
}

.sd-hero .sd-hero-sub {
  margin-bottom: 0;
}

.sd-detail-price {
  font-family: 'Space Grotesk', sans-serif;
  font-size: clamp(1.8rem, 4vw, 2.7rem);
  letter-spacing: -0.045em;
  font-weight: 700;
}

.sd-panel {
  border: 1px solid var(--sd-border);
  border-radius: 18px;
  padding: 1rem 1.1rem;
  background: rgba(15, 19, 36, 0.62);
}

.sd-panel-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 0.92rem;
  font-weight: 650;
  margin-bottom: 0.55rem;
}

.sd-kpi-row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
  margin: 0.5rem 0 0.9rem;
}

.sd-kpi {
  border: 1px solid rgba(167, 139, 250, 0.13);
  background: rgba(9, 12, 25, 0.5);
  border-radius: 12px;
  padding: 0.55rem 0.7rem;
  min-width: 105px;
}

.sd-kpi-label {
  font-size: 0.64rem;
  color: var(--sd-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 650;
}

.sd-kpi-value {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  font-weight: 650;
  margin-top: 0.15rem;
}

.sd-divider {
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(167, 139, 250, 0.22), transparent);
  margin: 1.2rem 0;
}

.offer-table, .compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}

.offer-table th, .compare-table th {
  text-align: left;
  color: var(--sd-muted);
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  padding: 0.45rem 0.5rem;
  border-bottom: 1px solid rgba(167, 139, 250, 0.14);
}

.offer-table td, .compare-table td {
  padding: 0.55rem 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.045);
}

.offer-table tr:last-child td, .compare-table tr:last-child td {
  border-bottom: 0;
}

.offer-table .best-row {
  background: rgba(52, 211, 153, 0.055);
}

/* Empty states -------------------------------------------------------- */
.sd-empty {
  text-align: center;
  padding: 2rem 1rem;
  border: 1px dashed rgba(167, 139, 250, 0.20);
  border-radius: 18px;
  background: rgba(15, 19, 36, 0.34);
}

.sd-empty-icon {
  font-size: 2rem;
  margin-bottom: 0.6rem;
}

/* Chat ----------------------------------------------------------------- */
[data-testid="stChatMessage"] {
  background: rgba(21, 26, 48, 0.55);
  border: 1px solid rgba(167, 139, 250, 0.11);
  border-radius: 15px;
  padding: 0.72rem 0.85rem;
}

[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li {
  font-size: 0.82rem;
  line-height: 1.55;
}

[data-testid="stChatMessage"] h3 {
  font-size: 0.92rem;
  margin-top: 0.1rem;
}

[data-testid="stChatMessage"] table {
  font-size: 0.7rem;
}

[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: linear-gradient(145deg, rgba(99, 102, 241, 0.16), rgba(56, 189, 248, 0.06));
  border-color: rgba(129, 140, 248, 0.18);
}

[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
  background: rgba(139, 92, 246, 0.16) !important;
}

.sd-copilot-context {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.6rem;
  padding: 0.55rem 0.68rem;
  border-radius: 11px;
  border: 1px solid rgba(56, 189, 248, 0.16);
  background: rgba(56, 189, 248, 0.055);
  font-size: 0.7rem;
  color: #BAE6FD;
  line-height: 1.4;
}

.sd-copilot-context strong { color: #E0F2FE; }

.sd-copilot-empty {
  padding: 1.1rem 0.35rem 0.55rem;
}

.sd-copilot-orb {
  width: 46px;
  height: 46px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  color: #FFFFFF;
  font-size: 1.2rem;
  background: linear-gradient(145deg, #8B5CF6, #38BDF8);
  box-shadow:
    0 12px 30px rgba(99, 102, 241, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.22);
  margin-bottom: 0.35rem;
}

.sd-copilot-empty h3 {
  font-size: 1.05rem;
  margin: 0.45rem 0 0.35rem;
  letter-spacing: -0.03em;
}

.sd-copilot-empty p {
  color: var(--sd-muted);
  font-size: 0.78rem;
  margin: 0;
}

.sd-source-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.62rem;
  color: var(--sd-muted);
  letter-spacing: 0.03em;
  margin-top: 0.35rem;
}

.sd-source-badge .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--sd-mint);
}

.sd-source-badge .dot.local { background: var(--sd-amber); }
.sd-source-badge .dot.error { background: var(--sd-rose); }

.sd-typing {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  padding: 0.25rem 0;
}

.sd-typing span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--sd-violet);
  animation: sd-bounce 1.15s infinite ease-in-out;
}

.sd-typing span:nth-child(2) { animation-delay: .14s; }
.sd-typing span:nth-child(3) { animation-delay: .28s; }

@keyframes sd-bounce {
  0%, 80%, 100% { opacity: .35; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-3px); }
}

/* Floating copilot ---------------------------------------------------- */
.st-key-copilot_fab {
  position: fixed !important;
  right: 26px !important;
  bottom: 24px !important;
  z-index: 1300 !important;
  width: auto !important;
}

.st-key-copilot_fab .stButton > button,
.st-key-copilot_fab button {
  border-radius: 999px !important;
  border: 1px solid rgba(196, 181, 253, 0.32) !important;
  background: linear-gradient(135deg, #7C3AED 0%, #6366F1 50%, #0EA5E9 100%) !important;
  color: white !important;
  padding: 0.8rem 1.15rem !important;
  min-height: 3.15rem;
  font-size: 0.86rem !important;
  font-weight: 750 !important;
  letter-spacing: 0.01em;
  box-shadow: 0 14px 36px rgba(99, 102, 241, 0.42), inset 0 1px 0 rgba(255,255,255,.18);
}

.st-key-copilot_fab .stButton > button:hover,
.st-key-copilot_fab button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 18px 44px rgba(99, 102, 241, 0.55), inset 0 1px 0 rgba(255,255,255,.22);
}

.st-key-copilot_panel {
  position: fixed !important;
  top: 18px !important;
  right: 18px !important;
  bottom: 18px !important;
  width: min(420px, calc(100vw - 36px)) !important;
  z-index: 1250 !important;
  display: flex !important;
  flex-direction: column !important;
  gap: 0.55rem !important;
  border-radius: 24px !important;
  border: 1px solid rgba(167, 139, 250, 0.24) !important;
  background:
    radial-gradient(400px 260px at 100% 0%, rgba(56, 189, 248, 0.10), transparent 65%),
    radial-gradient(420px 300px at 0% 100%, rgba(139, 92, 246, 0.13), transparent 68%),
    linear-gradient(165deg, #111528, #070914) !important;
  box-shadow: -24px 24px 80px rgba(0, 0, 0, 0.56), 0 0 0 1px rgba(255,255,255,.02) inset !important;
  padding: 0.85rem 0.85rem 0.8rem !important;
  overflow: hidden !important;
  animation: sd-panel-in 230ms cubic-bezier(.2,.8,.2,1);
}

.st-key-copilot_panel > * {
  flex: 0 0 auto;
  min-width: 0;
}

.st-key-copilot_panel > [data-testid="stLayoutWrapper"]:has(.st-key-copilot_history) {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

@keyframes sd-panel-in {
  from { opacity: 0; transform: translateX(18px) scale(.985); }
  to { opacity: 1; transform: translateX(0) scale(1); }
}

.st-key-copilot_panel [data-testid="stElementContainer"] {
  margin: 0 !important;
}

.st-key-copilot_header {
  flex: 0 0 auto;
}

.st-key-copilot_header [data-testid="stHorizontalBlock"] {
  align-items: center;
  gap: 0.35rem;
  flex-wrap: nowrap !important;
}

.st-key-copilot_header [data-testid="stColumn"] {
  width: auto !important;
  min-width: 0 !important;
}

.st-key-copilot_header [data-testid="stColumn"]:first-child {
  flex: 1 1 auto !important;
}

.st-key-copilot_header [data-testid="stColumn"]:nth-child(2) {
  flex: 0 0 3.4rem !important;
  width: 3.4rem !important;
  min-width: 3.4rem !important;
}

.st-key-copilot_header [data-testid="stColumn"]:nth-child(3) {
  flex: 0 0 2rem !important;
  width: 2rem !important;
  min-width: 2rem !important;
}

.st-key-copilot_header [data-testid="stColumn"]:nth-child(2) button {
  font-family: 'Manrope', 'Segoe UI', sans-serif;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  width: 100%;
  padding: 0 0.25rem;
}

.st-key-copilot_header [data-testid="stColumn"]:nth-child(3) button {
  font-size: 1.15rem;
}

.st-key-copilot_context_row [data-testid="stHorizontalBlock"] {
  align-items: center;
  gap: 0.4rem;
  flex-wrap: nowrap !important;
}

.st-key-copilot_context_row [data-testid="stColumn"] {
  width: auto !important;
  min-width: 0 !important;
}

.st-key-copilot_context_row [data-testid="stColumn"]:first-child {
  flex: 1 1 auto !important;
}

.st-key-copilot_context_row [data-testid="stColumn"]:last-child {
  flex: 0 0 4.2rem !important;
  width: 4.2rem !important;
  min-width: 4.2rem !important;
}

.st-key-copilot_context_row .stButton > button {
  min-height: 2rem;
  padding: 0 0.4rem;
  font-size: 0.7rem;
}

.st-key-copilot_header .stButton > button {
  min-height: 2rem;
  width: 2rem;
  padding: 0;
  border-radius: 10px;
  background: rgba(255,255,255,0.035);
  border-color: rgba(255,255,255,0.07);
  color: var(--sd-muted);
  font-family: 'Segoe UI Symbol', 'Arial Unicode MS', Arial, sans-serif;
  font-size: 1.1rem;
  line-height: 1;
}

.st-key-copilot_history {
  flex: 1 1 auto;
  min-height: 0;
  height: auto;
  max-height: none;
  overflow-y: auto;
  padding-right: 3px;
  scrollbar-width: thin;
}

.st-key-copilot_history::-webkit-scrollbar { width: 5px; }
.st-key-copilot_history::-webkit-scrollbar-thumb {
  background: rgba(167, 139, 250, 0.28);
  border-radius: 999px;
}

.st-key-copilot_history [data-testid="stVerticalBlock"] {
  gap: 0.45rem;
}

.st-key-copilot_history:has(.sd-copilot-empty) {
  justify-content: safe center;
}

.st-key-copilot_quick_prompts {
  flex: 0 0 auto;
}

.st-key-copilot_quick_prompts [data-testid="stHorizontalBlock"] {
  flex-wrap: nowrap !important;
  gap: 0.4rem !important;
}

.st-key-copilot_quick_prompts [data-testid="stColumn"] {
  flex: 1 1 0 !important;
  width: auto !important;
  min-width: 0 !important;
}

.st-key-copilot_quick_prompts .stButton > button {
  text-align: left !important;
  justify-content: flex-start !important;
  font-size: 0.72rem !important;
  font-weight: 600 !important;
  padding: 0.48rem 0.55rem !important;
  min-height: 2.25rem;
  height: auto !important;
  border-radius: 10px !important;
  background: rgba(139, 92, 246, 0.065) !important;
  border-color: rgba(167, 139, 250, 0.13) !important;
  color: #C4B5FD !important;
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
  line-height: 1.3 !important;
}

.st-key-copilot_quick_prompts .stMarkdownEllipsis,
.st-key-copilot_quick_prompts .stMarkdownEllipsis p {
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: clip !important;
}

.st-key-copilot_quick_prompts .stButton > button:hover {
  background: rgba(139, 92, 246, 0.16) !important;
  border-color: rgba(167, 139, 250, 0.35) !important;
  color: #EDE9FE !important;
}

.st-key-copilot_composer {
  flex: 0 0 auto;
}

.st-key-copilot_composer [data-testid="stForm"] {
  border: 1px solid rgba(167, 139, 250, 0.18);
  border-radius: 15px;
  padding: 0.5rem 0.55rem 0.55rem;
  background: rgba(9, 12, 25, 0.72);
}

.st-key-copilot_composer textarea {
  min-height: 54px !important;
  max-height: 118px;
  font-size: 0.82rem !important;
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
  padding: 0.25rem 0.2rem !important;
  resize: vertical;
}

.st-key-copilot_composer textarea:focus {
  box-shadow: none !important;
}

.st-key-copilot_composer [data-testid="InputInstructions"] {
  display: none !important;
}

.st-key-copilot_composer [data-testid="stFormSubmitButton"] > button {
  min-height: 2.1rem;
  border-radius: 9px;
  font-size: 0.73rem;
  padding: 0.25rem 0.65rem;
}

/* Hide the floating launcher while the panel is open. */
.stApp:has(.copilot-panel-marker) .st-key-copilot_fab {
  display: none !important;
}

@media (min-width: 1280px) {
  .stApp:has(.copilot-panel-marker) [data-testid="stMain"] {
    padding-right: 440px;
  }

  .stApp:has(.copilot-panel-marker) .block-container {
    padding-left: 1.5rem;
    padding-right: 1.5rem;
  }

  .stApp:has(.copilot-panel-marker) [data-testid="stMetricLabel"] p {
    font-size: 0.62rem !important;
    white-space: normal !important;
    overflow: visible !important;
    text-overflow: clip !important;
    line-height: 1.3 !important;
  }

  .stApp:has(.copilot-panel-marker) [data-testid="stMetricValue"] {
    font-size: 1.45rem;
  }
}

/* Mobile -------------------------------------------------------------- */
@media (max-width: 900px) {
  .block-container {
    padding-top: 1.3rem;
    padding-left: 1rem;
    padding-right: 1rem;
    padding-bottom: 5.5rem;
  }

  .st-key-copilot_panel {
    top: 8px !important;
    right: 8px !important;
    bottom: 8px !important;
    left: 8px !important;
    width: auto !important;
    border-radius: 20px !important;
    padding: 0.7rem 0.65rem 0.65rem !important;
  }

  .st-key-copilot_fab {
    right: 14px !important;
    bottom: 14px !important;
  }

  .st-key-copilot_fab button {
    min-height: 2.9rem;
    padding: 0.7rem 1rem !important;
    font-size: 0.8rem !important;
  }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
"""


def inject_theme() -> None:
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def inject_copilot_layout(open_state: bool, mobile: bool = False) -> None:
    """Adjust main-content padding when the drawer is open.

    The marker is rendered inside the panel, so `:has()` only applies while the
    panel exists. This prevents the fixed drawer from covering the dashboard's
    primary controls on desktop.
    """

    if not open_state:
        return
    st.markdown(
        """
        <style>
        .stApp .copilot-panel-marker { display: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )
