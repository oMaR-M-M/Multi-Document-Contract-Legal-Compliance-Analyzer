from pydantic import BaseModel, ConfigDict

class Page(BaseModel):
    page_number: int
    section_title: str
    text: str

class Document(BaseModel):
    document_id: str
    filename: str
    document_type: str
    pages: list[Page]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str
    documents: list[Document]