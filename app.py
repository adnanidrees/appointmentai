import os, time, json, io
import pandas as pd
import streamlit as st

# ---- Secrets → ENV bridge ----
try:
    os.environ.setdefault("OPENAI_API_KEY", st.secrets.get("OPENAI_API_KEY", ""))
except Exception:
    pass

st.set_page_config(page_title="AppointmentAI — Booking & Reminders", page_icon="📅", layout="wide")
st.title("📅 AppointmentAI — Booking copy + reminders")

st.caption(
    "Enter service + time slots → generate WhatsApp booking messages. "
    "Includes Confirm / Reminder / Reschedule / No-show templates. "
    "Roman Urdu + English, export TXT/CSV. (No external API in MVP.)"
)

# ---------- OpenAI helper with fallback ----------
def ai_text(prompt: str, system: str = "", temperature: float = 0.6, max_tokens: int = 700):
    key = os.getenv("OPENAI_API_KEY") or st.session_state.get("OPENAI_API_KEY", "")
    if not key:
        return None, "Missing OPENAI_API_KEY"
    try:
        from openai import OpenAI, RateLimitError
        client = OpenAI(api_key=key)
        delay = 1.0
        last_err = None
        for _ in range(5):
            try:
                r = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role":"system","content":system},
                              {"role":"user","content":prompt}],
                    temperature=temperature, max_tokens=max_tokens
                )
                return (r.choices[0].message.content or "").strip(), None
            except RateLimitError as e:
                last_err = str(e); time.sleep(delay); delay = min(delay*1.8, 12)
        return None, last_err or "Rate limited"
    except Exception as e:
        return None, str(e)

def fallback_booking(service, slots, brand, tone):
    lines = []
    lines.append(
        f"Assalamualaikum! {brand} se {service} ke liye booking karni hai? "
        f"Available slots: {slots}.\nReply with your preferred time. 😊"
    )
    lines.append(
        f"Hi! Quick heads-up — {service} slots filling fast. {slots}\n"
        f"Book now to lock your spot. 🙌"
    )
    if tone == "Premium":
        lines = [l.replace("😊","").replace("🙌","").replace("Hi!","Hello,").replace("Assalamualaikum!","Greetings,") for l in lines]
    return "\n\n".join(lines)

def fallback_templates(service, brand):
    return {
        "confirm": f"Confirmed ✅ — {service} at {{slot}} for {{name}}. Location: {brand}. "
                   f"Please arrive 5–10 mins early. Need help? Reply here.",
        "reminder": f"Reminder ⏰ — {service} today at {{slot}}. If running late, just let us know. See you soon! 😊",
        "reschedule": f"Sorry for the inconvenience — can we reschedule your {service}? Reply with a suitable time and we’ll confirm. 🙏",
        "noshow": f"We missed you today 😅 For your {service}. Want to rebook? Reply with a day/time and we’ll prioritize you."
    }

# ---------- Sidebar (global controls) ----------
with st.sidebar:
    st.header("Settings")
    st.session_state["OPENAI_API_KEY"] = st.text_input("OPENAI_API_KEY (optional)", os.getenv("OPENAI_API_KEY",""), type="password")
    tone = st.selectbox("Tone", ["Friendly", "Premium", "Caring"], index=0)
    lang = st.selectbox("Language", ["Mix (Roman Urdu + English)", "English only", "Roman Urdu only"], index=0)
    st.caption("Tip: Button ko bar-bar press na karein to avoid rate-limits.")

# ---------- Inputs ----------
col1, col2 = st.columns([2,1])
with col1:
    brand = st.text_input("Brand / Location name*", placeholder="e.g., TickCom Salon (Gulberg)")
    service = st.text_input("Service*", placeholder="e.g., Haircut, Dental Checkup, Consultation")
    slots_text = st.text_area("Available slots (one per line)*", "Mon 3:00 PM\nTue 11:00 AM\nWed 5:00 PM")
with col2:
    add_prep = st.checkbox("Include prep/what-to-bring tips", value=True)
    add_policy = st.checkbox("Include cancellation/no-show policy (short)", value=True)
    emoji_ok = st.checkbox("Use light emojis", value=True)

clients_csv = st.file_uploader("Clients CSV (optional: name, phone, slot)", type=["csv"])
st.caption("If CSV is provided, per-client messages will include {{name}} and {{slot}} when available.")

def lang_hint():
    if lang.startswith("Mix"): return "Language: Roman Urdu + English mix."
    if lang.startswith("English"): return "Language: English only."
    return "Language: Roman Urdu only."

