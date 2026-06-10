"""Deterministic + intelligent comparison logic for alcohol label fields.

This module is pure Python (no AI calls) so it can run instantly for re-compare
after the user edits extracted values. It is the source of truth for pass/fail.
"""

from __future__ import annotations

import re
from rapidfuzz import fuzz
from src.models import (
    LabelData,
    FieldComparison,
    VerificationResult,
    ComparisonStatus,
    OFFICIAL_GOVERNMENT_WARNING,
    WARNING_REQUIRED_PHRASES,
)


def _normalize_text(text: str) -> str:
    """Lowercase + collapse whitespace for forgiving comparisons."""
    return " ".join(text.lower().split())


def _extract_abv_value(text: str) -> float | None:
    """Try to pull a numeric ABV percentage out of free text.
    Supports '45%', '45.0% Alc./Vol.', '90 Proof' (converts proof/2).
    """
    if not text:
        return None
    t = text.replace(",", ".")
    # Direct percentage
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", t)
    if m:
        return float(m.group(1))
    # Proof
    m = re.search(r"(\d+(?:\.\d+)?)\s*proof", t, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 2.0
    return None


def compare_brand(extracted: str, provided: str) -> FieldComparison:
    """Brand names allow fuzzy matching (Dave's nuance: STONE'S THROW vs Stone's Throw)."""
    ex = extracted.strip()
    pr = provided.strip()
    if not ex and not pr:
        return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="missing",
                               explanation="Both sides are empty.")
    if not ex:
        return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="missing",
                               explanation="No brand name detected on the label.")
    if not pr:
        return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="mismatch",
                               explanation="Application is missing the brand name.")

    # Exact after light normalization
    if _normalize_text(ex) == _normalize_text(pr):
        return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="exact",
                               explanation="Exact match (ignoring case and extra spaces).")

    # Fuzzy
    ratio = fuzz.token_sort_ratio(ex, pr)
    if ratio >= 85:
        return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="fuzzy",
                               explanation=f"Very close match (fuzzy similarity {ratio}%). Minor differences in casing, punctuation or wording are common and usually acceptable with human review.")
    if ratio >= 70:
        return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="fuzzy",
                               explanation=f"Close but worth a quick look (similarity {ratio}%).")
    return FieldComparison(field="Brand Name", extracted=ex, provided=pr, status="mismatch",
                           explanation=f"Significant difference between label and application (similarity only {ratio}%).")


def compare_class_type(extracted: str, provided: str) -> FieldComparison:
    ex, pr = extracted.strip(), provided.strip()
    if not ex and not pr:
        return FieldComparison(field="Class/Type", extracted=ex, provided=pr, status="missing", explanation="Both empty.")
    if not ex:
        return FieldComparison(field="Class/Type", extracted=ex, provided=pr, status="missing", explanation="Class/type not clearly readable on label.")
    if not pr:
        return FieldComparison(field="Class/Type", extracted=ex, provided=pr, status="mismatch", explanation="Application missing class/type designation.")

    if _normalize_text(ex) == _normalize_text(pr):
        return FieldComparison(field="Class/Type", extracted=ex, provided=pr, status="exact", explanation="Matches.")

    ratio = fuzz.token_sort_ratio(ex, pr)
    if ratio >= 80:
        return FieldComparison(field="Class/Type", extracted=ex, provided=pr, status="fuzzy",
                               explanation=f"Close match (fuzzy {ratio}%). Class/type wording can vary slightly.")
    return FieldComparison(field="Class/Type", extracted=ex, provided=pr, status="mismatch",
                           explanation="Does not match the submitted class/type.")


