import re
import unicodedata
from io import BytesIO
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from pypdf import PdfReader
from schemas import Payload, Document, Page

app = FastAPI()

def normalize_text(raw_text: str) -> str:
    text = re.sub(r"[ \t]+", " ", raw_text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()

def make_document_id(filename: str) -> str:
    name, _ = filename.rsplit(".", 1)
    return name.lower()

def get_document_type(filename: str) -> str:
    name = Path(filename).stem.lower()

    if "privacy" in name:
        return "privacy_policy"

    if "terms" in name or "tos" in name:
        return "terms_of_service"

    if "nda" in name:
        return "nda"

    return "unknown"


async def process_pdf(file: UploadFile) -> Document:

    pdf_bytes = await file.read()

    reader = PdfReader(BytesIO(pdf_bytes))

    pages = []

    for page_number, pdf_page in enumerate(reader.pages,start=1):

        extracted_text = pdf_page.extract_text() or ""

        normalized_text = normalize_text(extracted_text)

        pages.append(
            Page(
                page_number=page_number,
                section_title="",
                text=normalized_text,
            )
        )

    return Document(
        document_id = make_document_id(file.filename),
        filename=file.filename,
        document_type = get_document_type(file.filename),
        pages=pages,
    )

async def build_payload(files: list[UploadFile]) -> Payload:
    documents = []
    for file in files:
        document = await process_pdf(file)
        documents.append(document)

    payload = Payload(
        documents=documents
    )
    return payload

@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):

    payload = await build_payload(files)

    return payload.model_dump(mode="json")

