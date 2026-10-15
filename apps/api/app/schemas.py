from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class JobAccepted(BaseModel):
    job_id: str
    status: str = "queued"
    poll_after_ms: int = 1500


class Candidate(BaseModel):
    title_id: str
    title: str
    original_title: str | None = None
    kind: str = "unknown"
    year: int | None = None
    synopsis: str | None = None
    genres: list[str] = Field(default_factory=list)
    poster_url: str | None = None
    rating: dict = Field(default_factory=lambda: {"value": None, "source": None})
    external_url: str | None = None
    provider: str | None = None
    attribution: str | None = None
    score: float = Field(ge=0, le=1)
    confidence: Literal["high", "medium", "low"]
    evidence: dict[str, float] = Field(default_factory=dict)
    episode: int | str | None = None
    timestamp_s: float | None = None
    preview_url: str | None = None


class IdentificationResult(BaseModel):
    band: Literal["high", "medium", "low", "none"] = "none"
    margin: float = 0.0
    scene_caption: str | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    signals_used: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    visual_method: str | None = None
    message: str | None = None


class JobStatus(BaseModel):
    id: str
    status: Literal["queued", "processing", "done", "failed"]
    progress: int = 0
    result: IdentificationResult | None = None
    error: str | None = None
    created_at: str
    finished_at: str | None = None


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    job_id: str = Field(min_length=36, max_length=36)
    predicted_title_id: str | None = Field(default=None, max_length=128)
    correct_title_id: str | None = Field(default=None, max_length=128)
    verdict: Literal["correct", "wrong", "unknown"]
    note: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(BaseModel):
    id: int
    accepted: bool = True


class TakedownCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    source_url: HttpUrl
    reason: str = Field(min_length=10, max_length=2000)
    contact_email: str | None = Field(default=None, max_length=320)
