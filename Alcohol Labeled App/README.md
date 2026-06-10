# TTB Alcohol Label Verification Assistant (Prototype)

**Take-home project for the TTB Compliance Division interview**

A clean, obvious, fast web prototype that uses AI vision to extract key fields from distilled spirits labels and compares them against the data submitted in an application.

Built to honor the real constraints and user needs from the discovery notes:
- Must feel fast (< 5 seconds target per label in real mode)
- Must be extremely simple and obvious (works for agents with a wide range of tech comfort)
- Strict Government Warning rules + intelligent fuzzy matching for brand names
- Full support for batch uploads
- Fully working demo mode with no API key required

---

## Current Status (as of implementation start)

- ✅ Core comparison engine (exact + fuzzy + strict warning validation)
- ✅ Full Streamlit UI with editable extraction + instant local re-compare
- ✅ Single label + batch flows
- ✅ 5 high-quality AI-generated realistic test label images included
- ✅ Strong mock / demo mode (the app is immediately usable)
- ✅ xAI Grok vision support (preferred) + OpenAI fallback
- Ready for GitHub push + public deployment

The app can be run and demonstrated **right now** in demo mode with zero setup beyond installing the requirements.

---

## Quick Start (Local)

1. **Clone or download** this folder.

2. **Create a virtual environment** (recommended):

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Install dependencies**:

   ```powershell
   pip install -r requirements.txt
   ```

4. **(Optional but powerful) Add an API key** for real AI extraction:

   - Preferred: Get a free or paid key from https://console.x.ai/ (xAI Grok)
   - Create a `.env` file (copy from `.env.example`) and add:

     ```
     XAI_API_KEY=your_xai_key_here
     ```

   - Or use an OpenAI key as fallback:
     ```
     OPENAI_API_KEY=sk-...
     ```

5. **Run the app**:

   ```powershell
   streamlit run app.py
   ```

   The app will open in your browser. It starts in **Demo Mode** by default (no key needed).

---

## Using the App

### Single Label
- Click any of the sample buttons at the top (they load realistic generated labels + correct data).
- Or upload your own photo.
- Edit the "Extracted from Label" fields on the left if the AI missed something.
- Adjust the "Application Submitted" fields on the right.
- Hit **Compare / Re-compare** — results appear instantly with explanations.
- Green = good, Amber = fuzzy/close (use your judgment), Red = clear problem.

### Batch
- Upload multiple files (or a .zip).
- Click "Process all".
- Review the summary table, export CSV/JSON, or click any row to drill into details and edit that specific result locally.

### Key Features That Address the Interview Feedback
- **Speed**: Mock mode is near-instant. Real Grok 4.3 vision is typically 2–5 seconds.
- **Obvious UI**: Large clear sections, sample buttons, status pills, explanations for every flag.
- **Strict warning**: Title-case "Government Warning:" or missing phrases → immediate FAIL with specific reason.
- **Fuzzy brand support**: "STONE'S THROW" vs "Stones Throw" is handled gracefully.
- **Editable extraction**: You are always in control — fix AI mistakes and re-compare with one click, no extra cost.
- **Batch first-class**: Designed for the 200–300 label dumps mentioned by stakeholders.
- **No storage**: Everything is in-memory for the current session.

---

## Deploying a Public URL (for the evaluators)

The easiest high-quality option:

1. Push this repo to GitHub (public or private — your choice).
2. Go to https://share.streamlit.io/ (or the new Streamlit Community Cloud).
3. Connect the repo, set the main file to `app.py`.
4. Add your `XAI_API_KEY` (or `OPENAI_API_KEY`) in the secrets UI if you want real AI for the public demo.
5. Deploy.

Alternative free hosts that also work great: Hugging Face Spaces (Docker or Streamlit template).

Once deployed, send the public URL + the GitHub link to the evaluators. They can test it themselves with the included samples or by uploading their own test labels.

---

## Getting the Correct xAI / Grok API Key (Important)

You have several products available in the xAI console: **Chat, Build, Imagine, and Voice**.

**For this app you need the Chat key.**

### Why "Chat"?
- **Chat** → Grok 4.3 (or equivalent) — this is the one that supports **image input** (vision).  
  We send the label photo to the model so it can read the brand name, ABV, warning text, etc.
- **Build** → Grok Build 0.1 (fast coding/agent model) — not used for vision.
- **Imagine** → Image *generation* (creating new pictures) — we don't need this.
- **Voice** → Voice features — not needed.

### Steps
1. Go to the xAI console: https://console.x.ai/ (or directly to API keys: https://console.x.ai/team/default/api-keys)
2. Locate the **Chat** section (it should show as "available").
3. Create a new API key for Chat (or copy the existing one).
4. In this project folder, copy `.env.example` → `.env`
5. Paste the key:

   ```env
   XAI_API_KEY=your_chat_key_from_console
   ```

6. Make sure `USE_MOCK_MODE=true` while you're testing (or if you don't have the key yet). The app will automatically switch to real Grok vision when it detects the key and you turn Demo Mode off in the sidebar.

The code in `src/extraction.py` checks for `XAI_API_KEY` first and points to the correct endpoint (`https://api.x.ai/v1`) with model `grok-4.3`.

If you only have an OpenAI key for now, you can use that as a temporary fallback (the code supports it).

### Quick Test
After adding the key:
- Run the app
- Turn **Demo Mode off** in the sidebar
- Upload one of the sample labels or a real photo
- You should see real extraction happening (and the sidebar will show "xAI Grok (primary)")

If it still says "Demo / Mock mode only", double-check the key name in `.env` (must be exactly `XAI_API_KEY`).

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

- Focused on **distilled spirits** only for the initial version (as agreed).
- No PDF export (CSV/JSON is sufficient per requirements).
- No persistent storage or user accounts (prototype scope).
- Real AI requires an internet connection and a key (no offline requirement was stated).
- The comparison engine is fully deterministic and auditable (no hidden LLM judgment on the final pass/fail).

These decisions were made to deliver a **working, clean, demonstrable** prototype quickly while still being thoughtful about the stakeholder feedback.

---

## Next Steps for You

1. `pip install -r requirements.txt`
2. `streamlit run app.py`
3. Play with the samples — especially #02 (title case warning) and #03 (fuzzy brand).
4. (Optional) Add your xAI or OpenAI key and turn Demo Mode off to see real vision extraction.
5. When you're happy, push to GitHub and deploy the public URL.

If you run into any issues on your laptop (missing Python, etc.), just let me know — we can walk through it.

---

**This should give the evaluators something they can actually use and understand.**

Good luck with the presentation!
