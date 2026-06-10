# AI-Powered Alcohol Label Verification App — Project Plan

**Project Location:** `C:\Users\kylee\Desktop\Alcohol Labeled App`  
**Status:** Planning Phase (no implementation started)  
**Date:** April 2026  
**Purpose:** Take-home prototype for TTB Compliance Division interview

This document captures the proposed approach, scope, technical decisions, and open questions. **We will not write application code until we discuss and align on this plan.**

---

## 1. Goals & Success Criteria

Primary goal: Deliver a **working, self-contained, easy-to-use web prototype** that demonstrates AI-assisted extraction and verification of alcohol beverage label data against a submitted application.

Success looks like:
- An agent can upload 1 or many label images, enter (or paste) the corresponding application fields, click Verify, and get clear, actionable results in well under 5 seconds per label on average.
- Results are presented simply enough that a 73-year-old who just learned video calling can understand them without training.
- Mismatches (especially the strict Government Warning rules) are highlighted with explanations.
- Batch mode supports the "200–300 at once" peak load scenario described by Sarah.
- The app runs as a deployed public URL anyone on the interview team can open and test.
- Clean, well-organized source code + excellent README + this plan as documentation of decisions and trade-offs.

Non-goals (for this exercise):
- Production integration with COLA
- User accounts, persistence, or audit logging
- FedRAMP / full federal compliance posture (prototype only)
- 100% perfect extraction on every possible label photo

---

## 2. Key Insights from Stakeholder Interviews (Why Design Choices Matter)

**Sarah Chen (Deputy Director):**
- Volume is high (150k/year), team is lean (47 agents).
- Much of the work is rote matching that feels like "data entry verification."
- Previous vendor pilot failed primarily on **speed** (30–40s per label unacceptable; target ~5s or better).
- Extremely wide range of technical comfort: Dave (Clinton admin era, prints emails) to Jenny (just out of college). "Clean, obvious, no hunting for buttons." "Something my mother could figure out."
- Batch upload is a long-standing, high-value request from the field (Seattle office especially).

**Marcus Williams (IT):**
- Azure environment post-2019 migration.
- Prototype is **standalone** — no COLA integration expected or desired at this stage.
- Network/firewall realities: outbound to many ML endpoints was blocked in the prior pilot. Plan accordingly (or document the limitation clearly).
- "Just don't do anything crazy" on security/PII for the prototype.

**Dave Morrison (28-year Senior Agent):**
- Nuance matters. Example: "STONE'S THROW" vs "Stone's Throw" — technically different but obviously the same.
- Agents have judgment; the tool must not fight them or create extra work.
- History of "modernization" projects that made life harder. Respect for existing workflow pain.

**Jenny Park (Junior Agent, 8 months):**
- Current process is shockingly manual (printed checklists).
- Warning statement is the trickiest: must be **exact**, "GOVERNMENT WARNING:" in **all caps and bold**, specific wording.
- Real photos are often imperfect (angles, glare, lighting, small text). Current practice: reject and ask for better image. Opportunity for AI to be more forgiving here.

**Design Implications We Must Honor:**
- Speed is non-negotiable for adoption.
- UI must be extremely obvious and forgiving.
- Always show the "why" for any flag (especially Dave-style judgment calls).
- Strict mode for warning statement + intelligent/fuzzy mode for brand names and other fields.
- Batch is a first-class feature, not bolted on later.
- Support real-world photography quality where possible.

---

## 3. Scope — MVP vs Stretch

### MVP (What We Commit To Delivering)
- Single-image upload + verification flow (end-to-end working)
- Multi-file / batch upload (multi-select or zip) with progress and summary table
- Structured input form for the "application" side:
  - Brand Name
  - Class/Type designation
  - Alcohol Content (ABV % and/or Proof)
  - Net Contents
  - (Optional) Bottler/Producer name & address, Country of origin
  - Government Warning statement (large text area)
- AI-powered extraction from the label image(s) returning structured fields
- Side-by-side comparison view per label:
  - Thumbnail or full image preview
  - Extracted value | Provided value | Status (Match / Fuzzy / Mismatch / Missing) + explanation
- Special handling for Government Warning:
  - Detect presence of the exact header "GOVERNMENT WARNING:" (all caps)
  - Compare body text for required content (see exact text in Appendix)
  - Flag case, punctuation, or wording deviations explicitly
