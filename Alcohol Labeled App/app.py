"""
TTB Alcohol Label Verification Assistant (Prototype)

A clean, obvious Streamlit web app for AI-powered verification of alcohol
labels against submitted application data.

Designed for the wide range of technical comfort levels described in the
discovery interviews (from long-tenured agents to brand new staff).

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Environment variables (optional but recommended for real AI):
    XAI_API_KEY=...          # Grok vision via xAI

"""

from __future__ import annotations

from dotenv import load_dotenv

# Load environment variables from .env file (for XAI_API_KEY etc.)
# This must happen early, before any src.* imports that read os.getenv at module level.
load_dotenv()

import io
import time
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from PIL import Image

from src.comparison import verify
from src.extraction import extract_from_image, get_available_providers
from src.models import LabelData, VerificationResult, OFFICIAL_GOVERNMENT_WARNING
from src.samples import (
    SAMPLES,
    get_sample_by_key,
    get_sample_image_bytes,
    get_sample_from_display_name,
    list_sample_display_names,
    create_demo_placeholder_images,
)


def _resize_for_vision(image_bytes: bytes, max_dimension: int = 1024) -> bytes:
    """Resize image before sending to vision AI.
    Smaller images = faster upload + faster inference. Keeps text readable.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


def _make_thumbnail(image_bytes: bytes, max_dimension: int = 256) -> bytes:
    """Create tiny thumbnail for UI display and to keep session_state small.
    Full-res images in state are a major cause of slow UI and large memory use.
    """
    img = Image.open(io.BytesIO(image_bytes))
    if max(img.size) > max_dimension:
        img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=70, optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Page config & simple theming (makes it feel clean and obvious)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TTB Label Verification Assistant",
    page_icon="🥃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Light custom CSS for better visual status pills and spacing
st.markdown(
    """
    <style>
    .status-pill {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .status-PASS { background-color: #d1fae5; color: #065f46; }
    .status-NEEDS-REVIEW { background-color: #fef3c7; color: #92400e; }
    .status-FAIL { background-color: #fee2e2; color: #991b1b; }
    .field-row { margin-bottom: 0.35rem; }
    .stExpander { border: 1px solid #e5e7eb; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def init_state():
    if "single_result" not in st.session_state:
        st.session_state.single_result: VerificationResult | None = None
    if "single_extracted" not in st.session_state:
        st.session_state.single_extracted: LabelData = LabelData.empty()
    if "single_provided" not in st.session_state:
        st.session_state.single_provided: LabelData = LabelData.empty()
    if "single_image_bytes" not in st.session_state:
        st.session_state.single_image_bytes: bytes | None = None
    if "single_image_name" not in st.session_state:
        st.session_state.single_image_name = ""
    if "batch_results" not in st.session_state:
        st.session_state.batch_results: list[dict[str, Any]] = []
    if "last_provider" not in st.session_state:
        st.session_state.last_provider = get_available_providers()

    # Seed the editable widget keys on first load so the text inputs render cleanly
    for k in ["ex_brand", "ex_class", "ex_abv", "ex_net", "ex_warn", "ex_bottler", "ex_country",
              "ex_appellation", "ex_age", "ex_composition",
              "pr_brand", "pr_class", "pr_abv", "pr_net", "pr_warn", "pr_bottler", "pr_country"]:
        if k not in st.session_state:
            st.session_state[k] = ""


init_state()


def reset_single():
    st.session_state.single_result = None
    st.session_state.single_extracted = LabelData.empty()
    st.session_state.single_provided = LabelData.empty()
    st.session_state.single_image_bytes = None
    st.session_state.single_image_name = ""
    # Clear widget keys so text inputs start fresh
    for k in ["ex_brand", "ex_class", "ex_abv", "ex_net", "ex_warn", "ex_bottler", "ex_country",
              "ex_appellation", "ex_age", "ex_composition",
              "pr_brand", "pr_class", "pr_abv", "pr_net", "pr_warn", "pr_bottler", "pr_country"]:
        st.session_state.pop(k, None)


def sync_extracted_to_widgets(extracted: LabelData):
    """Set the per-widget session_state keys so keyed text_inputs display the values.
    Use getattr for resilience if old LabelData instances from before model update are in session_state.
    """
    st.session_state["ex_brand"] = getattr(extracted, 'brand_name', '')
    st.session_state["ex_class"] = getattr(extracted, 'class_type', '')
    st.session_state["ex_abv"] = getattr(extracted, 'alcohol_content', '')
    st.session_state["ex_net"] = getattr(extracted, 'net_contents', '')
    st.session_state["ex_warn"] = getattr(extracted, 'government_warning', '')
    st.session_state["ex_bottler"] = getattr(extracted, 'bottler', '')
    st.session_state["ex_country"] = getattr(extracted, 'country_of_origin', '')
    # Type-specific (optional)
    st.session_state["ex_appellation"] = getattr(extracted, 'appellation_of_origin', '')
    st.session_state["ex_age"] = getattr(extracted, 'age_statement', '')
    st.session_state["ex_composition"] = getattr(extracted, 'statement_of_composition', '')


def sync_provided_to_widgets(provided: LabelData):
    st.session_state["pr_brand"] = getattr(provided, 'brand_name', '')
    st.session_state["pr_class"] = getattr(provided, 'class_type', '')
    st.session_state["pr_abv"] = getattr(provided, 'alcohol_content', '')
    st.session_state["pr_net"] = getattr(provided, 'net_contents', '')
    st.session_state["pr_warn"] = getattr(provided, 'government_warning', '') or OFFICIAL_GOVERNMENT_WARNING
    st.session_state["pr_bottler"] = getattr(provided, 'bottler', '')
    st.session_state["pr_country"] = getattr(provided, 'country_of_origin', '')
    # Type-specific not typically edited on the submitted side for this prototype, but seed for completeness
    st.session_state["pr_appellation"] = getattr(provided, 'appellation_of_origin', '')
    st.session_state["pr_age"] = getattr(provided, 'age_statement', '')
    st.session_state["pr_composition"] = getattr(provided, 'statement_of_composition', '')


def set_single_from_sample(sample_key: str):
    sample = get_sample_by_key(sample_key)
    if not sample:
        return
    img_bytes = get_sample_image_bytes(sample)
    if img_bytes:
        st.session_state.single_image_bytes = img_bytes
        st.session_state.single_image_name = sample.image_filename

    # Use the ground truth as "extracted"
    st.session_state.single_extracted = sample.extracted.model_copy()

    # Use override if present (for deliberate mismatch demos), else copy extracted
    if sample.submitted_override:
        st.session_state.single_provided = sample.submitted_override.model_copy()
    else:
        st.session_state.single_provided = sample.extracted.model_copy()

    st.session_state.single_result = None

    # Sync to the actual input widgets so they populate on rerun
    sync_extracted_to_widgets(st.session_state.single_extracted)
    sync_provided_to_widgets(st.session_state.single_provided)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🥃 TTB Alcohol Label Verification Assistant")
st.caption("AI-powered prototype for quick, accurate verification of Distilled Spirits, Wine, and Malt Beverage labels against application data")

with st.expander("How to use this tool (read this first — 30 seconds)", expanded=False):
    st.markdown(
        """
        **Step 1: Load a Label (in the left panel)**  
        Upload a label photo (jpg/png/webp) **or** use the "Quick demo samples" selectbox (just under the image area in Step 1).  
        The image preview will appear immediately, and processing starts automatically.

        **Step 2: Review Side-by-Side Data**  
        The AI automatically:
        - Identifies the **beverage type** (Distilled Spirits, Wine, or Malt Beverage) from the image.
        - Extracts the TTB-required elements appropriate for that type.
        - Populates both panels:
          - **Left: Extracted from Label** — what the AI read (edit any mistakes).
          - **Right: Application Submitted** — starts filled from extraction; edit to match what was actually submitted in the application.
        - A banner shows the **Detected Beverage Type** and key required elements for it.
        - Type-specific fields (e.g. Appellation for Wine, Age Statement for Spirits) appear when relevant.

        The comparison results (with status and explanations, especially the strict all-caps "GOVERNMENT WARNING:" rule) appear automatically below.  
        Green = good, Yellow = close/fuzzy (human judgment recommended), Red = clear mismatch.

        Use the **"Clear this label"** button (in Step 1) or **"Start a new verification (clear)"** (top-right of results) to reset everything, including the upload selection.

        **Batch Mode (right tab)**  
        Upload multiple images or a .zip in the uploader. Processing starts automatically (no button needed).  
        Review the summary table (with Download CSV next to the header to save space).  
        Use "Inspect & Edit a Specific Result" to see side-by-side AI vs Application values + field-by-field comparison for that item (with a note that real app data would come from upload or COLA source).  
        Use the **"Clear batch"** button to reset results and the upload selection.

        The goal is speed + obviousness. Everything stays in memory — no data is stored. AI Provider is always **xAI Grok**.
        """
    )

st.divider()

# ---------------------------------------------------------------------------
# Main area - Tabs for Single vs Batch
# ---------------------------------------------------------------------------
tab_single, tab_batch = st.tabs(["Single Label Verification", "Batch Upload & Review"])

# NOTE: In a real deployment the "Application Submitted" data would be uploaded
# separately or pulled from the COLA system / database. Here we use the
# AI output as the "application" data purely for demo purposes 

# ===========================================================================
# SINGLE LABEL TAB
# ===========================================================================
with tab_single:
    st.caption("**AI Provider:** xAI Grok")

    # Note about real application data
    st.info(
            "Note: In this demo the 'Application Submitted' values are copied from the AI extraction "
            "so the comparison UI has the same structure as the single-file tab. In a real deployment "
            "the application data would be uploaded separately or pulled from the COLA system / "
            "database for meaningful mismatch detection."
        )

    # Dynamic key for single uploader to allow clearing the selection via code
    if "single_uploader_key" not in st.session_state:
        st.session_state.single_uploader_key = 0
    single_uploader_key = f"single_uploader_{st.session_state.single_uploader_key}"

    col1, col2 = st.columns([0.42, 0.58], gap="large")

    with col1:
        # Early handling for sample select reset (must be before the selectbox widget is created)
        if st.session_state.pop("_sample_loaded", False):
            st.session_state["sample_select"] = ""

        st.markdown("### Step 1: Label Image")

        uploaded = st.file_uploader(
            "Upload a label photo (jpg, png, etc.)",
            type=["jpg", "jpeg", "png", "webp"],
            key=single_uploader_key,
            help="Real photos with some angle or glare are supported.",
        )

        if uploaded is not None:
            original_bytes = uploaded.getvalue()
            st.session_state.single_image_bytes = original_bytes
            st.session_state.single_image_name = uploaded.name
            st.session_state.single_result = None

            # Auto-process immediately on upload (no extract button)
            t0 = time.time()
            # Resize before AI call for speed
            ai_bytes = _resize_for_vision(original_bytes)
            with st.spinner("Analyzing label..."):
                extracted, notes = extract_from_image(
                    ai_bytes,
                    filename=st.session_state.single_image_name,
                    force_mock=False,  # Always use live AI now
                )
            extract_time = time.time() - t0
            st.session_state.single_extracted = extracted
            st.session_state.single_result = None
            st.session_state.single_extract_time = extract_time
            if notes:
                st.info(f"AI notes: {notes}")

            st.caption(f"**Extraction time for this sample:** {extract_time:.2f} seconds")

            # Store only a tiny thumbnail for display (performance)
            st.session_state.single_image_bytes = _make_thumbnail(original_bytes)

            # Push into widgets
            sync_extracted_to_widgets(extracted)

            # Auto-populate the right side
            st.session_state.single_provided = extracted.model_copy()
            sync_provided_to_widgets(st.session_state.single_provided)

        # Clear button after upload handling so it sees the freshly set bytes on the same run
        has_image = bool(st.session_state.get("single_image_bytes"))
        if st.button("Clear this label", disabled=not has_image, use_container_width=True):
            reset_single()
            # Increment key to clear the file_uploader selection so the list is cleared
            if "single_uploader_key" not in st.session_state:
                st.session_state.single_uploader_key = 0
            st.session_state.single_uploader_key += 1
            st.rerun()

        if st.session_state.single_image_bytes:
            try:
                img = Image.open(io.BytesIO(st.session_state.single_image_bytes))
                st.image(img, caption=st.session_state.single_image_name or "Uploaded label", use_container_width=True)
            except Exception:
                st.warning("Could not display the image, but the bytes are loaded.")
        else:
            st.info("Upload a label or use one of the sample buttons above.")

        # Show extract time for the current single sample (persists after rerun)
        if st.session_state.get("single_extract_time") is not None:
            st.caption(f"**Last AI extraction time:** {st.session_state.single_extract_time:.2f} seconds")
        # Also show the AI notes if available from last extract
        if st.session_state.get("single_extract_notes"):
            st.caption(f"AI notes: {st.session_state.single_extract_notes}")

        st.markdown("**Quick demo samples:**")
        sample_names = [s.display_name for s in SAMPLES]
        selected_sample = st.selectbox("Load sample", options=[""] + sample_names, label_visibility="collapsed", key="sample_select")
        if selected_sample:
            for s in SAMPLES:
                if s.display_name == selected_sample:
                    set_single_from_sample(s.key)
                    # Force the comparison result for samples (mock data, instant "extraction")
                    result = verify(st.session_state.single_extracted, st.session_state.single_provided, processing_time=0.0)
                    st.session_state.single_result = result
                    st.session_state["_sample_loaded"] = True
                    st.rerun()
                    break

        if not st.session_state.get("single_image_bytes"):
            st.info("Tip: Use the demo selectbox above to instantly load a realistic test case and see the full flow.")

    with col2:
        st.markdown("### Step 2: Review Data")
        ex = st.session_state.single_extracted
        bev_type = getattr(ex, 'beverage_type', '')
        if bev_type:
            st.success(f"**Detected Beverage Type: {bev_type}**")
            if bev_type == "Distilled Spirits":
                st.caption("**Key required elements for this type:** Brand Name • Class/Type (per standards of identity) • Alcohol Content • Net Contents • Government Warning (ALL CAPS header + full text) • Bottler/Producer • Country of Origin (imports) • Age Statement (if claimed)")
            elif bev_type == "Wine":
                st.caption("**Key required elements for this type:** Brand Name • Class/Type • Alcohol Content (varies by category) • Net Contents • Government Warning • Bottler • Appellation of Origin (if applicable) • Country of Origin • Foreign wine % (if applicable)")
            elif bev_type == "Malt Beverage":
                st.caption("**Key required elements for this type:** Brand Name • Class/Type or Statement of Composition (for specialties) • Alcohol Content (varies) • Net Contents • Government Warning • Bottler • Country of Origin")
        else:
            st.info("Beverage type will be detected after extraction.")

        # Now side-by-side for Extracted and Submitted so both visible at once, fields aligned
        data_left, data_right = st.columns(2)

        with data_left:
            # Extracted side
            st.markdown("**Extracted from Label** (edit these if the AI was off)")

            # Core fields for all types
            brand_name = st.text_input("Brand Name", key="ex_brand")
            class_type = st.text_input("Class / Type", key="ex_class")
            alcohol_content = st.text_input("Alcohol Content", key="ex_abv")
            net_contents = st.text_input("Net Contents", key="ex_net")
            government_warning = st.text_area(
                "Government Warning (full text)",
                height=140,
                key="ex_warn",
                help="This field is the most strictly checked. Paste or type exactly what you see.",
            )
            bottler = st.text_input("Bottler / Producer (optional)", key="ex_bottler")
            country_of_origin = st.text_input("Country of Origin (optional)", key="ex_country")

            # Type-specific fields - only for the detected beverage type (same set shown in Submitted side)
            if bev_type == "Distilled Spirits":
                st.markdown("**Type-Specific (Distilled Spirits)**")
                age = st.text_input("Age Statement", key="ex_age")
                appellation = ""
                composition = ""
            elif bev_type == "Wine":
                st.markdown("**Type-Specific (Wine)**")
                appellation = st.text_input("Appellation of Origin", key="ex_appellation")
                age = ""
                composition = ""
            elif bev_type == "Malt Beverage":
                st.markdown("**Type-Specific (Malt Beverage)**")
                composition = st.text_input("Statement of Composition", key="ex_composition")
                age = ""
                appellation = ""
            else:
                # No type yet - show all for flexibility, or none
                st.markdown("**Type-Specific**")
                age = st.text_input("Age Statement (Distilled Spirits)", key="ex_age")
                appellation = st.text_input("Appellation of Origin (Wine)", key="ex_appellation")
                composition = st.text_input("Statement of Composition (Malt Beverage)", key="ex_composition")

            new_ex = LabelData(
                beverage_type=getattr(ex, 'beverage_type', ''),
                brand_name=brand_name or "",
                class_type=class_type or "",
                alcohol_content=alcohol_content or "",
                net_contents=net_contents or "",
                government_warning=government_warning or "",
                bottler=bottler or "",
                country_of_origin=country_of_origin or "",
                appellation_of_origin=appellation or "",
                age_statement=age or "",
                statement_of_composition=composition or "",
            )
            st.session_state.single_extracted = new_ex

        with data_right:
            st.markdown("**Application Submitted** (what the applicant entered)")

            # Same fields as left, based on beverage type for consistency
            pr_brand = st.text_input("Brand Name", key="pr_brand")
            pr_class = st.text_input("Class / Type", key="pr_class")
            pr_abv = st.text_input("Alcohol Content", key="pr_abv")
            pr_net = st.text_input("Net Contents", key="pr_net")
            pr_warn = st.text_area(
                "Government Warning (full text)",
                height=140,
                key="pr_warn",
            )
            pr_bottler = st.text_input("Bottler / Producer (optional)", key="pr_bottler")
            pr_country = st.text_input("Country of Origin (optional)", key="pr_country")

            # Type Specific header in Application Submitted for alignment with Extracted side
            st.markdown("**Type-Specific**")
            if bev_type == "Distilled Spirits":
                pr_age = st.text_input("Age Statement", key="pr_age")
                pr_appellation = ""
                pr_composition = ""
            elif bev_type == "Wine":
                pr_appellation = st.text_input("Appellation of Origin", key="pr_appellation")
                pr_age = ""
                pr_composition = ""
            elif bev_type == "Malt Beverage":
                pr_composition = st.text_input("Statement of Composition", key="pr_composition")
                pr_age = ""
                pr_appellation = ""
            else:
                pr_age = st.text_input("Age Statement (Distilled Spirits)", key="pr_age")
                pr_appellation = st.text_input("Appellation of Origin (Wine)", key="pr_appellation")
                pr_composition = st.text_input("Statement of Composition (Malt Beverage)", key="pr_composition")

            new_pr = LabelData(
                beverage_type=getattr(ex, 'beverage_type', ''),
                brand_name=pr_brand or "",
                class_type=pr_class or "",
                alcohol_content=pr_abv or "",
                net_contents=pr_net or "",
                government_warning=pr_warn or "",
                bottler=pr_bottler or "",
                country_of_origin=pr_country or "",
                appellation_of_origin=pr_appellation or "",
                age_statement=pr_age or "",
                statement_of_composition=pr_composition or "",
            )
            st.session_state.single_provided = new_pr

    # Auto-run comparison (no button needed - happens automatically after extract or edits)
    if (st.session_state.get("single_extracted") and 
        st.session_state.get("single_provided") and
        getattr(st.session_state.get("single_extracted", LabelData.empty()), 'has_minimum_data', lambda: False)()):
        start = time.time()
        result = verify(
            st.session_state.single_extracted,
            st.session_state.single_provided,
            processing_time=st.session_state.get("single_extract_time", 0.0)
        )
        st.session_state.single_result = result

    # Results section
    if st.session_state.single_result:
        res: VerificationResult = st.session_state.single_result

        st.divider()

        # Header with title left, export top-right
        header_left, header_right = st.columns([0.65, 0.35])
        with header_left:
            st.subheader("Comparison Results")
        with header_right:
            # Build one-row CSV with status and processing_time at beginning, then per-field details
            # Columns: status, processing_time, then for each field: field_extracted, field_provided, field_status, field_explanation
            row = {
                "status": res.overall_status,
                "processing_time": res.processing_time_seconds,
            }
            for fr in res.field_results:
                prefix = fr.field.lower().replace(" ", "_").replace("/", "_")
                row[f"{prefix}_extracted"] = fr.extracted
                row[f"{prefix}_provided"] = fr.provided
                row[f"{prefix}_status"] = fr.status
                row[f"{prefix}_explanation"] = fr.explanation
            field_df = pd.DataFrame([row])
            csv = field_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "single_comparison.csv", "text/csv", use_container_width=True)

        # Duplicate of "Clear this label" so user has multiple places to clear the same way
        with header_right:
            if st.button("Start a new verification (clear)", type="secondary", use_container_width=True):
                reset_single()
                # Increment key to clear the file_uploader selection
                if "single_uploader_key" not in st.session_state:
                    st.session_state.single_uploader_key = 0
                st.session_state.single_uploader_key += 1
                st.rerun()

        status_class = res.overall_status.replace(" ", "-")
        st.markdown(
            f"<div style='font-size:1.6rem; margin: 0.5rem 0;'>"
            f"Overall: <span class='status-pill status-{status_class}'>{res.overall_status}</span>"
            f" &nbsp;&nbsp; <small>({res.processing_time_seconds}s)</small></div>",
            unsafe_allow_html=True,
        )

        if res.notes:
            st.caption(f"Notes: {res.notes}")

        # Field-by-field table + explanations - compact: field name, then line with Label | Submitted | Status, explanation under
        for fr in res.field_results:
            status_emoji = {"exact": "✅", "fuzzy": "⚠️", "mismatch": "❌", "missing": "❓"}.get(fr.status, "")
            with st.container(border=True):
                st.markdown(f"**{fr.field}**")
                st.markdown(f"**Label:** {fr.extracted or '—'}   |   **Submitted:** {fr.provided or '—'}   |   {status_emoji} **{fr.status.upper()}**")
                if fr.explanation:
                    st.caption(fr.explanation)

# ===========================================================================
# BATCH TAB
# ===========================================================================
with tab_batch:
    st.markdown("### Batch Processing")
    st.caption("Select multiple label photos or a .zip file. The app will process them and let you review each result in detail.")

    # Use a dynamic key so we can force-reset the uploader selection when user clears images/results
    if "batch_uploader_key" not in st.session_state:
        st.session_state.batch_uploader_key = 0
    batch_uploader_key = f"batch_uploader_{st.session_state.batch_uploader_key}"
    batch_files = st.file_uploader(
        "Upload label images (multi-select or zip supported)",
        type=["jpg", "jpeg", "png", "webp", "zip"],
        accept_multiple_files=True,
        key=batch_uploader_key,
    )

    if batch_files:
        st.write(f"**{len(batch_files)} file(s) selected**")

    colA, colB = st.columns([1, 1])
    with colA:
        # Automatically start processing once files are selected (like individual tab: once "open" on upload).
        # No "Process / Re-process" button.
        if batch_files and not st.session_state.batch_results:
            st.session_state.batch_results = []
            progress = st.progress(0, text="Starting batch...")

            # Pre-count total images (including those inside zips) for correct progress [0-1]
            total_images = 0
            for f in batch_files:
                fname = f.name
                bytes_data = f.getvalue()
                if fname.lower().endswith(".zip"):
                    try:
                        with zipfile.ZipFile(io.BytesIO(bytes_data)) as zf:
                            for member in zf.namelist():
                                if member.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                                    total_images += 1
                    except Exception:
                        pass
                else:
                    total_images += 1

            processed_count = 0

            for f in batch_files:
                fname = f.name
                bytes_data = f.getvalue()

                image_entries = []

                if fname.lower().endswith(".zip"):
                    # Handle zip: extract individual image files
                    try:
                        with zipfile.ZipFile(io.BytesIO(bytes_data)) as zf:
                            for member in zf.namelist():
                                if member.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                                    try:
                                        member_bytes = zf.read(member)
                                        image_entries.append({
                                            "filename": f"{fname}/{member}",
                                            "bytes": member_bytes
                                        })
                                    except Exception:
                                        continue  # skip unreadable member
                    except Exception:
                        # Not a valid zip or corrupted - skip
                        continue
                else:
                    # Regular image file
                    image_entries.append({
                        "filename": fname,
                        "bytes": bytes_data
                    })

                for entry in image_entries:
                    t0 = time.time()
                    # Resize for AI (major speed win for vision calls)
                    ai_bytes = _resize_for_vision(entry["bytes"])
                    extracted, notes = extract_from_image(
                        ai_bytes,
                        filename=entry["filename"],
                        force_mock=False,  # always live AI now
                    )
                    provided = extracted.model_copy()
                    result = verify(extracted, provided, processing_time=time.time() - t0, notes=notes)

                    # Store only a thumbnail, not the full image. Full images in session_state
                    # are a reason for slow UI / image loading in batch.
                    thumb = _make_thumbnail(entry["bytes"])

                    st.session_state.batch_results.append({
                        "filename": entry["filename"],
                        "overall": result.overall_status,
                        "time_s": result.processing_time_seconds,
                        "extracted": extracted.model_dump(),
                        "provided": provided.model_dump(),
                        "result": result.model_dump(),
                        "image_bytes": thumb,
                        "notes": notes,
                    })
                    processed_count += 1
                    progress.progress(min(processed_count / max(total_images, 1), 1.0), text=f"Processed {processed_count} image(s)")

            progress.empty()
            if processed_count > 0:
                st.success(f"Batch complete. Processed {processed_count} image(s). Scroll down to review individual results.")

    with colB:
        if st.button("Clear batch", disabled=not st.session_state.batch_results):
            st.session_state.batch_results = []
            # Force the file_uploader to forget the previously selected files
            if "batch_uploader_key" not in st.session_state:
                st.session_state.batch_uploader_key = 0
            st.session_state.batch_uploader_key += 1
            st.rerun()

    # Results table
    if st.session_state.batch_results:
        st.divider()

        # Build the detailed export CSV first (to place button next to header)
        # one row per batch record, matching individual export format
        batch_rows = []
        for r in st.session_state.batch_results:
            row = {
                "filename": r.get("filename", ""),
                "status": r["overall"],
                "processing_time": r["time_s"],
            }
            field_results = r.get("result", {}).get("field_results", [])
            for fr in field_results:
                prefix = fr.get("field", "").lower().replace(" ", "_").replace("/", "_")
                row[f"{prefix}_extracted"] = fr.get("extracted", "")
                row[f"{prefix}_provided"] = fr.get("provided", "")
                row[f"{prefix}_status"] = fr.get("status", "")
                row[f"{prefix}_explanation"] = fr.get("explanation", "")
            batch_rows.append(row)
        batch_df = pd.DataFrame(batch_rows)
        csv = batch_df.to_csv(index=False).encode("utf-8")

        # Header with summary title left, download CSV top-right to save space
        header_l, header_r = st.columns([0.7, 0.3])
        with header_l:
            st.markdown("#### Batch Summary")
        with header_r:
            st.download_button("Download CSV", csv, "batch_label_results.csv", "text/csv", use_container_width=True)

        # Simple summary table for display
        df = pd.DataFrame([
            {
                "File": r["filename"],
                "Status": r["overall"],
                "Time (s)": r["time_s"],
                "Brand (extracted)": r["extracted"].get("brand_name", ""),
            }
            for r in st.session_state.batch_results
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Drill-down inspector
        st.markdown("#### Inspect & Edit a Specific Result")
        options = [f"{i+1}. {r['filename']} — {r['overall']}" for i, r in enumerate(st.session_state.batch_results)]
        choice = st.selectbox("Choose a label to inspect", options, index=0 if options else None)

        if choice:
            idx = int(choice.split(".")[0]) - 1
            item = st.session_state.batch_results[idx]

            st.write(f"**{item['filename']}** — {item['overall']}")

            # Show the image (thumbnail)
            try:
                st.image(item["image_bytes"], width=420)
            except Exception:
                pass

            # Note about real application data
            st.info(
                "Note: In this demo the 'Application Submitted' values are copied from the AI extraction "
                "so the comparison UI has the same structure as the single-file tab. In a real deployment "
                "the application data would be uploaded separately or pulled from the COLA system / "
                "database for meaningful mismatch detection."
            )

            ex_dict = item.get("extracted", {})
            edited_ex = LabelData(**ex_dict)

            prov_dict = item.get("provided", {})
            edited_prov = LabelData(**prov_dict)

            st.markdown("**AI Extraction vs Application Submitted** (edit to simulate differences)")

            comp_left, comp_right = st.columns(2)
            with comp_left:
                st.markdown("**AI Extracted from Label**")
                edited_ex.brand_name = st.text_input("Brand", edited_ex.brand_name, key=f"b_ex_brand_{idx}")
                edited_ex.class_type = st.text_input("Class/Type", edited_ex.class_type, key=f"b_ex_class_{idx}")
                edited_ex.alcohol_content = st.text_input("Alcohol Content", edited_ex.alcohol_content, key=f"b_ex_abv_{idx}")
                edited_ex.net_contents = st.text_input("Net Contents", edited_ex.net_contents, key=f"b_ex_net_{idx}")
                edited_ex.government_warning = st.text_area("Government Warning", edited_ex.government_warning, height=90, key=f"b_ex_warn_{idx}")

            with comp_right:
                st.markdown("**Application Submitted**")
                edited_prov.brand_name = st.text_input("Brand", edited_prov.brand_name, key=f"b_pr_brand_{idx}")
                edited_prov.class_type = st.text_input("Class/Type", edited_prov.class_type, key=f"b_pr_class_{idx}")
                edited_prov.alcohol_content = st.text_input("Alcohol Content", edited_prov.alcohol_content, key=f"b_pr_abv_{idx}")
                edited_prov.net_contents = st.text_input("Net Contents", edited_prov.net_contents, key=f"b_pr_net_{idx}")
                edited_prov.government_warning = st.text_area("Government Warning", edited_prov.government_warning, height=90, key=f"b_pr_warn_{idx}")

            # Show current comparison for the chosen item (values from application vs AI)
            current_res = VerificationResult(**item["result"])
            st.markdown("**Field-by-field comparison (Application vs AI)**")
            for fr in current_res.field_results:
                emoji = {"exact": "✅", "fuzzy": "⚠️", "mismatch": "❌", "missing": "❓"}.get(fr.status, "")
                st.markdown(f"- **{fr.field}**: AI=`{fr.extracted}` | App=`{fr.provided}` → {emoji} {fr.status} — {fr.explanation}")

# ---------------------------------------------------------------------------
# Footer / final notes
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "This is a standalone proof-of-concept. It is not connected to COLA and is intended only for evaluation. "
    "All processing happens in the current browser session."
)