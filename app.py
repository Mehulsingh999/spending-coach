"""Streamlit demo: streamlit run app.py"""
import pathlib

import streamlit as st

import agent
from ledger import Ledger

SAMPLE = pathlib.Path(__file__).parent / "sample_data" / "transactions.csv"

st.set_page_config(page_title="Spending Coach", page_icon="💸")
st.title("Spending Coach")
st.caption("Doesn't just total your spending. Tells you what changed, why, and what to do.")

provider = st.sidebar.radio("Model", ["anthropic", "ollama"],
                            format_func=lambda p: "Claude (hosted)" if p == "anthropic" else "Ollama (local)")
up = st.sidebar.file_uploader("Your bank CSV (date, description, category, amount)", type=["csv"])
ledger = Ledger.from_csv(up.getvalue().decode("utf-8"), is_text=True) if up else Ledger.from_csv(str(SAMPLE))
st.sidebar.caption("Using your CSV" if up else "Using sample data (made up)")

summary = ledger.monthly_summary()
cols = st.columns(len(summary))
for c, m in zip(cols, summary):
    c.metric(m["month"], f"${m['spent']:,.0f} spent", f"net ${m['net']:,.0f}")

presets = ["Where did my money go last month, and what should I change?",
           "Do I have subscriptions that went up in price or were charged twice?",
           "What are my top 3 merchants in the latest month?"]
pick = st.radio("Try one", presets, index=0)
question = st.text_input("Or ask your own", value=pick)

if st.button("Ask", type="primary"):
    with st.spinner("Calling tools..."):
        try:
            r = agent.ask(ledger, question, agent.get_llm(provider))
        except Exception as e:
            st.error(f"{type(e).__name__}: {e}")
            st.stop()
    st.subheader("Coach says")
    st.write(r["answer"])
    st.subheader(f"Tool calls ({len(r['tool_calls'])})")
    for i, c in enumerate(r["tool_calls"], 1):
        args = ", ".join(f"{k}={v!r}" for k, v in c["args"].items())
        st.code(f"{i}. {c['tool']}({args})", language="python")
    st.caption(f"{r['tokens']:,} tokens used")
