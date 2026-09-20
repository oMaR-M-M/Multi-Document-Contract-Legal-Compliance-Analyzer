import json

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware

from ai_service.code.pipeline import analyse
from .pdf_parser import build_payload

app = FastAPI(title="Multi-Document Contract & Legal Compliance Analyzer")

# In development, the frontend is served by VS Code's Live Server on
# 127.0.0.1:5500. Update this if the frontend is served from elsewhere.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "API is working"}


@app.post("/analyze")
async def analyze(
    files: list[UploadFile] = File(...),
    prompt: str = Form(...),
):
    payload = await build_payload(files, prompt)
    report = analyse(query=prompt, files=payload)

    print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
    return report.model_dump()
