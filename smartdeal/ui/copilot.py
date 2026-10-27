"""Floating, context-aware shopping copilot panel."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..analytics import format_inr
from ..config import Settings
from ..copilot import QUICK_PROMPTS, CopilotAnswer, ask_copilot
from ..database import Database
from .components import e, source_badge
from .theme import inject_copilot_layout

_PANEL_JS = """
<script>
(function () {
  const doc = window.parent.document;
  const COMPOSER = '.st-key-copilot_composer';
  const HISTORY = '.st-key-copilot_history';

  // Delegate on the parent document so the shortcut survives Streamlit reruns
  // that replace the textarea node. Reinstall on every iframe load because the
  // previous listener dies with its iframe realm.
  if (doc.__copilotEnterHandler) {
    doc.removeEventListener('keydown', doc.__copilotEnterHandler, true);
  }
  doc.__copilotEnterHandler = function (event) {
    if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
    const composer = doc.querySelector(COMPOSER);
    if (!composer || !composer.contains(event.target)) return;
    const textarea = composer.querySelector('textarea');
    if (!textarea || event.target !== textarea) return;
    const submit = composer.querySelector('[data-testid="stFormSubmitButton"] button');
    if (!submit) return;
    event.preventDefault();
    submit.click();
  };
  doc.addEventListener('keydown', doc.__copilotEnterHandler, true);

  function scrollHistory() {
    const history = doc.querySelector(HISTORY);
    if (!history) return;
    const messages = history.querySelectorAll('[data-testid="stChatMessage"]');
    if (!messages.length) {
      history.scrollTop = 0;
      return;
    }
    const count = String(messages.length);
    if (history.dataset.copilotCount !== count) {
      history.dataset.copilotCount = count;
      const toBottom = function () {
        requestAnimationFrame(function () {
          history.scrollTop = history.scrollHeight;
        });
      };
      toBottom();
      // Markdown, alerts, and captions can finish laying out after the message
      // node appears. Settle the scroll position once more so the newest notice
      // is not left underneath the composer.
      setTimeout(toBottom, 350);
      setTimeout(toBottom, 1000);
    }
  }

  const observer = new MutationObserver(scrollHistory);
  observer.observe(doc.body, { childList: true, subtree: true });
  scrollHistory();
})();
</script>
"""


def _init_state() -> None:
    defaults = {
        "copilot_open": False,
        "copilot_messages": [],
        "copilot_pending": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def open_copilot(prompt: str | None = None) -> None:
    """Open the panel, optionally queuing a prompt, then rerun."""

    st.session_state.copilot_open = True
    if prompt:
        st.session_state.copilot_pending = prompt
    st.rerun()


def _queue_message(prompt: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return
    st.session_state.copilot_messages.append(
        {
            "role": "user",
            "content": prompt,
            "source": "user",
        }
    )
    st.session_state.copilot_messages = st.session_state.copilot_messages[-40:]
    st.session_state.copilot_pending = prompt
    st.session_state.copilot_open = True
    st.rerun()


def _product_context_text(db: Database, product_id: int | None) -> str | None:
    if product_id is None:
        return None
    product = db.get_product(int(product_id))
    if not product:
        return None
    return f"{product['emoji']} {product['name']} · {format_inr(product['current_price'])}"


def _render_header(settings: Settings) -> None:
    with st.container(key="copilot_header"):
        title_col, clear_col, close_col = st.columns([0.70, 0.15, 0.15])
        with title_col:
            mode = "Smart explanations" if settings.ai_configured else "Built-in analysis"
            dot_color = "#34D399" if settings.ai_configured else "#FBBF24"
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:.55rem">
                  <div style="width:31px;height:31px;border-radius:10px;display:grid;place-items:center;
                    background:linear-gradient(145deg,#8B5CF6,#38BDF8);font-size:.9rem;
                    box-shadow:0 8px 22px rgba(139,92,246,.28)">✦</div>
                  <div>
                    <div style="font-family:'Space Grotesk';font-size:.9rem;font-weight:700;line-height:1.15">Shopping Copilot</div>
                    <div style="font-size:.58rem;color:#9AA3C0;margin-top:.15rem;letter-spacing:.04em">
                      <span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:{dot_color};margin-right:.3rem"></span>
                      {e(mode)} · grounded in app data
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with clear_col:
            if st.button("Reset", key="copilot_clear_chat", help="Clear this session's chat"):
                st.session_state.copilot_messages = []
                st.session_state.copilot_pending = None
                st.rerun()
        with close_col:
            if st.button("×", key="copilot_close", help="Close copilot"):
                st.session_state.copilot_open = False
                st.rerun()


def _render_context(db: Database, product_id: int | None) -> None:
    context_text = _product_context_text(db, product_id)
    with st.container(key="copilot_context_row"):
        if context_text:
            left, right = st.columns([0.78, 0.22])
            with left:
                st.markdown(
                    f'<div class="sd-copilot-context"><span>🛍️ <strong>Context</strong><br>{e(context_text)}</span></div>',
                    unsafe_allow_html=True,
                )
            with right:
                if st.button("Clear", key="copilot_clear_context", help="Clear product context"):
                    st.session_state.selected_product_id = None
                    st.session_state.view = "products"
                    st.rerun()
        else:
            st.markdown(
                '<div class="sd-copilot-context"><span>💬 <strong>No product selected</strong><br>'
                "I can still answer catalog and navigation questions.</span></div>",
                unsafe_allow_html=True,
            )


_NOTICE_BY_KIND = {
    "not_configured": (
        "Smart explanations aren't enabled, so this answer uses the app's "
        "built-in analysis."
    ),
    "auth": (
        "The explanation service could not authenticate the request. This answer "
        "uses the app's built-in analysis, not a model-written response."
    ),
    "credits": (
        "The explanation service is unavailable right now. This answer uses the "
        "app's built-in analysis, not a model-written response."
    ),
    "rate_limit": (
        "The explanation service is busy right now. This answer uses the app's "
        "built-in analysis, not a model-written response."
    ),
    "timeout": (
        "The explanation request took too long. This answer uses the app's "
        "built-in analysis, not a model-written response."
    ),
    "network": (
        "The explanation service could not be reached. This answer uses the app's "
        "built-in analysis, not a model-written response."
    ),
    "provider": (
        "The explanation service returned an error. This answer uses the app's "
        "built-in analysis, not a model-written response."
    ),
    "bad_response": (
        "The explanation service returned an unexpected response. This answer "
        "uses the app's built-in analysis, not a model-written response."
    ),
    "unexpected": (
        "The explanation request failed. This answer uses the app's built-in "
        "analysis, not a model-written response."
    ),
}


def _display_notice(message: dict[str, Any]) -> str:
    """Return a user-facing notice without provider or configuration details."""

    if message.get("source") == "action":
        return str(message.get("notice") or "")
    if not message.get("notice"):
        return ""
    kind = str(message.get("error_kind") or "")
    return _NOTICE_BY_KIND.get(
        kind,
        "This answer uses the app's built-in analysis, not a model-written response.",
    )


def _render_notice(message: dict[str, Any]) -> None:
    notice = _display_notice(message)
    if not notice:
        return
    if message.get("source") == "action":
        st.success(notice, icon="✅")
    elif message.get("error_kind") == "not_configured":
        st.info(notice, icon="🔒")
    else:
        st.warning(notice, icon="⚠️")


def _render_messages() -> None:
    with st.container(key="copilot_history"):
        messages = st.session_state.copilot_messages
        if not messages:
            st.markdown(
                """
                <div class="sd-copilot-empty">
                  <div class="sd-copilot-orb">✦</div>
                  <h3>Your Personal Shopping Copilot</h3>
                  <p>Ask about the product in context, its recorded price history, a seller offer, or your target price. I only use data available in this app, with live and demo records clearly labelled.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="sd-empty" style="padding:.8rem .7rem;text-align:left">'
                '<div class="sd-small sd-muted" style="line-height:1.55">'
                "<strong style=\"color:#DDD6FE\">Recorded facts</strong> come from the app database. "
                "<strong style=\"color:#DDD6FE\">Deal scores</strong> are app calculations. "
                "<strong style=\"color:#DDD6FE\">Forecasts</strong> are estimates with uncertainty."
                "</div></div>",
                unsafe_allow_html=True,
            )
            return

        for message in messages:
            role = message.get("role", "assistant")
            with st.chat_message(role):
                st.markdown(message.get("content", ""))
                if role == "assistant":
                    st.markdown(
                        source_badge(
                            message.get("source", "local"), message.get("model", "")
                        ),
                        unsafe_allow_html=True,
                    )
                    _render_notice(message)
                    data_used = message.get("data_used") or {}
                    if data_used.get("selected_product"):
                        st.caption(
                            f"Grounded in {data_used.get('catalog_products', 0)} catalog products, "
                            f"{data_used.get('recorded_observations', 0)} price observations, and "
                            f"{data_used.get('seller_offers', 0)} seller offers."
                        )


