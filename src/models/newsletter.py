"""
Pydantic models for newsletter data structures.
Provides type safety and validation for newsletter content.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class NewsletterItem(BaseModel):
    """Single item in a newsletter."""

    title: str = Field(..., description="Item title")
    url: str = Field(..., description="Source URL")
    summary: str = Field(..., description="Item summary/description")
    category: str = Field(..., description="Content category (research, product, funding, etc.)")
    source: str = Field(..., description="Content source (arxiv, huggingface, etc.)")
    relevance_score: int = Field(ge=1, le=10, description="Relevance score 1-10")
    published_date: datetime | None = Field(None, description="Original publication date")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Normalize category to lowercase."""
        return v.lower().strip()

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Normalize source to lowercase."""
        return v.lower().strip()


class Newsletter(BaseModel):
    """Complete newsletter structure."""

    date: str = Field(..., description="Newsletter date in format: YYYY-MM-DD-HH")
    items: list[NewsletterItem] = Field(..., description="Newsletter items")
    summary: str = Field(default="", description="Newsletter summary")
    item_count: int = Field(..., description="Number of items")

    @field_validator("item_count")
    @classmethod
    def validate_item_count(cls, v: int, info) -> int:
        """Validate that item_count matches actual items length."""
        items = info.data.get("items", [])
        if v != len(items):
            raise ValueError(f"item_count {v} doesn't match items length {len(items)}")
        return v

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date format is YYYY-MM-DD-HH."""
        parts = v.split("-")
        if len(parts) != 4:
            raise ValueError(f"Date must be in format YYYY-MM-DD-HH, got: {v}")

        # Validate year, month, day, hour are numeric
        try:
            _, month, day, hour = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            if not (1 <= month <= 12):
                raise ValueError(f"Month must be 1-12, got: {month}")
            if not (1 <= day <= 31):
                raise ValueError(f"Day must be 1-31, got: {day}")
            if not (0 <= hour <= 23):
                raise ValueError(f"Hour must be 0-23, got: {hour}")
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid date format: {v}. Error: {str(e)}") from e

        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Newsletter":
        """Create Newsletter from dictionary."""
        return cls(**data)
