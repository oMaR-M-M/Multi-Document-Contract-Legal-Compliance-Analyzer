"""
Single source of truth for every data shape used across backend,
ai_service, and (indirectly) the frontend's JSON contract.

Previously this project had TWO different `Payload`/`Document` classes
defined independently (one in Back-end/schemas.py, one in
AI_service/code/schemas.py) that happened to look similar and were
used interchangeably by duck-typing. That's fragile: if one drifts
from the other, you get confusing runtime errors instead of a clear
import error. This module removes that duplication.
"""
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------
# Compliance enums
# ---------------------------------------------------
class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


Severity = Literal["HIGH", "MEDIUM", "LOW"]


# ---------------------------------------------------
# Parsed document format (produced by backend/pdf_parser.py)
# ---------------------------------------------------
class Page(BaseModel):
    page_number: int
    section_title: str
    text: str


class Document(BaseModel):
    document_id: str
    filename: str
    document_type: str
    source: str | None = None
    pages: list[Page]


# ---------------------------------------------------
# Backend request payload (files + prompt, sent to /analyze)
# ---------------------------------------------------
class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str
    documents: list[Document]


# ---------------------------------------------------
# Chunk format (produced by ai_service/code/chunking.py)
# ---------------------------------------------------
class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    document_type: str
    page_number: int
    section_title: str
    text: str


# ---------------------------------------------------
# Retrieval evidence format
# ---------------------------------------------------
class Evidence(BaseModel):
    score: float
    metadata: Chunk
    text: str


# ---------------------------------------------------
# Query routing format
# ---------------------------------------------------
class QueryIntent(BaseModel):
    is_requirement_check: bool
    target_doc_types: list[str]


# ---------------------------------------------------
# LLM output: one finding per requirement
# ---------------------------------------------------
class Finding(BaseModel):
    finding_id: str
    severity: Severity
    status: ComplianceStatus
    requirement: str
    document: str
    page: int
    section: str
    evidence: str
    analysis: str
    recommendation: str


# ---------------------------------------------------
# LLM output: full report (this is what /analyze returns)
# ---------------------------------------------------
class ComplianceReport(BaseModel):
    status: ComplianceStatus
    summary: str
    findings: list[Finding]


# ---------------------------------------------------
# Legacy helper (kept for any code still expecting a plain list wrapper)
# ---------------------------------------------------
class RequirementList(BaseModel):
    requirements: list[str]
