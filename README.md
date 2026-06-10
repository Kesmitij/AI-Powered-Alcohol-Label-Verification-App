# TTB Alcohol Label Verification Assistant (Prototype)

A clean, obvious, fast web prototype that uses AI vision to extract key fields from alcohol labels and compares them against the data submitted in an application.

Built to honor the real constraints and user needs from the discovery notes:
- Must feel fast (< 5 seconds target per label)
- Must be extremely simple and obvious (works for agents with a wide range of tech comfort)
- Strict Government Warning rules + intelligent fuzzy matching for brand names
- Full support for batch uploads

---

## Current Status (as of implementation start)

- ✅ Core comparison engine (exact + fuzzy + strict warning validation)
- ✅ Full Streamlit UI with editable extraction + instant local re-compare
- ✅ Single label + batch flows
- ✅ 5 high-quality AI-generated realistic test label images included
- ✅ Strong mock / demo mode (the app is immediately usable)
- ✅ xAI Grok vision support (preferred) + OpenAI fallback

---

## Quick Start (Local)

1. **Clone or download** this folder.
2. **Depoy to streamlit:
3. **Add an API key** for real AI extraction:
   - Preferred: Get a free or paid key from https://console.x.ai/ (xAI Grok)
   - Create a `.env` file (copy from `.env.example`) and add:
     ```
     XAI_API_KEY=your_xai_key_here
     ```
   - Or once deployed on streamlit, add to secrets
4. Examples are embedded within the app, you can also download the "Download and Test Sample" files if you want to test uploading them directly.
---

## Using the App

### Single Label
- Click any of the sample buttons at the top (they load realistic generated labels + correct data).
- Or upload your own photo.
- Green = good, Amber = fuzzy/close (use your judgment), Red = clear problem.

### Batch
- Upload multiple files (or a .zip).
- Review the summary table, export CSV/JSON, or click any row to drill into details and edit that specific result locally.

### Key Features That Address the Interview Feedback
- **Speed**: Mock mode is near-instant. Real Grok 4.3 vision is typically 2–5 seconds. Have seen lag later in the evening 6-8 seconds. Lag is on API side, started to build adjustment to OpenAI if needed.
- **Obvious UI**: Large clear sections, sample buttons, status pills, explanations for every flag.
- **Strict warning**: Title-case "Government Warning:" or missing phrases → immediate FAIL with specific reason.
- **Fuzzy brand support**: "STONE'S THROW" vs "Stones Throw" is handled gracefully.
- **Editable extraction**: You are always in control — fix AI mistakes and re-compare with one click, no extra cost.
- **Batch first-class**: Designed for the 200–300 label dumps mentioned by stakeholders.
- **No storage**: Everything is in-memory for the current session.

---

## Deploying to a Public URL

The easiest high-quality option:

1. Pushed this repo to GitHub (public) from my local.
2. Deployed to Streamlit Community Cloud.
3. Connected the repo, set the main file to `app.py`.
4. Added my `XAI_API_KEY` in the secrets UI for the public demo.

Alternative free hosts: Hugging Face Spaces (Docker or Streamlit template).

---

### Quick Test
After adding the key:
- Run the app
- Upload one of the sample labels or a real photo
- You should see real extraction happening

---

## Project Structure

```
Alcohol Labeled App/
├── app.py                  # The Streamlit application (main entrypoint)
├── requirements.txt
├── .env.example
├── .streamlit/config.toml
├── PROJECT_PLAN.md         # Original planning document (kept for reference)
├── README.md               # This file
├── src/
│   ├── __init__.py
│   ├── models.py           # Pydantic data models + official warning text
│   ├── comparison.py       # Pure Python exact + fuzzy + strict warning logic
│   ├── extraction.py       # Grok / OpenAI vision + excellent mock mode
│   └── samples.py          # Sample definitions + image loading + PIL generator
└── samples/
    ├── 01_clean_old_tom.jpg
    ├── 02_warning_titlecase.jpg   # Tests strict warning header
    ├── 03_angled_stones_throw.jpg # Tests fuzzy brand matching
    ├── 04_eagle_ridge_clean.jpg
    ├── 05_partial_old_tom.jpg
    └── README_SAMPLES.txt
```

All the important logic lives in `src/` so it is easy to review, test, or reuse.

---

## What Was Intentionally Kept Simple (Trade-offs)

- No PDF export (CSV is sufficient).
- No persistent storage or user accounts (prototype scope).
- The comparison engine is fully deterministic and auditable (no hidden LLM judgment on the final pass/fail).

These decisions were made to deliver a **working, clean, demonstrable** prototype quickly while still being thoughtful about the stakeholder feedback.
