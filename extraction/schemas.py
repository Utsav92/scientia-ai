from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

EntityType = Literal["METHOD", "MODEL", "ALGORITHM", "DATASET", "METRIC", "MATERIAL", "CHEMICAL", "BIOLOGICAL_ENTITY",
                     "BIOLOGICAL_DATA", "PHYSICAL_QUANTITY", "EXPERIMENTAL_CONDITION", "TASK"]


class Entity(BaseModel):
    text: str                        # surface form exactly as in the source
    type: EntityType
    canonical: str                   # normalised id used for graph merging
    char_start: int | None = None
    char_end: int | None = None
    source: str = "rules"            # rules | llm


class Evidenced(BaseModel):
    """A statement that is only kept if `quote` is a verbatim span of the source text."""
    text: str
    quote: str
    chunk_ids: list[str] = Field(default_factory=list)


class PaperExtraction(BaseModel):
    paper_id: str
    method: str = "rules"
    research_question: Evidenced | None = None
    hypothesis: Evidenced | None = None
    methodology: Evidenced | None = None
    datasets: list[Evidenced] = Field(default_factory=list)
    findings: list[Evidenced] = Field(default_factory=list)
    quantitative_results: list[Evidenced] = Field(default_factory=list)
    limitations: list[Evidenced] = Field(default_factory=list)
    future_work: list[Evidenced] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    supporting_chunk_ids: list[str] = Field(default_factory=list)
    dropped_ungrounded: int = 0      # LLM items rejected because the quote/entity was not in the source
