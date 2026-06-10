"""Pydantic data models for the alcohol label verification app."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal

ComparisonStatus = Literal["exact", "fuzzy", "mismatch", "missing"]


class LabelData(BaseModel):
    """Structured data extracted from (or entered for) an alcohol label / application."""

    beverage_type: str = Field(
        default="",
        description="Detected beverage type: 'Distilled Spirits', 'Wine', or 'Malt Beverage'"
    )
    brand_name: str = Field(default="", description="Brand name as it appears")
    class_type: str = Field(default="", description="Class and type designation (e.g. Kentucky Straight Bourbon Whiskey, India Pale Ale, Cabernet Sauvignon)")
    alcohol_content: str = Field(default="", description="Alcohol content statement as printed (e.g. '45% Alc./Vol. (90 Proof)')")
    net_contents: str = Field(default="", description="Net contents (e.g. '750 mL', '1.75 L')")
    government_warning: str = Field(default="", description="The full government health warning statement")
    bottler: str = Field(default="", description="Name and address of bottler/producer/importer (optional for prototype)")
    country_of_origin: str = Field(default="", description="Country of origin if imported (optional)")

    # Type-specific (populated by AI when relevant, otherwise empty)
    appellation_of_origin: str = Field(default="", description="For Wine: appellation of origin if present")
    age_statement: str = Field(default="", description="For Distilled Spirits: age statement if present")
    statement_of_composition: str = Field(default="", description="For Malt Beverages or specialties: statement of composition")

    @classmethod
    def empty(cls) -> "LabelData":
        return cls()

    def has_minimum_data(self) -> bool:
        return bool(self.brand_name.strip() and self.government_warning.strip())


class FieldComparison(BaseModel):
    """Result of comparing one field between extracted label and submitted application."""

    field: str
    extracted: str
    provided: str
    status: ComparisonStatus
    explanation: str = ""
    # For future: confidence: float | None = None


class VerificationResult(BaseModel):
    """Full verification outcome for one label."""

    overall_status: Literal["PASS", "NEEDS REVIEW", "FAIL"]
    field_results: list[FieldComparison]
    processing_time_seconds: float = 0.0
    notes: str = ""  # e.g. from AI about image quality or formatting observations


# The exact required U.S. Government Warning statement (TTB)
OFFICIAL_GOVERNMENT_WARNING: str = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink "
    "alcoholic beverages during pregnancy because of the risk of birth defects. (2) "
    "Consumption of alcoholic beverages impairs your ability to drive a car or operate "
    "machinery, and may cause health problems."
)

# Keywords that must appear for a minimally acceptable warning
WARNING_REQUIRED_PHRASES = [
    "according to the surgeon general",
    "women should not drink alcoholic beverages during pregnancy",
    "risk of birth defects",
    "impairs your ability to drive a car or operate machinery",
    "may cause health problems",
]
