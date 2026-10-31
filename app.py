"""AIDTM Student Support Agent - Assignment 1 UI (chat, traces & evaluation, memory & data).
   streamlit run app.py          (tick "Demo mode" in the sidebar to try it without an API key)"""
import json
import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import config
import memory
import observability as obs
import records
import tools
from agent import SupportAgent

st.set_page_config(page_title="AIDTM Student Support", page_icon="🎓", layout="wide", initial_sidebar_state="auto")
ss = st.session_state
for key, default in {"student": None, "agent": None, "chat": [], "demo": False, "quick": None, "_runs": 0}.items():
    ss.setdefault(key, default)

scroll_widget = components.declare_component("aidtm_scroll", path=str(Path(__file__).parent / "scroll_component"))
PAGES = ["💬 Chat", "📊 Traces & evaluation", "🧠 Memory & data"]

# ============================================================ look & feel
st.markdown("""
<style>
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stAppDeployButton"],
[data-testid="stMainMenu"], [data-testid="stToolbarActions"] { display: none !important; }
/* The "open sidebar" button lives in the toolbar: keep it visible and easy to find. */
[data-testid="stExpandSidebarButton"] { background: #4F46E5 !important; border-radius: 10px !important; opacity: 1 !important; }
[data-testid="stExpandSidebarButton"] *, [data-testid="stExpandSidebarButton"] svg { color: #fff !important; fill: #fff !important; }
[data-testid="stAppViewContainer"] { background: linear-gradient(rgba(244,246,251,.93), rgba(244,246,251,.97)),
        url(app/static/campus.jpg) center / cover no-repeat fixed; }
[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; max-width: 1180px; }
[data-testid="stSidebar"] { border-right: 1px solid #E5E7EB; }
[data-testid="stBottom"], [data-testid="stBottom"] > div { background: transparent !important; }
[data-testid="stBottomBlockContainer"] { max-width: 1180px; margin: 0 auto; }
[data-testid="stSidebar"] .block-container { padding-top: 1rem !important; }

.hero { background: linear-gradient(105deg, rgba(49,46,129,.93) 0%, rgba(91,33,182,.80) 55%, rgba(124,58,237,.45) 100%),
        url(app/static/campus.jpg) center 42% / cover; color: #fff; border-radius: 18px;
        padding: 12px 22px; margin-bottom: 10px; box-shadow: 0 6px 18px rgba(79,70,229,.22); }
.hero h2 { margin: 0; padding: 0; font-size: 1.3rem; line-height: 1.3; color: #fff; }
.hero p { margin: 2px 0 0; opacity: .92; font-size: .88rem; }
/* The scrolling chat/transcript box always fits the window, so the page itself never scrolls. */
[data-testid="stLayoutWrapper"]:has(> [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] .chat-anchor),
[data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .chat-anchor) {
    height: calc(100vh - 330px) !important; flex: 0 0 calc(100vh - 330px) !important; min-height: 260px !important; max-height: none !important; }
.chat-anchor { display: none; }
.brandimg { height: 86px; border-radius: 14px; color: #fff; padding: 14px 16px; display: flex; flex-direction: column; justify-content: flex-end;
        background: linear-gradient(120deg, rgba(49,46,129,.90), rgba(109,40,217,.55)), url(app/static/campus.jpg) center / cover;
        box-shadow: 0 4px 12px rgba(79,70,229,.25); }
.brandimg b { font-size: 1.1rem; } .brandimg small { opacity: .9; font-size: .78rem; }
.usercard { background: #F4F6FB; border: 1px solid #E5E7EB; border-radius: 14px; padding: 12px 14px; margin: 10px 0 6px; }
.usercard b { font-size: 1rem; }
.usercard span { color: #6B7280; font-size: .82rem; }
.chip { display:inline-block; padding:2px 10px; border-radius:999px; font-size:.74rem; font-weight:600; margin:2px 4px 2px 0; }
.chip.ok { background:#DCFCE7; color:#166534; } .chip.warn { background:#FEF3C7; color:#92400E; }
.chip.info { background:#E0E7FF; color:#3730A3; } .chip.bad { background:#FEE2E2; color:#991B1B; }

[data-testid="stChatMessage"] { background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:.65rem .9rem;
        margin-bottom:.45rem; box-shadow:0 1px 2px rgba(16,24,40,.04); }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background:#EEF2FF; border-color:#E0E7FF; }
[data-testid="stMetric"] { background:#fff; border:1px solid #E5E7EB; border-radius:14px; padding:12px 16px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
.stButton > button { border-radius: 10px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ============================================================ small helpers
def table(rows, empty="Nothing here yet."):
    if not rows:
        st.caption(empty)
        return
    try:
        st.dataframe(rows, hide_index=True, width="stretch")
    except Exception:
        st.dataframe(rows, hide_index=True, use_container_width=True)


def button(label, container=st, **kw):
    try:
        return container.button(label, width="stretch", **kw)
    except Exception:
        return container.button(label, use_container_width=True, **kw)


def hero(title, subtitle):
    st.markdown(f'<div class="hero"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)


def friendly_error(exc) -> str:
    text = str(exc).lower()
    if "429" in text or "rate" in text or "quota" in text or "limit" in text:
        return "The free AI model is busy (rate limit). Please wait about a minute and try again."
    if "401" in text or "api key" in text or "unauthorized" in text:
        return "The API key was rejected. Check GROQ_API_KEY in your .env file."
    if "timeout" in text or "connection" in text:
        return "Could not reach the AI service. Check your internet connection and try again."
    return "Sorry, something went wrong. Please try again."


def autoscroll():
    """Keeps the chat box fitted to the window and the newest message visible."""
    try:
        ss["_runs"] += 1
        scroll_widget(nonce=ss["_runs"], key="chat_scroll", default=None)
    except Exception:
        pass


def new_session():
    """Fresh conversation. Saved memory is kept - that is the point of persistent memory."""
    ss.chat, ss.quick = [], None
    ss.agent = make_agent(ss.student)


def make_agent(student):
    if ss.demo or os.getenv("USE_MOCK") == "1":
        from mock_llm import MockClient
        return SupportAgent(student, MockClient())
    return SupportAgent(student)


def render_message(m):
    with st.chat_message(m["role"], avatar="🧑‍🎓" if m["role"] == "user" else "🎓"):
        st.markdown(m["content"])
        t = m.get("trace")
        if t:
            bits = []
            if t["tools_used"]:
                bits.append("🔧 " + ", ".join(dict.fromkeys(t["tools_used"])))
            if t["evidence"]["policy"]:
                bits.append("📄 " + ", ".join(dict.fromkeys(t["evidence"]["policy"])))
            if t["evidence"]["memory"]:
                bits.append("🧠 " + ", ".join(t["evidence"]["memory"]))
            srcs = t.get("sources") or []
            if srcs:
                bits.append("📍 " + " · ".join(srcs[:2]) + (f" +{len(srcs) - 2}" if len(srcs) > 2 else ""))
            bits += [f"⏱ {t['latency_s']}s", f"🔢 {t['tokens']['input']}→{t['tokens']['output']} tokens"]
            st.caption("  ·  ".join(bits))
            with st.expander("Trace details"):
                st.markdown("**Where this answer came from:** " + ", ".join(f"`{x}`" for x in (t.get("sources") or ["-"])))
                rows = [{"model call": b["call"], "purpose": b["purpose"], "input tokens": b["input"], "output tokens": b["output"],
                         "input tokens went to (estimate)": ", ".join(f"{k} {v}" for k, v in b["input_split_estimate"].items())}
                        for b in t.get("token_breakdown", [])]
                table(rows, "No model calls.")
                if t.get("langsmith_run_id"):
                    st.caption(f"LangSmith run id: {t['langsmith_run_id']}")
                st.json(t["steps"] or [{"info": "answered directly, no tool call"}], expanded=False)


def chat_box():
    """Fixed-height, internally scrolling container; its height is fitted to the window by scroll_component."""
    box = st.container(height=420, border=True)
    with box:
        st.markdown('<span class="chat-anchor"></span>', unsafe_allow_html=True)
    return box


def ask_agent(text, box):
    with box:
        with st.chat_message("user", avatar="🧑‍🎓"):
            st.markdown(memory.redact(text))
        with st.chat_message("assistant", avatar="🎓"):
            with st.spinner("Thinking..."):
                try:
                    t = ss.agent.chat(text)
                except Exception as exc:
                    st.error(friendly_error(exc))
                    return
    ss.chat += [{"role": "user", "content": memory.redact(t["question"])}, {"role": "assistant", "content": t["answer"], "trace": t}]
    st.rerun()


# ============================================================ sidebar
def sidebar():
    with st.sidebar:
        st.markdown('<div class="brandimg"><b>🎓 AIDTM</b><small>Student Support Agent</small></div>', unsafe_allow_html=True)
        students = records.list_students()
        names = {f"{s.name} ({s.user_id})": s for s in students}
        current = next((k for k, v in names.items() if ss.student and v.user_id == ss.student.user_id), list(names)[0])
        pick = st.selectbox("Student asking", list(names), index=list(names).index(current),
                            help="Assignment 1 has no login: choose which student the agent is helping.")
        if ss.student is None or names[pick].user_id != ss.student.user_id:
            ss.student = names[pick]
            ss.chat, ss.quick = [], None
            ss.agent = make_agent(ss.student)
        no_key = not config.GROQ_API_KEY and os.getenv("USE_MOCK") != "1"
        demo = st.toggle("Demo mode (no API key)", value=ss.demo or no_key or os.getenv("USE_MOCK") == "1",
                         help="Uses a simple keyword model instead of the Groq LLM.")
        if demo != ss.demo:
            ss.demo = demo
            ss.agent = None
        if ss.agent is None:
            try:
                ss.agent = make_agent(ss.student)
            except RuntimeError as exc:
                st.error(str(exc))
        page = st.radio("Menu", PAGES, key="nav", label_visibility="collapsed")
        if button("🔄 New session (keeps memory)"):
            new_session()
            st.rerun()
        st.divider()
        ls = obs.status()
        model = "demo (keyword mock)" if (ss.demo or os.getenv("USE_MOCK") == "1") else config.MODEL
        st.markdown(f'<span class="chip info">{model}</span>'
                    + ('<span class="chip ok">LangSmith ON</span>' if ls["enabled"] else '<span class="chip warn">LangSmith off</span>'),
                    unsafe_allow_html=True)
        st.caption(f"Tracing to project: {ls['project']}" if ls["enabled"] else f"LangSmith: {ls['reason']}")
        traces = [m["trace"] for m in ss.chat if m.get("trace")]
        st.caption(f"🔢 Session tokens: {sum(t['tokens']['input'] for t in traces):,} in · {sum(t['tokens']['output'] for t in traces):,} out")
    return page


# ============================================================ pages
QUICK = ["What is my current fee status?", "The payment portal failed. Can I pay on the next working day?",
         "What is my scholarship status?", "What is the hostel fee refund policy?"]


def page_chat():
    hero("💬 Chat with your support agent", "The agent decides when to answer directly, call a tool, search the handbook or use remembered facts.")
    box = chat_box()
    with box:
        if not ss.chat:
            st.markdown("#### 👋 Hi! Try one of these")
            c1, c2 = st.columns(2)
            for i, q in enumerate(QUICK):
                if button(q, container=(c1 if i % 2 == 0 else c2), key=f"quick_{i}"):
                    ss.quick = q
                    st.rerun()
        for m in ss.chat:
            render_message(m)
    typed = st.chat_input("Ask about fees, scholarships, courses or policies...")
    question = typed or ss.pop("quick", None)
    if question and ss.agent:
        ask_agent(question, box)
    autoscroll()


def read_traces():
    p = config.runtime_path("traces.jsonl")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def page_traces():
    hero("📊 Traces & evaluation", "One row per question: which tools ran, where the answer came from, latency and token usage.")
    traces = read_traces()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Questions traced", len(traces))
    c2.metric("Avg latency", f"{round(sum(t['latency_s'] for t in traces) / len(traces), 2) if traces else 0} s")
    c3.metric("Input tokens", f"{sum(t['tokens']['input'] for t in traces):,}")
    c4.metric("Output tokens", f"{sum(t['tokens']['output'] for t in traces):,}")
    st.subheader("Trace log (this app run)")
    table([{"time": t["ts"][11:], "student": t["user"], "question": t["question"][:70], "tools": ", ".join(t["tools_used"]) or "-",
            "data sources": "; ".join(t["sources"]), "model calls": t["llm_calls"], "latency s": t["latency_s"],
            "in tokens": t["tokens"]["input"], "out tokens": t["tokens"]["output"]} for t in reversed(traces)],
          "Ask something in the Chat page and it appears here.")
    st.subheader("Latest evaluation report")
    report = Path(__file__).parent / "results" / "eval_report.md"
    if report.exists():
        st.markdown(report.read_text(encoding="utf-8"))
    else:
        st.info("No report yet. Run `python eval.py` in a terminal (or `python eval.py --mock` for an offline check).")


def page_memory():
    hero("🧠 Memory & data", "What the agent can read and what it has saved. Open these during the demo to explain the answers.")
    s = ss.student
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Saved memory")
        mem = memory.load_all(s.user_id)
        table([{"key": k, "value": v} for k, v in mem.items()], "Nothing saved yet. Say: \"Remember that I prefer WhatsApp\".")
        st.caption("Only durable preferences are stored. Temporary or sensitive statements are rejected in code.")
        st.subheader("Support tickets")
        table([{k: t[k] for k in ("ticket_id", "category", "status", "description")}
               for t in tools.load_tickets() if t["student"] == s.user_id], "No tickets yet.")
    with right:
        st.subheader("Student record (data source)")
        rec = records.get(s.user_id)
        st.json(rec, expanded=False)
        st.subheader("Handbook sections (retrieval source)")
        import rag
        chunks, _, _ = rag._index()
        table([{"section": c["id"], "title": c["title"], "words": len(c["text"].split())} for c in chunks])


# ============================================================ router
def main():
    page = sidebar()
    if ss.student is None:
        return
    {PAGES[0]: page_chat, PAGES[1]: page_traces, PAGES[2]: page_memory}[page]()


main()