- Basic fuzzy/semantic matching for brand names and free-text fields (handles capitalization, minor punctuation, obvious equivalents)
- Numeric normalization for ABV (e.g., "45% Alc./Vol. (90 Proof)" ↔ 45% or 90 proof)
- Overall status per label + batch-level summary (X passed, Y need review, Z failed)
- Export of results (CSV or simple JSON) for the batch
- "Demo / Mock mode" toggle so the app can be used without an API key (curated examples)
- Very clean, spacious UI with large targets, clear labels, minimal jargon, inline help
- Full README with setup, run, and demo instructions
- 8–12 varied sample label images (clean + realistic photo-style) + expected ground truth
- This PROJECT_PLAN.md + approach notes in README

### Explicitly Out of Scope for v1 (Documented Trade-offs)
- Persistent history or user accounts
- PDF report generation styled like official COLA forms (nice-to-have)
- Deep support for beer vs wine vs spirits rule differences (start with distilled spirits example, make extensible)
- On-device / fully local LLM (see AI section)
- Image enhancement pipeline (deskew, super-res, glare removal) beyond what the vision model provides
- Accessibility audit (WCAG) or screen-reader testing beyond basic good practices
- Mobile-first (desktop/agent workstation use case)

If time allows after MVP is solid, we can discuss adding 1–2 stretch items.

---

## 4. Proposed Technical Stack & Rationale

**Recommended Primary Stack: Python + Streamlit**

**Why this choice fits the constraints extremely well:**
- **Speed of development + iteration:** We can have a fully working single-file or small-module prototype in days, not weeks. Critical for a time-constrained take-home.
- **UI simplicity & obviousness:** Streamlit's widget model (file_uploader, text_input, text_area, columns, dataframe, progress, st.tabs) naturally produces clean, linear, form-driven interfaces. Very little "hunting for buttons."
- **Batch UX:** `st.dataframe` + live updating containers + `st.progress` are excellent for the batch results table with per-row status and timing.
- **Deployment:** One-click or near-zero-config deploy to Streamlit Community Cloud or Hugging Face Spaces → instant public URL. Perfect for "Deployed Application URL" deliverable.
- **Python ecosystem:** Easy access to `openai`, `Pillow`, `pandas`, `pydantic` for structured outputs. Can add light OpenCV/PIL preprocessing later if desired.
- **Single language:** Easier to keep the whole thing coherent and reviewable.

**Strong Alternative Considered: Next.js (React + TypeScript) frontend + FastAPI (Python) backend**
- More "production web app" aesthetics and component control.
- Better for highly custom comparison UI or future micro-interactions.
- Slightly higher surface area and deployment complexity (two services, or full Vercel + serverless functions).
- Recommended only if the interviewers have expressed preference for modern frontend frameworks.

**Decision point for discussion:** Do you have a strong preference between "maximum speed + obviousness" (Streamlit) vs "more polished/custom UI" (Next.js + FastAPI)? My bias is Streamlit unless told otherwise.

**AI / Vision Layer**
- **Primary recommendation:** OpenAI `gpt-4o` (or `gpt-4o-mini`) with vision + structured outputs (JSON mode / tool calling / response_format).
  - Prompt the model once per image to extract all fields + confidence notes + specific call-outs for warning formatting.
  - Can also ask the model to perform the comparison in a second step (or do it deterministically in code for transparency).
  - Strengths: Excellent robustness to angles, glare, unusual fonts, small text, creative layouts. Handles the "not perfectly shot" case Jenny mentioned far better than classical OCR.
  - Speed: Typically 2–5 seconds per label in practice — meets Sarah's hard requirement.
- **Why not pure local OCR (Tesseract / EasyOCR / PaddleOCR) for MVP?**
  - Significantly worse on real bottle photos, glare, perspective distortion.
  - Requires more post-processing code and heuristics.
  - Still needs an LLM (or rules) for the intelligent comparison part anyway.
  - Harder to hit the "works on imperfect images" bar without extra work.
- **Hybrid future path (if wanted):** Run local OCR first for speed/cost, fall back to vision LLM on low-confidence or warning fields.
- **Mock mode:** When enabled, bypasses all API calls and returns hand-crafted extraction + comparison results for the bundled sample images. This is essential for reliable demos and for anyone who cannot or does not want to supply an API key.

**Other Libraries (kept minimal)**
- `openai` (or `litellm` for provider flexibility)
- `Pillow`, `pandas`, `pydantic`
- (Optional light) `opencv-python-headless` or pure PIL for any pre-processing
- `python-dotenv` for local keys

**Data & State**
- Everything in-memory / session state only.
- No database. Uploaded images and results live only for the current browser session (or until "Clear").
- On deployment platforms this is safe and matches "not storing anything sensitive."

