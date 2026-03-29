from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    document_id: str
    title: str
    path: str
    text: str
    article_no: str | None = None
    chapter_title: str | None = None
    region: str | None = None
    promulgated_on: str | None = None
    effective_on: str | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conclusion: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    scope: str = ""
    uncertainty: str = ""


class ChatResponse(ModelAnswer):
    evidence: list[EvidenceItem] = Field(default_factory=list)
