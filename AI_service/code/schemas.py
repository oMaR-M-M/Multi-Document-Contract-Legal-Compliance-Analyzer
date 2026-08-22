from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict

#---------------------------------------------------
# For agent findings
#---------------------------------------------------
class ComplianceStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

Severity = Literal["HIGH", "MEDIUM", "LOW"]
#---------------------------------------------------


#---------------------------------------------------
# document page format
#---------------------------------------------------
class Page(BaseModel):
    page_number: int
    section_title: str
    text: str
#---------------------------------------------------


#---------------------------------------------------
# documnet format
#---------------------------------------------------
class Document(BaseModel):
    document_id: str
    filename: str
    document_type: str
    source: str | None = None
    pages: list[Page]
#---------------------------------------------------


#---------------------------------------------------
# Backend payload format
#---------------------------------------------------
class Payload(BaseModel):
    model_config = ConfigDict(extra="allow")
    documents: list[Document]
#---------------------------------------------------


#---------------------------------------------------
# requirement file format
#---------------------------------------------------
class RequirementList(BaseModel):
    requirements: list[str]
#---------------------------------------------------


#---------------------------------------------------
# Chunk format
#---------------------------------------------------
class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    document_type: str
    page_number: int
    section_title: str
    text: str
#---------------------------------------------------


#---------------------------------------------------
# Evidence format
#---------------------------------------------------
class Evidence(BaseModel):
    score: float
    metadata: Chunk
    text: str
#---------------------------------------------------


#---------------------------------------------------
# finding format
#---------------------------------------------------
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
#---------------------------------------------------


#---------------------------------------------------
# QueryIntent format
#---------------------------------------------------
class QueryIntent(BaseModel):
    is_requirement_check: bool
    target_doc_types: list[str]
#---------------------------------------------------


#---------------------------------------------------
# ComplianceReport(all findings) format
#---------------------------------------------------
class ComplianceReport(BaseModel):
    status: ComplianceStatus
    summary: str
    findings: list[Finding]
#---------------------------------------------------