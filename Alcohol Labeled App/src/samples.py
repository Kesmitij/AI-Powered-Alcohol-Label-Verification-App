"""Sample label data and helpers for the demo.

Includes:
- References to the real AI-generated label photos in samples/
- Ground-truth "extracted" data that the mock mode and Load Sample buttons use.
- A small PIL-based generator that can create additional placeholder labels if needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from PIL import Image, ImageDraw, ImageFont
from src.models import LabelData, OFFICIAL_GOVERNMENT_WARNING


SAMPLES_DIR = Path(__file__).parent.parent / "samples"


class SampleDef(NamedTuple):
    key: str
    display_name: str
    image_filename: str
    extracted: LabelData
    # Optional: a slightly different "submitted" version to demonstrate mismatches on load
    submitted_override: LabelData | None = None


# Ground truth data that matches the 5 generated images.
# These are also used as the "AI would return this" when in mock mode.
SAMPLES: list[SampleDef] = [
    SampleDef(
        key="01_clean_old_tom",
        display_name="01 - Clean OLD TOM (perfect match demo)",
        image_filename="01_clean_old_tom.jpg",
        extracted=LabelData(
            beverage_type="Distilled Spirits",
            brand_name="OLD TOM DISTILLERY",
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            government_warning=OFFICIAL_GOVERNMENT_WARNING,
            bottler="Old Tom Distillery, Louisville, KY",
        ),
    ),
    SampleDef(
        key="02_warning_titlecase",
        display_name="02 - Title case warning (should FAIL strict check)",
        image_filename="02_warning_titlecase.jpg",
        extracted=LabelData(
            beverage_type="Distilled Spirits",
            brand_name="OLD TOM DISTILLERY",
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            government_warning="Government Warning: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.",
        ),
        # Submitted version is correct (to show the mismatch is on the label side)
        submitted_override=LabelData(
            brand_name="OLD TOM DISTILLERY",
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            government_warning=OFFICIAL_GOVERNMENT_WARNING,
        ),
    ),
    SampleDef(
        key="03_angled_stones_throw",
        display_name="03 - Angled 'STONE'S THROW' (fuzzy brand test)",
        image_filename="03_angled_stones_throw.jpg",
        extracted=LabelData(
            beverage_type="Distilled Spirits",
            brand_name="STONE'S THROW",
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="90 Proof",
            net_contents="750 mL",
            government_warning=OFFICIAL_GOVERNMENT_WARNING,
        ),
        # Submitted with slightly different casing / spelling to demo fuzzy
        submitted_override=LabelData(
            brand_name="Stones Throw",
            class_type="Kentucky Straight Bourbon Whiskey",
            alcohol_content="45% Alc./Vol. (90 Proof)",
            net_contents="750 mL",
            government_warning=OFFICIAL_GOVERNMENT_WARNING,
        ),
    ),
    SampleDef(
        key="04_eagle_ridge_clean",
        display_name="04 - Eagle Ridge 100 Proof (different numbers)",
        image_filename="04_eagle_ridge_clean.jpg",
        extracted=LabelData(
            beverage_type="Distilled Spirits",
            brand_name="EAGLE RIDGE DISTILLING CO.",
            class_type="Straight Rye Whiskey",
            alcohol_content="50% Alc./Vol. (100 Proof)",
            net_contents="1.75 L",
            government_warning=OFFICIAL_GOVERNMENT_WARNING,
            bottler="Eagle Ridge Distilling Co., Portland, OR",
        ),
    ),
    SampleDef(
        key="05_partial_old_tom",
        display_name="05 - Challenging photo (partial extraction)",
        image_filename="05_partial_old_tom.jpg",
        extracted=LabelData(
            beverage_type="Distilled Spirits",
            brand_name="OLD TOM",
            class_type="Bourbon Whiskey",
            alcohol_content="90 Proof",
            net_contents="750ml",
            government_warning="GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.",
        ),
    ),
]


def get_sample_image_bytes(sample: SampleDef) -> bytes | None:
    path = SAMPLES_DIR / sample.image_filename
    if path.exists():
        return path.read_bytes()
    return None


def get_sample_by_key(key: str) -> SampleDef | None:
    for s in SAMPLES:
        if s.key == key:
            return s
    return None


def list_sample_display_names() -> list[str]:
    return [s.display_name for s in SAMPLES]


def get_sample_from_display_name(name: str) -> SampleDef | None:
    for s in SAMPLES:
        if s.display_name == name:
            return s
    return None


# ---------------------------------------------------------------------------
# Optional: simple PIL label generator (used if user wants more demo images)
# This runs on the user's machine after they pip install the requirements.
# ---------------------------------------------------------------------------

def generate_simple_placeholder_label(
    brand: str = "DEMO DISTILLERY",
    class_type: str = "Kentucky Straight Bourbon Whiskey",
    abv: str = "45% Alc./Vol. (90 Proof)",
    net: str = "750 mL",
    warning_header_all_caps: bool = True,
    output_path: Path | None = None,
) -> bytes:
    """Create a very basic but usable synthetic label image using Pillow.

    Useful for quick additional test cases without needing the image gen tool.
    """
    width, height = 900, 1200
    img = Image.new("RGB", (width, height), color="#F5F0E6")
    draw = ImageDraw.Draw(img)

    # Try to use a decent font, fall back to default
    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        body_font = ImageFont.truetype("arial.ttf", 28)
        small_font = ImageFont.truetype("arial.ttf", 20)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Simple "label" border
    draw.rectangle([40, 40, width-40, height-40], outline="#3C2F2F", width=4)

    y = 80
    draw.text((width // 2, y), brand.upper(), fill="#1a1a1a", font=title_font, anchor="mt")
    y += 80
    draw.text((width // 2, y), class_type, fill="#333", font=body_font, anchor="mt")
    y += 70
    draw.text((width // 2, y), abv, fill="#222", font=body_font, anchor="mt")
    y += 55
    draw.text((width // 2, y), net, fill="#222", font=body_font, anchor="mt")

    y += 120
    header = "GOVERNMENT WARNING:" if warning_header_all_caps else "Government Warning:"
    draw.text((width // 2, y), header, fill="#8B0000", font=body_font, anchor="mt")
    y += 45

    warning_lines = [
        "(1) According to the Surgeon General, women should not drink",
        "alcoholic beverages during pregnancy because of the risk",
        "of birth defects.",
        "",
        "(2) Consumption of alcoholic beverages impairs your ability",
        "to drive a car or operate machinery, and may cause health",
        "problems.",
    ]
    for line in warning_lines:
        draw.text((width // 2, y), line, fill="#222", font=small_font, anchor="mt")
        y += 28

    if output_path:
        img.save(output_path)

    # Return bytes
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.getvalue()


def create_demo_placeholder_images(target_dir: Path = SAMPLES_DIR) -> list[Path]:
    """Generate a couple of extra simple labels on disk (for variety)."""
    target_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for i, (brand, abv) in enumerate([
        ("RIVER BEND", "42% Alc./Vol. (84 Proof)"),
        ("HIGHLAND OAK", "50% Alc./Vol. (100 Proof)"),
    ], start=10):
        data = generate_simple_placeholder_label(
            brand=brand,
            abv=abv,
            warning_header_all_caps=(i % 2 == 0),
        )
        p = target_dir / f"demo_{i}.jpg"
        p.write_bytes(data)
        created.append(p)
    return created