---

## 5. Core Flows (User Experience)

**Single Label Flow (Primary happy path)**
1. User lands on clean screen with two clear sections side-by-side or stacked:
   - "Upload Label Image" (big obvious dropzone + browse button)
   - "Enter Application Data" (labeled form fields matching the required TTB elements)
2. User uploads image → immediate preview (thumbnail + filename).
3. User fills/pastes the fields (we can provide a "Load sample data" button that matches one of the test labels).
4. Prominent "Verify Label" button (enabled once image + minimum fields present).
5. Processing state: clear spinner + "Analyzing label with AI (usually 2–4 seconds)..." + perhaps a fake progress bar.
6. Results appear below or in a new tab/section:
   - Large overall status pill (PASS / NEEDS REVIEW / FAIL)
   - Two-column comparison table or cards: Field | Extracted from Label | You Entered | Status + Explanation
   - The original image remains visible (click to enlarge).
   - For the warning row: extra call-out if header casing or exact wording issues.
7. Actions: "Verify Another", "Download Results (CSV)", "Try with corrected values" (re-run comparison locally without new API call).

**Batch Flow**
1. Same upload area, but user can select multiple files or drop a .zip.
2. After upload, a table appears listing each file with status "Queued".
3. "Process All" button (with note "Estimated time: ~3s per label").
4. As items complete, rows update live with status icon, timing, and a "View details" expander or modal that shows the full comparison for that label.
5. Final summary bar: "12 labels processed • 9 clean matches • 2 need review (warning issues) • 1 extraction failure"
6. "Export full report (CSV)" + "Clear all".

**Error & Edge Handling (Critical for Trust)**
- Image unreadable / very low confidence → "AI could not reliably extract text. Options: (a) Try a clearer photo (b) Enter values manually and compare (c) Flag for human review."
- Partial extraction → show what was found + "Missing: Net Contents" etc.
- API failure / timeout / rate limit → graceful message + offer mock mode or retry.
- User corrects a field after seeing AI output → "Re-compare" uses the edited values (no extra API cost).

---

## 6. Comparison Logic Details

We will implement two layers:

1. **Deterministic / Rule-based (transparent and auditable)**
   - Exact match after light normalization (strip, lower for some fields).
   - ABV/proof parsing and equivalence (45% Alc/Vol == 90 Proof for 90-proof spirits).
   - Warning-specific rules:
     - Header must be exactly "GOVERNMENT WARNING:" (all caps, colon present).
     - Body must contain the two required Surgeon General sentences (see Appendix). Minor whitespace/punctuation tolerance but flag deviations.
     - Note presence/absence of "bold" is difficult from image; we can comment that the model saw the header in caps and we assume formatting intent unless the submitter used title case.