def compare_alcohol_content(extracted: str, provided: str) -> FieldComparison:
    ex, pr = extracted.strip(), provided.strip()
    if not ex and not pr:
        return FieldComparison(field="Alcohol Content", extracted=ex, provided=pr, status="missing", explanation="Both empty.")

    ex_val = _extract_abv_value(ex)
    pr_val = _extract_abv_value(pr)

    if ex_val is not None and pr_val is not None:
        # Allow small tolerance (e.g. rounding or proof vs %)
        if abs(ex_val - pr_val) < 0.6:
            return FieldComparison(field="Alcohol Content", extracted=ex, provided=pr, status="exact",
                                   explanation=f"Equivalent ({ex_val:.1f}% ABV on both sides).")
        else:
            return FieldComparison(field="Alcohol Content", extracted=ex, provided=pr, status="mismatch",
                                   explanation=f"Different strength: label shows ~{ex_val:.1f}% ABV, application shows ~{pr_val:.1f}% ABV.")

    # Fallback to string similarity if we couldn't parse numbers
    if _normalize_text(ex) == _normalize_text(pr):
        return FieldComparison(field="Alcohol Content", extracted=ex, provided=pr, status="exact", explanation="Text matches.")
    ratio = fuzz.ratio(ex, pr)
    if ratio > 75:
        return FieldComparison(field="Alcohol Content", extracted=ex, provided=pr, status="fuzzy", explanation="Close text match; verify the numbers manually.")
    return FieldComparison(field="Alcohol Content", extracted=ex, provided=pr, status="mismatch", explanation="Alcohol content statements do not match.")


def compare_net_contents(extracted: str, provided: str) -> FieldComparison:
    ex, pr = extracted.strip(), provided.strip()
    if not ex and not pr:
        return FieldComparison(field="Net Contents", extracted=ex, provided=pr, status="missing", explanation="Both empty.")
    if _normalize_text(ex) == _normalize_text(pr):
        return FieldComparison(field="Net Contents", extracted=ex, provided=pr, status="exact", explanation="Matches.")
    # Very forgiving on units (mL vs ML, L vs l)
    ex2 = re.sub(r"[^0-9a-z]", "", _normalize_text(ex))
    pr2 = re.sub(r"[^0-9a-z]", "", _normalize_text(pr))
    if ex2 and pr2 and ex2 == pr2:
        return FieldComparison(field="Net Contents", extracted=ex, provided=pr, status="exact", explanation="Matches (after normalizing spacing/punctuation).")
    return FieldComparison(field="Net Contents", extracted=ex, provided=pr, status="mismatch", explanation="Net contents do not match.")


def compare_government_warning(extracted: str, provided: str) -> FieldComparison:
    """Strict rules for the government warning (per Jenny's notes)."""
    ex = extracted.strip()
    pr = provided.strip()

    if not ex:
        return FieldComparison(field="Government Warning", extracted=ex, provided=pr, status="missing",
                               explanation="No government warning text was found on the label.")

    # 1. Header must be exactly "GOVERNMENT WARNING:" (all caps)
    header_ok = False
    header_match = re.search(r"(GOVERNMENT WARNING\s*:)", ex, re.IGNORECASE)
    if header_match:
        actual_header = header_match.group(1)
        if actual_header == "GOVERNMENT WARNING:":
            header_ok = True
        else:
            # Title case or other casing
            return FieldComparison(
                field="Government Warning",
                extracted=ex[:120] + ("..." if len(ex) > 120 else ""),
                provided=pr[:120] + ("..." if len(pr) > 120 else ""),
                status="mismatch",
                explanation="The header is not in the required all-caps format. It must read exactly 'GOVERNMENT WARNING:' (all capital letters, followed by a colon). Title case or lowercase is a common rejection reason."
            )

    if not header_ok:
        return FieldComparison(field="Government Warning", extracted=ex[:120]+"...", provided=pr[:120]+"...", status="mismatch",
                               explanation="Could not find the required 'GOVERNMENT WARNING:' header in all capital letters.")

    # 2. Check that the core required content is present
    ex_norm = _normalize_text(ex)
    missing_phrases = [p for p in WARNING_REQUIRED_PHRASES if p not in ex_norm]

    if missing_phrases:
        return FieldComparison(
            field="Government Warning",
            extracted=ex[:150] + ("..." if len(ex) > 150 else ""),
            provided=pr[:150] + ("..." if len(pr) > 150 else ""),
            status="mismatch",
            explanation="The warning is missing required content. The full two-sentence Surgeon General statement must appear."
        )

    # 3. Compare to the official text (allow the provided side to be the full official or very close)
    if _normalize_text(OFFICIAL_GOVERNMENT_WARNING) in ex_norm or _normalize_text(pr) in ex_norm or fuzz.token_sort_ratio(ex, OFFICIAL_GOVERNMENT_WARNING) > 90:
        return FieldComparison(field="Government Warning", extracted=ex[:120]+"...", provided=pr[:120]+"...", status="exact",
                               explanation="Header is correct all-caps and the required warning content is present.")

    # Still mostly good but not perfect match to official
    return FieldComparison(field="Government Warning", extracted=ex[:120]+"...", provided=pr[:120]+"...", status="fuzzy",
                           explanation="Header casing is correct and key phrases are present, but the exact wording differs slightly from the official TTB statement. Human review recommended.")


