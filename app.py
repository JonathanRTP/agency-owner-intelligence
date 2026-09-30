import os
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Owner Intelligence", page_icon="◈", layout="wide")
DATA = Path(__file__).parent / "data" / "activity.csv"

HUMAN_DISPOSITIONS = {"conversation", "appointment"}

@st.cache_data
def load_data():
    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    df["is_person"] = df["agent"].ne("PBG Billing")
    # Challenge rule: carrier_answered alone is not evidence of a real conversation.
    df["confirmed_conversation"] = (
        df["disposition"].isin(HUMAN_DISPOSITIONS) | (df["speaker_turns"] >= 4)
    )
    df["quality_flag"] = (
        (df["speaker_turns"] >= 4)
        & (~df["disposition"].isin(HUMAN_DISPOSITIONS))
    )
    # Callbacks are explicitly not appointments.
    df["real_appointment_signal"] = df["appointment_type"].eq("appointment")
    return df


def money(x):
    return f"${x:,.2f}"

def pct(x):
    return f"{x:.1%}"

def build_metrics(df):
    people = df[df.is_person].copy()
    confirmed = people[people.confirmed_conversation]
    sales = int(people.sales.sum())
    applications = int(people.applications.sum())
    spend = float(people.ad_spend.sum())
    dials = int(people.dials.sum())
    carrier = int(people.carrier_answered.sum())
    appointments = int(people.real_appointment_signal.sum())
    return {
        "records": len(people), "dials": dials, "carrier_answered": carrier,
        "confirmed_interactions": len(confirmed), "applications": applications,
        "sales": sales, "ad_spend": spend, "appointments": appointments,
        "sales_per_confirmed": sales / len(confirmed) if len(confirmed) else 0,
        "ad_spend_per_sale": spend / sales if sales else None,
        "data_quality_flags": int(df.quality_flag.sum()),
        "excluded_non_person_records": int((~df.is_person).sum()),
    }

def owner_brief(m):
    signals=[]
    if m["ad_spend_per_sale"] is not None:
        signals.append(f"Ad spend per reported sale is {money(m['ad_spend_per_sale'])}; this is not ROI because revenue is not provided.")
    signals.append(f"There are {m['data_quality_flags']} records where speaker activity (>=4 turns) conflicts with a non-human conversation disposition; these are surfaced, not silently corrected.")
    signals.append(f"{m['appointments']} records have appointment_type='appointment'; callbacks are not counted as appointments.")
    signals.append(f"{m['excluded_non_person_records']} PBG Billing records are excluded from person-level performance views.")
    return signals

@st.cache_data
def agent_table(df):
    p=df[df.is_person].copy()
    g=p.groupby("agent", as_index=False).agg(
        dials=("dials","sum"), carrier_answered=("carrier_answered","sum"),
        confirmed_interactions=("confirmed_conversation","sum"),
        applications=("applications","sum"), sales=("sales","sum"), ad_spend=("ad_spend","sum"),
    )
    g["sales_per_confirmed"]=g["sales"]/g["confirmed_interactions"].replace(0,pd.NA)
    g["ad_spend_per_sale"]=g["ad_spend"]/g["sales"].replace(0,pd.NA)
    return g.sort_values(["sales","applications"], ascending=False)

df=load_data()
m=build_metrics(df)

st.title("Owner Intelligence")
st.caption("Decision-ready business view built on explicit data-confidence rules.")

with st.sidebar:
    st.header("Data trust")
    st.success("Conversation rule applied")
    st.write("Confirmed = human disposition (conversation/appointment) OR ≥4 speaker turns.")
    st.warning("carrier_answered alone does not prove a conversation.")
    st.info("Callbacks are not counted as appointments.")
    st.write(f"Excluded from person performance: **{m['excluded_non_person_records']}** PBG Billing records.")