def _render_quick_prompts() -> None:
    if st.session_state.copilot_messages:
        return
    with st.container(key="copilot_quick_prompts"):
        st.markdown(
            '<div class="sd-small sd-muted" style="margin:.15rem 0 .4rem;font-size:.68rem;'
            'text-transform:uppercase;letter-spacing:.09em;font-weight:700">Quick prompts</div>',
            unsafe_allow_html=True,
        )
        columns = st.columns(2)
        for index, prompt in enumerate(QUICK_PROMPTS):
            with columns[index % 2]:
                if st.button(
                    prompt,
                    key=f"quick_prompt_{index}",
                    width="stretch",
                ):
                    _queue_message(prompt)


def _render_composer() -> None:
    with st.container(key="copilot_composer"):
        with st.form("copilot_form", clear_on_submit=True, border=False):
            text = st.text_area(
                "Message",
                placeholder="Ask about a deal, price history, offers, or a target…",
                height=64,
                max_chars=2000,
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button(
                "Send  ↑", width="stretch"
            )
        st.markdown(
            '<div class="sd-small" style="color:#6F7898;font-size:.61rem;text-align:center;margin-top:.28rem">'
            "Enter to send · Shift+Enter for a new line · answers use your tracked data"
            "</div>",
            unsafe_allow_html=True,
        )
    if submitted and text.strip():
        _queue_message(text)


def _process_pending(db: Database, settings: Settings) -> None:
    pending = st.session_state.get("copilot_pending")
    if not pending:
        return

    history = [
        message
        for message in st.session_state.copilot_messages[:-1]
        if message.get("role") in {"user", "assistant"}
    ]
    with st.spinner("Reading recorded prices and seller offers…"):
        try:
            answer: CopilotAnswer = ask_copilot(
                db,
                pending,
                history=history,
                selected_product_id=st.session_state.get("selected_product_id"),
                settings=settings,
            )
        except Exception:
            answer = CopilotAnswer(
                text=(
                    "I could not complete that request because of an unexpected "
                    "application error. The shopping pages and recorded calculations "
                    "are still available. Please try again."
                ),
                source="fallback",
                notice="The copilot request failed; no AI response is being shown.",
                error_kind="unexpected",
            )
    st.session_state.copilot_messages.append(
        {
            "role": "assistant",
            "content": answer.text,
            "source": answer.source,
            "model": answer.model,
            "notice": answer.notice,
            "error_kind": answer.error_kind,
            "data_used": answer.data_used,
        }
    )
    st.session_state.copilot_messages = st.session_state.copilot_messages[-40:]
    st.session_state.copilot_pending = None
    st.rerun()


def render_copilot(db: Database, settings: Settings) -> None:
    _init_state()

    # Launch button (hidden by CSS while the panel is present).
    if st.button("✦  Copilot", key="copilot_fab", help="Open your AI Shopping Copilot"):
        st.session_state.copilot_open = True
        st.rerun()

    if not st.session_state.copilot_open:
        return

    inject_copilot_layout(True)

    with st.container(key="copilot_panel"):
        st.markdown('<div class="copilot-panel-marker"></div>', unsafe_allow_html=True)
        _render_header(settings)
        _render_context(db, st.session_state.get("selected_product_id"))
        _render_messages()
        _render_quick_prompts()
        _process_pending(db, settings)
        _render_composer()
        st.iframe(_PANEL_JS, height=1)
