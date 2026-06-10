"""AI-powered label extraction.

Primary: xAI Grok vision models via the OpenAI-compatible endpoint (https://api.x.ai/v1)
Fallback: OpenAI gpt-4o / gpt-4o-mini
Strong mock mode for demos and when no key is available.
"""

from __future__ import annotations

from dotenv import load_dotenv

# Load .env early so the module-level os.getenv calls below pick up XAI_API_KEY
load_dotenv()

import base64
import json
import os
import time
from typing import Any

from openai import OpenAI, OpenAIError
from src.models import LabelData, OFFICIAL_GOVERNMENT_WARNING

# Preferred models
XAI_VISION_MODEL = os.getenv("XAI_VISION_MODEL", "grok-4.3")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")  # or gpt-4o-mini for cheaper/faster

MOCK_EXTRACTIONS: dict[str, dict[str, str]] = {
    # These are realistic "AI output" for the generated sample images.
    # They are used when demo mode is on or when no API key is present.
    # All current demo samples are Distilled Spirits.
    "01_clean_old_tom": {
        "beverage_type": "Distilled Spirits",
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "government_warning": OFFICIAL_GOVERNMENT_WARNING,
        "bottler": "Old Tom Distillery, Louisville, KY",
        "country_of_origin": "",
        "appellation_of_origin": "",
        "age_statement": "",
        "statement_of_composition": "",
        "notes": "Clean straight-on photo. Header is correctly 'GOVERNMENT WARNING:' in all caps and bold. Full warning text legible.",
    },
    "02_warning_titlecase": {
        "beverage_type": "Distilled Spirits",
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "government_warning": "Government Warning: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.",
        "bottler": "",
        "country_of_origin": "",
        "appellation_of_origin": "",
        "age_statement": "",
        "statement_of_composition": "",
        "notes": "Header detected as 'Government Warning:' (title case). This will be flagged by the strict warning rules.",
    },
    "03_angled_stones_throw": {
        "beverage_type": "Distilled Spirits",
        "brand_name": "STONE'S THROW",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "90 Proof",
        "net_contents": "750 mL",
        "government_warning": OFFICIAL_GOVERNMENT_WARNING,
        "bottler": "",
        "country_of_origin": "",
        "appellation_of_origin": "",
        "age_statement": "",
        "statement_of_composition": "",
        "notes": "Photo taken at a slight angle with minor glare. Brand casing on label is 'STONE'S THROW'. Warning header is correct all-caps.",
    },
    "04_eagle_ridge_clean": {
        "beverage_type": "Distilled Spirits",
        "brand_name": "EAGLE RIDGE DISTILLING CO.",
        "class_type": "Straight Rye Whiskey",
        "alcohol_content": "50% Alc./Vol. (100 Proof)",
        "net_contents": "1.75 L",
        "government_warning": OFFICIAL_GOVERNMENT_WARNING,
        "bottler": "Eagle Ridge Distilling Co., Portland, OR",
        "country_of_origin": "",
        "appellation_of_origin": "",
        "age_statement": "",
        "statement_of_composition": "",
        "notes": "Excellent clean photo. All elements very clear.",
    },
    "05_partial_old_tom": {
        "beverage_type": "Distilled Spirits",
        "brand_name": "OLD TOM",
        "class_type": "Bourbon Whiskey",
        "alcohol_content": "90 Proof",
        "net_contents": "750ml",
        "government_warning": "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.",
        "bottler": "",
        "country_of_origin": "",
        "appellation_of_origin": "",
        "age_statement": "",
        "statement_of_composition": "",
        "notes": "Photo has uneven lighting and the bottom of the warning is slightly cut off / small. Net contents has no space. Brand is abbreviated on label.",
    },
}