def compare_optional(field_name: str, extracted: str, provided: str) -> FieldComparison:
    ex, pr = extracted.strip(), provided.strip()
    if not ex and not pr:
        return FieldComparison(field=field_name, extracted=ex, provided=pr, status="exact", explanation="Not provided on either side (optional for this prototype).")
    if not ex:
        return FieldComparison(field=field_name, extracted=ex, provided=pr, status="missing", explanation=f"{field_name} not detected on label.")
    if not pr:
        return FieldComparison(field=field_name, extracted=ex, provided=pr, status="fuzzy", explanation=f"{field_name} appears on label but was not entered in the application.")
    if _normalize_text(ex) == _normalize_text(pr):
        return FieldComparison(field=field_name, extracted=ex, provided=pr, status="exact", explanation="Matches.")
    return FieldComparison(field=field_name, extracted=ex, provided=pr, status="fuzzy", explanation="Slight differences — usually acceptable for optional fields.")


def compare_label_data(extracted: LabelData, provided: LabelData) -> list[FieldComparison]:
    """Run all field comparisons. Order matters for display."""
    results: list[FieldComparison] = []
    results.append(compare_brand(extracted.brand_name, provided.brand_name))
    results.append(compare_class_type(extracted.class_type, provided.class_type))
    results.append(compare_alcohol_content(extracted.alcohol_content, provided.alcohol_content))
    results.append(compare_net_contents(extracted.net_contents, provided.net_contents))
    results.append(compare_government_warning(extracted.government_warning, provided.government_warning))
    results.append(compare_optional("Bottler / Producer", extracted.bottler, provided.bottler))
    results.append(compare_optional("Country of Origin", extracted.country_of_origin, provided.country_of_origin))
    return results


def compute_overall_status(field_results: list[FieldComparison]) -> str:
    """Simple but effective overall status."""
    has_mismatch = any(r.status == "mismatch" for r in field_results)
    has_missing_critical = any(r.status == "missing" and r.field in ("Brand Name", "Government Warning") for r in field_results)

    if has_mismatch or has_missing_critical:
        return "FAIL"
    if any(r.status in ("fuzzy", "missing") for r in field_results):
        return "NEEDS REVIEW"
    return "PASS"


def verify(extracted: LabelData, provided: LabelData, processing_time: float = 0.0, notes: str = "") -> VerificationResult:
    """Main entry point used by the UI (and by the AI extraction layer)."""
    field_results = compare_label_data(extracted, provided)
    overall = compute_overall_status(field_results)
    return VerificationResult(
        overall_status=overall,
        field_results=field_results,
        processing_time_seconds=round(processing_time, 2),
        notes=notes,
    )
