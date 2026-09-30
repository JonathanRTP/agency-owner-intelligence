# PBG Consulting — Owner Intelligence

## What to submit
1. Push this folder to a public/private GitHub repository.
2. Deploy `app.py` on Streamlit Community Cloud (or another HTTPS host) if desired.
3. Record a <=2 minute demo.
4. Submit `SCREEN_SHARING_RESEARCH.md` as the written research response.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The core app does **not** require an OpenAI key. To enable the optional AI Owner Brief:
```bash
# Windows PowerShell
$env:OPENAI_API_KEY="..."
streamlit run app.py
```

## Design decisions
- Deterministic metrics are calculated before any LLM call.
- A confirmed interaction follows the challenge rule: human disposition (`conversation`/`appointment`) OR >=4 speaker turns.
- `carrier_answered` is never used alone to prove a conversation.
- `callback` is never counted as an appointment.
- `PBG Billing` is excluded from person-level performance because the supplied notes identify it as a non-person account.
- Revenue is not present, so the app does not claim ROI. It shows ad spend per reported sale instead.
- Conflicting disposition/speaker-turn records are surfaced as data-quality signals rather than silently corrected.

## Why this fits the role
The MVP emphasizes software engineering, business reasoning, data quality, and a controlled AI layer. The LLM receives validated metrics and explains them; it is not trusted to invent or calculate the underlying numbers.