# ---------- Generate Booking Messages ----------
if st.button("📝 Generate Booking Messages", type="primary", use_container_width=True):
    if not brand or not service or not slots_text.strip():
        st.error("Please fill Brand, Service, and Slots."); st.stop()

    slots_oneline = " | ".join([s.strip() for s in slots_text.splitlines() if s.strip()][:10])
    extras = []
    if add_prep:
        extras.append("Include 1 short line: any prep or 'what to bring' if relevant.")
    if add_policy:
        extras.append("Include 1 short line: cancellation/no-show policy (very short).")
    if emoji_ok:
        extras.append("Use light, brand-safe emojis (if appropriate).")
    else:
        extras.append("Do not use emojis.")
    extras.append(lang_hint())

    prompt = f"""
Create 4 WhatsApp booking prompts for a business.

Service: {service}
Brand/Location: {brand}
Available slots to present: {slots_oneline}
Tone: {tone}
{'; '.join(extras)}

Each prompt must be <= 320 characters.
Return them separated by blank lines. Avoid long paragraphs.
""".strip()

    with st.spinner("Generating…"):
        text, err = ai_text(prompt, system="You are a helpful booking coordinator for SMBs in Pakistan.")
    if err or not text:
        st.info(f"AI fallback used: {err or 'no content'}")
        text = fallback_booking(service, slots_oneline, brand, tone)

    st.success("Booking prompts ready.")
    st.text_area("Booking Prompts", text, height=280)

    st.download_button("⬇️ Download booking_prompts.txt", text.encode("utf-8"),
                       "booking_prompts.txt", "text/plain")

# ---------- Generate Confirm / Reminder / Reschedule / No-show ----------
st.markdown("---")
st.subheader("Templates: Confirm / Reminder / Reschedule / No-show")

if st.button("✨ Generate Templates", use_container_width=True):
    guidelines = []
    if emoji_ok:
        guidelines.append("Use light, respectful emojis if natural.")
    else:
        guidelines.append("No emojis.")
    guidelines.append(lang_hint())

    prompt = f"""
Create 4 short WhatsApp message templates for a booking workflow:

1) Confirmation after booking (variables: {{name}}, {{slot}})
2) Reminder before appointment (variables: {{name}}, {{slot}})
3) Reschedule (business asks customer to pick a new time)
4) No-show follow-up (gentle, invite to rebook)

Service: {service}
Brand: {brand}
Tone: {tone}
{"; ".join(guidelines)}

Each template <= 280 characters. Return clearly separated by headings, each with 1–2 lines.
""".strip()

    with st.spinner("Generating…"):
        text, err = ai_text(prompt, system="You write concise, polite WhatsApp booking ops messages.")
    if err or not text:
        st.info(f"AI fallback used: {err or 'no content'}")
        ft = fallback_templates(service, brand)
        text = (
            "CONFIRMATION\n" + ft["confirm"] + "\n\n"
            "REMINDER\n" + ft["reminder"] + "\n\n"
            "RESCHEDULE\n" + ft["reschedule"] + "\n\n"
            "NO-SHOW\n" + ft["noshow"]
        )

    st.success("Templates ready.")
    st.text_area("Workflow Templates", text, height=360)
    st.download_button("⬇️ Download templates.txt", text.encode("utf-8"),
                       "templates.txt", "text/plain")

# ---------- Per-client personalisation (optional) ----------
st.markdown("---")
st.subheader("Per-client messages (optional)")

st.caption("Upload a CSV with columns like: name, phone, slot. We’ll personalize Confirmation + Reminder messages.")

if clients_csv and st.button("📤 Build per-client messages"):
    df = pd.read_csv(clients_csv)
    # Load or create confirmation/reminder from earlier (or fallback)
    confirm_tpl = f"Confirmed ✅ — {service} at {{slot}} for {{name}}. Location: {brand}. Please arrive 5–10 mins early."
    reminder_tpl = f"Reminder ⏰ — {service} today at {{slot}} for {{name}}. See you soon!"
    # try to reuse AI templates if available in session textarea? (not storing, simple MVP)

    rows = []
    for _, r in df.iterrows():
        nm = str(r.get("name", "Guest")).strip()
        ph = str(r.get("phone", "")).strip()
        sl = str(r.get("slot", "—")).strip()
        rows.append({
            "name": nm,
            "phone": ph,
            "slot": sl,
            "confirm_message": confirm_tpl.replace("{name}", nm).replace("{slot}", sl),
            "reminder_message": reminder_tpl.replace("{name}", nm).replace("{slot}", sl),
        })
    out = pd.DataFrame(rows)
    st.dataframe(out, use_container_width=True)

    # Downloads
    buf = io.BytesIO()
    out.to_csv(buf, index=False, encoding="utf-8")
    st.download_button("⬇️ Download client_messages.csv", buf.getvalue(),
                       "client_messages.csv", "text/csv")

# ---------- Footer ----------
st.markdown("---")
st.caption("MVP only generates content. Actual sending/scheduling can be added later via WhatsApp Cloud + Calendar API.")
