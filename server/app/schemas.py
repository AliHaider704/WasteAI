# File: server/app/schemas.py
"""Pydantic models matching the frozen contract (ARCHITECTURE sections 3-4)."""
from typing import Literal

from pydantic import BaseModel, Field

Bin = Literal["blue", "green", "yellow", "red", "black", "brown", "grey", "special"]


class CategoryScore(BaseModel):
    id: str
    name: str
    group: str | None = None
    confidence: float = Field(ge=0, le=1)


class Guidance(BaseModel):
    bin: Bin
    summary: str
    steps: list[str]
    warnings: list[str]


class SourceLabel(BaseModel):
    label: str
    score: float


class SourceResult(BaseModel):
    name: str
    ok: bool
    top: list[SourceLabel] = Field(default_factory=list, max_length=3)


class ClassifyResponse(BaseModel):
    request_id: str
    status: Literal["ok", "uncertain"]
    category: CategoryScore | None
    alternatives: list[CategoryScore] = Field(max_length=2)
    agreement: Literal["full", "partial", "none", "single_source"]
    hazard: bool
    guidance: Guidance | None
    sources: list[SourceResult]
    elapsed_ms: int


class CategoryItem(BaseModel):
    id: str
    name: str
    group: str
    bin: str
    icon: str
    summary: str
    steps: list[str]
    warnings: list[str]


class CategoriesResponse(BaseModel):
    version: int = 1
    categories: list[CategoryItem]


class FeedbackBody(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    correct_category_id: str = Field(min_length=1, max_length=64)


class HealthSources(BaseModel):
    local_onnx: Literal["up", "down"]
    azure: Literal["up", "quota", "disabled", "down"]
    reciclapi: Literal["up", "disabled", "down"]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    sources: HealthSources