2. **Intelligent / Fuzzy (for Dave's nuance cases)**
   - Brand name: use simple string similarity (rapidfuzz or difflib) + optional LLM "are these the same brand?" for edge cases.
   - Class/type and free text: semantic similarity or direct LLM judgment with explanation.
   - Always surface the raw difference + the system's reasoning so the agent can apply human judgment.

The UI will clearly label "Exact match", "Close enough (fuzzy)", "Mismatch — review", and allow overriding the final status.

---

## 7. Test Data & Evaluation

We will curate or generate:
- 4–5 "clean" labels (synthetic, high-quality, matching the example style).
- 3–4 "realistic photo" versions (slight angle, reflections, varied lighting).
- 2–3 "problematic" examples (title-case warning, missing field, brand name casing difference, weird font, glare).
- Ground-truth JSON for each so we can validate the pipeline.
- A small script or notebook (in `samples/`) that documents how each was created and what the expected extraction/comparison outcome is.

Recommendation: Use the available image generation capabilities here to create consistent, professional-looking test labels that look like real distilled spirits bottles. We can also include a couple of actual photographed bottle images if the user can provide (redacted) examples.

---

## 8. Deployment & Demo Considerations

- Target: Deployed public URL (Streamlit Cloud recommended for zero-friction Python deploys).
- API key handling:
  - Local: `.env` file (documented, gitignored).
  - Deployed: Platform secrets UI.
  - Always support "Demo mode (no key required)" using the bundled samples.
- Performance on deploy platform: Most free tiers are fine for demo traffic. We can note rate limits.
- Firewall note: In the final documentation we will explicitly call out Marcus's warning about outbound connections and that a production version would need an approved endpoint (Azure OpenAI, self-hosted model, or on-prem OCR).

---

## 9. Risks, Trade-offs & Assumptions

**Risks & Mitigations**
- Vision model speed/cost variability → Use 4o-mini where possible; implement client-side image resizing before upload; provide timing in UI; mock mode as safety net.
- Extraction errors on creative or poor images → Strong prompting + fallback to "partial extraction + manual correction" flow. Never claim the AI is authoritative.
- Interviewers may have different tech taste → We will present the rationale clearly and offer the alternative stack as a documented option.
- Network blocks in real TTB environment → Documented limitation + note that this prototype uses public APIs for demonstration.

**Assumptions**
- Using a commercial vision LLM (OpenAI) is acceptable for the prototype exercise.
- A public demo URL is the expected deliverable (not an .exe or internal-only).
- We are free to choose modern, productive libraries.
- The focus is on a delightful core experience + solid code quality rather than exhaustive coverage of every TTB rule.

---

## 10. Open Questions (Please Answer Before We Code)

1. **Platform preference:** Web prototype with public URL (Streamlit or Next.js) is strongly implied by the "Deployed Application URL" requirement. Is a desktop app (e.g. Tauri/Electron or PyInstaller) also acceptable or preferred?

2. **AI provider & cost:** Is an OpenAI API key (or Azure OpenAI) acceptable and available for development and the interview demo? Any hard preference or restriction on providers?

3. **Offline capability:** How important is it that the prototype can run completely without internet / external API calls? (This significantly changes the tech choices and accuracy on real photos.)

4. **UI direction:** Do you want the fastest path to an obviously-usable interface (Streamlit/Gradio) or a more custom-designed frontend (React + shadcn or similar)?

5. **Editable extraction:** Should users be able to edit the AI-extracted values in the UI and instantly re-run the comparison logic locally?

6. **Batch upload UX:** Is selecting multiple files (or a .zip) from the file picker sufficient, or do we need drag-and-drop of an entire folder?

7. **Output artifacts:** Is CSV/JSON export enough, or do we need a formatted PDF "review summary" that could be printed or attached?

8. **Presentation logistics:** When is the interview / presentation? How much time will we have to demo the tool vs explain the approach? Is a live walk-through expected or can we pre-record?

9. **Beverage scope:** Focus primarily on the distilled spirits example given, or include basic beer/wine variations in the form and rules?

10. **Anything else** from internal stakeholders or constraints not captured in the discovery notes?

---

## 11. Proposed Way Forward (After Alignment)

1. Finalize stack + scope + answers to the questions above.
2. Initialize git (if not already) and agree on any repo hosting (or just local for now).
3. Generate / curate the sample label set (I can produce high-quality synthetic ones here).
4. Implement the core pipeline (extraction prompt + comparison engine) first, with a simple CLI or notebook harness for fast iteration.
5. Build the Streamlit (or chosen) UI around the proven pipeline.
6. Add batch, export, mock mode, error states, and polish.
7. Write final README + short "Approach & Decisions" section.
8. Deploy + test the public URL.
9. (Optional) Quick self-review or second pair of eyes on UX flow.

We can move extremely quickly once the direction is locked.

---

## Appendix A: Standard U.S. Government Health Warning (TTB)

Exact text that must appear (formatting rules apply):

```
GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.
```

Key enforcement points from Jenny:
- "GOVERNMENT WARNING:" must be in **all capital letters**.
- The header is typically required to be **bold**.
- The full statement must be present and legible.
- Creative variations (title case, missing sentences, smaller font, different wording) are common rejection reasons.

We will hard-code this text in the app for exact comparison and call out deviations.

---

## Appendix B: Core Label Fields (from Example + TTB Context)

- Brand Name
- Class/Type (e.g., "Kentucky Straight Bourbon Whiskey")
- Alcohol Content (ABV % and/or Proof)
- Net Contents (e.g., "750 mL", "1.75 L")
- Name and address of bottler / producer / importer
- Country of origin (for imports)
- Government Health Warning Statement (mandatory on all)

The prototype should at minimum handle the distilled spirits example fields and the warning.

---

## Appendix C: References

- TTB Label Requirements: https://www.ttb.gov/ (we should review the current labeling regulations page during implementation for any edge details)
- COLA system context is provided only for background; prototype is deliberately disconnected.

---

**End of Plan.** This is the document we will discuss and edit together before any code is written in `src/`.

Please reply with answers to the questions in Section 10 (or any other feedback), and we will lock scope and begin implementation immediately afterward.
