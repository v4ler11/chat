import re

from typing import List, Literal

from pydantic import BaseModel, field_validator, Field


class Icon(BaseModel):
    src: str
    mimeType: str
    sizes: List[str] = Field(default_factory=list)

    @classmethod
    @field_validator('sizes')
    def validate_sizes(cls, v: List[str]) -> List[str]:
        pattern = re.compile(r'any|([1-9]\d*)x([1-9]\d*)')
        for size in v:
            if not pattern.fullmatch(size):
                raise ValueError(
                    f"Invalid size '{size}'. Must be 'any' or 'WIDTHxHEIGHT'."
                )
        return v

class Annotations(BaseModel):
    audience: List[Literal["user", "assistant"]] | None = None
    priority: float | None = Field(default=None, ge=0.0, le=1.0)
    lastModified: str | None = None
