# Approach, Tools, and Assumptions

## Overview

This prototype is a standalone web application built as a proof-of-concept for the TTB's Alcohol Label Verification needs. The goal was to demonstrate an AI-powered tool that could extract key label information from uploaded images (including real-world photos) and intelligently compare it against submitted application data, while prioritizing the constraints and feedback gathered from stakeholders.

The core approach combines:
- A multimodal large language model (vision-capable LLM) for robust text and structure extraction from imperfect label images.
- A transparent, rule-based + fuzzy comparison engine for field matching.
- A simple, obvious user interface that supports both single-label review and batch processing.
- Automatic detection of beverage type to surface only the relevant TTB-required fields.

The app is deliberately **not** integrated with the existing COLA system. It is a self-contained prototype intended to illustrate technical feasibility, user experience priorities, and engineering trade-offs.

## Key Decisions and Rationale

### Why Streamlit (Python)?
- Fast to build a clean, usable interface.
- Built-in widgets (file uploaders, columns, progress, dataframes, expanders) naturally produce linear, obvious flows. Matching stakeholder requirements for users with varying technical comfort (from Dave to Jenny).
- Single-language stack (Python) simplified integration with the vision API, image processing, and data models.
- Easy deployment to Streamlit Community Cloud for a public demo URL with almost zero infrastructure work.

Trade-off accepted: Less "polished" custom UI than a full React + backend stack, but far more appropriate for the time constraints and the target user base.

