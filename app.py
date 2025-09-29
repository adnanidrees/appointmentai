import os, io, json, time
import streamlit as st

# ---- Bridge Streamlit Secrets → ENV ----
try:
    os.environ.setdefault("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY",""))
except Exception:
    pass

st.set_page_config(page_title="AppointmentAI", page_icon="📅", layout="wide")
st.title("📅 AppointmentAI")
st.caption("Booking copy + reminders (MVP without API)")

# ---- OpenAI helper (optional) ----
import typing as _t
def ai_or_rule_based(prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 500) -> str:
    """Try OpenAI; fallback to rule-based template if key missing or API error."""
    try:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY") or st.session_state.get("OPENAI_API_KEY","")
        if not key:
            raise RuntimeError("no-key")
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":system},{"role":"user","content":prompt}],
            temperature=temperature, max_tokens=max_tokens
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        # simple fallback
        return "• " + prompt[:72] + "...\n• (AI key missing or rate-limited; showing template text)"

st.write('This is a placeholder app body.')