def _get_client() -> OpenAI | None:
    """Return an OpenAI-compatible client for xAI if XAI key present, else regular OpenAI.
    Returns None if no usable key.

    IMPORTANT: For this project you need the **Chat** key from the xAI console
    (Grok 4.3). That is the one that supports sending images for vision analysis.
    "Build", "Imagine", and "Voice" keys/products are not suitable here.
    """
    xai_key = os.getenv("XAI_API_KEY") or os.getenv("XAI_KEY")
    if xai_key:
        return OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key)

    return None


def _encode_image(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    # Most vision endpoints accept jpeg/png via data URL
    return f"data:image/jpeg;base64,{b64}"


def _build_extraction_prompt() -> str:
    return (
        "You are an expert TTB alcohol beverage label compliance reviewer.\n"
        "Carefully read the provided label image and extract the information into the exact JSON structure below.\n\n"
        "STEP 1: Identify the beverage type from visual cues, class/type text, design style, and wording.\n"
        "You MUST return exactly one of these three strings for 'beverage_type' (do not invent others, do not leave blank):\n"
        "- 'Distilled Spirits' (whiskey, vodka, gin, rum, tequila, brandy, etc.)\n"
        "- 'Wine' (table wine, sparkling, dessert, including qualifying ciders/meads)\n"
        "- 'Malt Beverage' (beer, ale, lager, stout, or flavored malt beverages)\n"
        "If uncertain from the image, choose the most likely based on the class/type text and overall label design.\n\n"
        "STEP 2: Extract fields. Only populate type-specific fields when they are visible and relevant; otherwise use empty string.\n\n"
        "Return ONLY a single valid JSON object (no markdown, no extra text) with these exact keys:\n"
        "{\n"
        '  "beverage_type": "Distilled Spirits or Wine or Malt Beverage",\n'
        '  "brand_name": "exact brand name text from the label",\n'
        '  "class_type": "the class and type designation exactly as printed (e.g. Kentucky Straight Bourbon Whiskey, India Pale Ale, Cabernet Sauvignon)",\n'
        '  "alcohol_content": "the full alcohol content statement as printed on the label",\n'
        '  "net_contents": "net contents exactly as shown",\n'
        '  "government_warning": "the COMPLETE government warning text visible on the label, including the header",\n'
        '  "bottler": "bottler or producer name and address if present, otherwise empty string",\n'
        '  "country_of_origin": "country of origin if shown, otherwise empty string",\n'
        '  "appellation_of_origin": "for Wine only: the appellation of origin if present, else empty",\n'
        '  "age_statement": "for Distilled Spirits only: any age statement if present, else empty",\n'
        '  "statement_of_composition": "for Malt Beverages or specialty products: any statement of composition if present, else empty",\n'
        '  "notes": "brief observations especially about the GOVERNMENT WARNING header casing, boldness, legibility, glare, angle, or any formatting issues you notice. Also note any type-specific elements you saw."\n'
        "}\n\n"
        "CRITICAL RULES FOR THE GOVERNMENT WARNING (applies to ALL types):\n"
        "- The header must be detected exactly. Note whether it says 'GOVERNMENT WARNING:' (all caps) or 'Government Warning:' (title case).\n"
        "- Extract the warning body as completely and accurately as possible.\n"
        "- If the warning is hard to read due to glare, angle, or small text, say so in the 'notes' field.\n\n"
        "Be as precise as possible. Do not invent text that is not visible. If a field is not present or not applicable to the detected type, use an empty string."
    )


def extract_from_image(
    image_bytes: bytes,
    filename: str = "uploaded.jpg",
    force_mock: bool = False,
) -> tuple[LabelData, str]:
    """Main extraction function used by the app.

    Returns (LabelData, notes_from_ai_or_mock)
    """
    start = time.time()

    if force_mock:
        # Use filename or a default mock
        key = _match_mock_key(filename)
        data = MOCK_EXTRACTIONS.get(key, MOCK_EXTRACTIONS["01_clean_old_tom"])
        time.sleep(0.6)  # simulate fast processing even in mock
        return LabelData(**{k: v for k, v in data.items() if k != "notes"}), data.get("notes", "")

    client = _get_client()
    if client is None:
        # No key available → fall back to mock gracefully
        key = _match_mock_key(filename)
        data = MOCK_EXTRACTIONS.get(key, MOCK_EXTRACTIONS["01_clean_old_tom"])
        return LabelData(**{k: v for k, v in data.items() if k != "notes"}), data.get("notes", "") + " (demo mode — no API key was found)"

    # Real vision call
    try:
        data_url = _encode_image(image_bytes)
        prompt = _build_extraction_prompt()

        response = client.chat.completions.create(
            model=XAI_VISION_MODEL if "x.ai" in str(client.base_url) else OPENAI_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=900,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "{}"
        parsed: dict[str, Any] = json.loads(raw)

        # Robust beverage_type detection: use what the model returned, or infer from class_type text
        # This helps when the vision model doesn't perfectly follow the "beverage_type" key on real photos.
        bev = parsed.get("beverage_type", "").strip()
        if not bev or bev not in ("Distilled Spirits", "Wine", "Malt Beverage"):
            ct = (parsed.get("class_type", "") or "").lower()
            if any(x in ct for x in ["whiskey", "vodka", "gin", "rum", "tequila", "brandy", "bourbon", "scotch", "spirit"]):
                bev = "Distilled Spirits"
            elif any(x in ct for x in ["wine", "cabernet", "merlot", "chardonnay", "pinot", "sparkling", "dessert"]):
                bev = "Wine"
            elif any(x in ct for x in ["beer", "ale", "lager", "stout", "porter", "ipa", "malt beverage"]):
                bev = "Malt Beverage"
            else:
                bev = "Distilled Spirits"  # safe default for most alcohol labels

        # Clean up and construct
        label = LabelData(
            beverage_type=bev,
            brand_name=parsed.get("brand_name", "").strip(),
            class_type=parsed.get("class_type", "").strip(),
            alcohol_content=parsed.get("alcohol_content", "").strip(),
            net_contents=parsed.get("net_contents", "").strip(),
            government_warning=parsed.get("government_warning", "").strip(),
            bottler=parsed.get("bottler", "").strip(),
            country_of_origin=parsed.get("country_of_origin", "").strip(),
            appellation_of_origin=parsed.get("appellation_of_origin", "").strip(),
            age_statement=parsed.get("age_statement", "").strip(),
            statement_of_composition=parsed.get("statement_of_composition", "").strip(),
        )
        notes = parsed.get("notes", "").strip()
        return label, notes

    except (OpenAIError, json.JSONDecodeError, KeyError) as e:
        # On any failure fall back to a reasonable mock so the demo never breaks
        key = _match_mock_key(filename)
        data = MOCK_EXTRACTIONS.get(key, MOCK_EXTRACTIONS["01_clean_old_tom"])
        return LabelData(**{k: v for k, v in data.items() if k != "notes"}), f"AI extraction had an error ({type(e).__name__}). Showing closest demo data."


def _match_mock_key(filename: str) -> str:
    """Heuristic to pick the best mock data based on uploaded filename."""
    name = filename.lower()
    if "title" in name or "02" in name:
        return "02_warning_titlecase"
    if "angle" in name or "stone" in name or "03" in name:
        return "03_angled_stones_throw"
    if "eagle" in name or "04" in name:
        return "04_eagle_ridge_clean"
    if "partial" in name or "05" in name:
        return "05_partial_old_tom"
    return "01_clean_old_tom"


def get_available_providers() -> str:
    """Human readable status for the sidebar."""
    if os.getenv("XAI_API_KEY") or os.getenv("XAI_KEY"):
        return "xAI Grok (primary)"
    if os.getenv("OPENAI_API_KEY"):
        return "OpenAI (fallback)"
    return "Demo / Mock mode only (no key detected)"