### Why a Vision LLM (Grok via xAI / OpenAI-compatible client) instead of classical OCR?
- Real label photos are frequently imperfect (angles, glare, lighting, small text, creative layouts) — exactly as described by Jenny.
- Vision models handle these variations far better than traditional OCR + post-processing pipelines, with less custom code.
- Structured JSON output mode allows reliable field extraction in a single call.
- Speed: Typical 2–5 seconds per label with proper image resizing (meeting Sarah's hard requirement of results in ~5 seconds or less).

Trade-off accepted: Did see lagging in processing eclipsing the 5 seconds late in the evening. Assumption is due to API, expanded most processes to allow OpenAI api as well.

The model is called via the official OpenAI client pointed at `https://api.x.ai/v1` using the "Chat" API key (Grok 4.3 or equivalent vision model). This was chosen because:
- It natively supports image input + structured outputs.
- It aligns with my personal preference for an xAI solution when possible. Can switch to OpenAI is time lag persists.

### Automatic Beverage Type Detection + Dynamic Fields?
TTB requirements vary by beverage category (Distilled Spirits, Wine, Malt Beverage). The AI is explicitly instructed (Step 1 in the prompt) to classify the label and only return/populate type-appropriate fields (e.g., Appellation of Origin for Wine, Age Statement for Spirits, Statement of Composition for Malt Beverages).

This directly supports the requirement to handle "the most common type first" while making the system extensible.

### Side-by-Side Extracted vs. Submitted + Automatic Comparison?
- Mirrors real workflow (agent reviews label vs. application data).
- Allows immediate editing of AI output (addresses AI imperfection) and the submitted data.
- Comparison runs automatically after extraction or edits — no extra buttons required.
- Uses a hybrid engine: deterministic rules for critical fields (especially the strict Government Warning formatting) + fuzzy matching (rapidfuzz) for brand names and similar text (respecting Dave's feedback on nuance like "STONE'S THROW" vs "Stones Throw").

The Government Warning check is deliberately strict on casing and required phrasing, while other fields allow "fuzzy" tolerance with clear explanations.

### Performance and State Management Decisions
- Images are resized before being sent to the vision model (max ~1024px) — reduces latency and cost while preserving readability.
- Only small thumbnails (~256px) are kept in `st.session_state` for display. Full-resolution images are never persisted long-term.
- This was a direct response to observed slowdowns when full images were stored in session state.
- All processing is in-memory. No database or permanent storage (security and prototype scope).

### Batch Processing
- Supports both individual image files and .zip archives.
- Processing is fully automatic once files are selected.
- Only thumbnails are stored. Full comparison data (extracted, provided, and field-level results) is kept for the inspector and exports.

## Tools and Libraries

| Category          | Tool / Library          | Purpose                                               | Why Chosen |
|-------------------|-------------------------|-------------------------------------------------------|------------|
| Web Framework     | Streamlit               | UI, file handling, layout, state                      | Rapid development, clean & obvious UX, easy deployment |
| Vision / LLM      | openai (client)         | Calls to xAI Grok vision endpoint                     | OpenAI-compatible, excellent vision + structured JSON support |
| Data Models       | Pydantic (v2)           | Type-safe `LabelData`, `VerificationResult`           | Validation, serialization, clear schema |
| Image Processing  | Pillow                  | Resize before AI, create thumbnails                   | Lightweight, reliable, already a standard |
| Data / Exports    | pandas                  | DataFrames for CSV/JSON exports                       | Simple, powerful tabular handling |
| Fuzzy Matching    | rapidfuzz               | Brand name and text similarity                        | Fast, accurate, pure-Python friendly |
| Environment       | python-dotenv           | Load `XAI_API_KEY` from .env during dev or local runs | Standard, secure secret handling |
| Standard Library  | zipfile, io, etc.       | Zip extraction, image bytes handling                  | No extra dependencies |

No classical OCR (Tesseract/EasyOCR) was used because vision LLMs proved far more robust on real photos with minimal code.

## Assumptions Made

- The prototype is **standalone** and will not be integrated with COLA in this exercise (explicitly stated in the technical requirements).
- A real XAI (or compatible) API key will be provided for the live demo. Without a key the app cannot perform real extraction.
- Focus is on the three main TTB beverage categories (Distilled Spirits, Wine, Malt Beverage). Distilled Spirits was used for the initial test set, but the system is designed to be type-aware.
- Real label photos may be imperfect (angles, glare, lighting, small text). The vision model is expected to handle this better than rule-based OCR.
- Speed is critical for adoption (< ~5 seconds per label target from stakeholder interviews). This drove image resizing and thumbnail-only storage.
- Human review will always be required. The tool surfaces mismatches and explanations but does not make final compliance decisions.
- Batch processing in this prototype is for demonstration purposes (tens of images), not production-scale (hundreds of simultaneous submissions).
- The "Application Submitted" data in the batch demo is synthesized from the AI output for illustration. In production assumption is this would come from a separate upload or system integration (documented in the UI).

## Trade-offs and Known Limitations

- **Cloud Vision Dependency**: Requires internet and an API key. This was accepted because local/open-source vision models at the time did not match the quality/speed/robustness needed for real photos without significant additional engineering.
- **State is In-Memory Only**: Nothing is persisted. This is intentional for a prototype (security, simplicity) but means a browser refresh loses work.
- **Accuracy is Not Guaranteed**: The LLM can still hallucinate or misread on very difficult images. All outputs must be reviewed by a human. Grok has the lowest hallucination rate, hence the reason it was selected.
- **Limited Type Coverage**: While three categories are supported, not every edge-case TTB rule or rare beverage type is implemented.
- **No PDF/Image Enhancement**: No deskewing, contrast enhancement, or super-resolution. We rely on the vision model's tolerance + user-provided thumbnails.
- **Single-Threaded Batch**: Images are processed sequentially for simplicity and to respect rate limits. Parallelism could be added later.

## Why These Decisions Align with Stakeholder Feedback

- **Sarah (speed + batch + simple UI)**: Automatic flows, <5s target via resizing, obvious side-by-side layout, batch support.
- **Jenny (strict warning, real photos)**: Explicit strict checks on "GOVERNMENT WARNING:", vision model chosen for imperfect images.
- **Dave (nuance + don't make life harder)**: Fuzzy matching with explanations for brand names and similar fields; clear "why" for every flag.
- **Marcus (standalone prototype, no crazy security, Azure context)**: Self-contained app, secrets via standard .env (never committed), uses approved-style OpenAI-compatible endpoint.

This approach prioritizes a working, demonstrable, user-centric prototype that directly addresses the pain points described in the discovery interviews while staying within the time and scope constraints of a take-home exercise.

---