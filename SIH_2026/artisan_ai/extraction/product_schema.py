"""
artisan_ai.extraction.product_schema
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pydantic v2 schemas for structured product fact extraction.

Design principles
-----------------
* Every field uses an :class:`EvidencedField` wrapper so downstream
  validation can trace any generated claim back to the artisan's words.
* ``status`` uses a controlled vocabulary instead of a bare float so the
  meaning is unambiguous:
    - ``"supported"``  – artisan explicitly stated this.
    - ``"uncertain"``  – artisan hinted at this but was not explicit.
    - ``"missing"``    – artisan never mentioned this field.
* ``None`` at the top level means the field was not mentioned at all and
  no EvidencedField wrapper was created.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Evidence wrapper ──────────────────────────────────────────────────────────

class EvidencedField(BaseModel):
    """A single extracted product attribute with provenance.

    Attributes
    ----------
    value:
        The extracted value.  Can be a string, list, or number depending
        on the field.
    status:
        ``"supported"`` | ``"uncertain"`` | ``"missing"``
    evidence:
        The verbatim or paraphrased portion of the artisan's translated
        statement that supports this value.
    """

    value: str | list[str] | float | None
    status: Literal["supported", "uncertain", "missing"] = "supported"
    evidence: str = ""


# ── Product facts ─────────────────────────────────────────────────────────────

class ProductFacts(BaseModel):
    """Structured product facts extracted from the artisan's statement.

    All fields are Optional.  A value of ``None`` means the artisan did
    not mention that attribute.  Extractors MUST NOT infer values from
    domain knowledge; only information explicitly present in the
    artisan's words should be extracted.
    """

    product_name: Optional[EvidencedField] = Field(
        default=None,
        description="Name of the product (e.g. 'Phulkari Dupatta').",
    )
    category: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "Broad product category: Clothing, Handicraft, Jewelry, "
            "Furniture, Pottery, Textile, or similar."
        ),
    )
    subcategory: Optional[EvidencedField] = Field(
        default=None,
        description="Narrower product sub-type (e.g. 'Dupatta', 'Shawl').",
    )
    material: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "Material(s) used. value should be a list of strings. "
            "Do NOT infer material from product type."
        ),
    )
    colors: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "Color(s) mentioned. value should be a list of strings. "
            "Do NOT infer colors."
        ),
    )
    dimensions: Optional[EvidencedField] = Field(
        default=None,
        description="Size or dimensions (e.g. '2.5 metres × 1 metre').",
    )
    weight: Optional[EvidencedField] = Field(
        default=None,
        description="Weight of the product (e.g. '250 grams').",
    )
    craft_type: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "High-level craft classification (e.g. 'Handmade', 'Machine-made')."
        ),
    )
    craft_technique: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "Specific craft or embroidery technique "
            "(e.g. 'Phulkari embroidery', 'Block printing')."
        ),
    )
    production_method: Optional[EvidencedField] = Field(
        default=None,
        description="How the product is made (e.g. 'Handmade', 'Hand-woven').",
    )
    region: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "Geographic origin stated by the artisan. "
            "Do NOT infer region from craft type."
        ),
    )
    production_time: Optional[EvidencedField] = Field(
        default=None,
        description="Time taken to make the product (e.g. '3 days').",
    )
    usage: Optional[EvidencedField] = Field(
        default=None,
        description="Stated purpose or usage of the product.",
    )
    cultural_significance: Optional[EvidencedField] = Field(
        default=None,
        description=(
            "Cultural or historical significance ONLY if explicitly stated "
            "by the artisan."
        ),
    )
    care_instructions: Optional[EvidencedField] = Field(
        default=None,
        description="Care or washing instructions if mentioned.",
    )

    def get_category_str(self) -> str:
        """Return category value as a plain string, or empty string."""
        if self.category and self.category.value:
            v = self.category.value
            return v if isinstance(v, str) else str(v)
        return ""

    def to_flat_dict(self) -> dict:
        """Return a simplified {field: value} dict for downstream use."""
        result: dict = {}
        for field_name, evidenced in self.__dict__.items():
            if evidenced is None:
                result[field_name] = None
            elif isinstance(evidenced, EvidencedField):
                result[field_name] = evidenced.value
            else:
                result[field_name] = evidenced
        return result

    def to_evidence_dict(self) -> dict:
        """Return the full evidence-annotated dict."""
        result: dict = {}
        for field_name, evidenced in self.__dict__.items():
            if evidenced is None:
                result[field_name] = None
            elif isinstance(evidenced, EvidencedField):
                result[field_name] = evidenced.model_dump()
            else:
                result[field_name] = evidenced
        return result


# ── Listing output schema ─────────────────────────────────────────────────────

class ProductListing(BaseModel):
    """Generated e-commerce product listing."""

    title: str = Field(description="Short, specific product title (max 80 chars).")
    short_description: str = Field(
        description="One-sentence product summary (max 150 chars)."
    )
    description: str = Field(
        description=(
            "Professional 2–4 paragraph product description. "
            "Use only information present in product facts."
        )
    )
    highlights: list[str] = Field(
        default_factory=list,
        description="Up to 6 bullet-point highlights. Each grounded in product facts.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="SEO keywords (product name, material, craft technique, etc.).",
    )


# ── Follow-up question schema ─────────────────────────────────────────────────

class FollowUpQuestion(BaseModel):
    """A single follow-up question for the artisan."""

    field: str = Field(description="The product fact field this question targets.")
    question_en: str = Field(description="The question in English.")
    question_local: str = Field(
        default="",
        description="The question translated into the artisan's detected language.",
    )


# ── Validation result schema ──────────────────────────────────────────────────

class ValidationResult(BaseModel):
    """Result of the factual validation stage."""

    valid: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    notes: str = ""