cols=st.columns(6)
items=[("Reported sales",m["sales"]), ("Applications",m["applications"]), ("Confirmed interactions",m["confirmed_interactions"]), ("Appointments",m["appointments"]), ("Ad spend",money(m["ad_spend"])), ("Data flags",m["data_quality_flags"])]
for c,(label,val) in zip(cols,items): c.metric(label,val)

st.divider()

left,right=st.columns([1.35,1])
with left:
    st.subheader("Where should the owner look?")
    t=agent_table(df).copy()
    t["Ad spend / sale"]=t["ad_spend_per_sale"].map(lambda x: money(x) if pd.notna(x) else "—")
    t["Sales / confirmed"]=t["sales_per_confirmed"].map(lambda x: pct(x) if pd.notna(x) else "—")
    display=t[["agent","sales","applications","confirmed_interactions","ad_spend","Sales / confirmed","Ad spend / sale"]].rename(columns={"agent":"Agent","sales":"Sales","applications":"Apps","confirmed_interactions":"Confirmed","ad_spend":"Ad spend"})
    st.dataframe(display, use_container_width=True, hide_index=True)
with right:
    st.subheader("Owner brief")
    for s in owner_brief(m): st.write("• "+s)
    st.markdown("**Recommended next actions**")
    st.write("1. Investigate high-spend / low-sale segments before changing budgets.")
    st.write("2. Audit records where speaker turns conflict with disposition.")
    st.write("3. Keep callbacks separate from appointment reporting.")
    st.write("4. Do not calculate ROI until revenue is available and defined.")

st.divider()

st.subheader("Data quality signals")
flags=df[df.quality_flag].copy()
if flags.empty:
    st.success("No conflicting interaction signals found.")
else:
    st.write(f"{len(flags)} records have ≥4 speaker turns but a disposition other than conversation/appointment. The app does not overwrite the source disposition.")
    st.dataframe(flags[["timestamp_utc","agent","speaker_turns","disposition","appointment_type","applications","sales","ad_spend"]], use_container_width=True, hide_index=True)

with st.expander("Metric definitions & limitations"):
    st.markdown("""
- **Confirmed interaction:** `disposition` is `conversation` or `appointment`, **OR** `speaker_turns >= 4`, following the challenge rule.
- **Appointment:** only `appointment_type == appointment`. `callback` is deliberately excluded.
- **Sales:** reported `sales` sum; this is a source metric, not an independently verified revenue event.
- **Ad spend / sale:** `ad_spend / sales`. It is **not ROI** because the dataset does not provide revenue.
- **Person performance:** excludes `PBG Billing`, documented in the supplied notes as a non-person account.
- **Premium screen:** not used as a business outcome because the supplied notes identify a Maria document/screen override; it should be treated as a field requiring domain validation before using it for decision-making.
""")

st.subheader("AI Owner Brief (optional)")
st.caption("The AI layer is intentionally downstream of deterministic metrics. It explains validated signals; it does not calculate them.")
api_key=os.getenv("OPENAI_API_KEY")
if api_key:
    if st.button("Generate AI brief"):
        try:
            from openai import OpenAI
            client=OpenAI(api_key=api_key)
            payload={"metrics":m,"signals":owner_brief(m)}
            prompt=("You are an executive analytics assistant. Summarize the supplied validated metrics in 4 short bullets. "
                    "Do not invent facts. Do not call ad spend/sale ROI. Mention data-quality limitations when relevant. "
                    "End with 2 concrete next actions.\n"+json.dumps(payload))
            r=client.responses.create(model=os.getenv("OPENAI_MODEL","gpt-5-mini"), input=prompt)
            st.write(r.output_text)
        except Exception as e:
            st.error(f"AI brief unavailable: {e}")
else:
    st.info("Set OPENAI_API_KEY to enable the optional AI summary. The core experience works without an LLM.")

st.caption("Synthetic challenge data only • Built as a 60-minute MVP • Deterministic metrics first, AI second")
