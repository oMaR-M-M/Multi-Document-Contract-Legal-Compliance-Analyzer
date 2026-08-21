from fastapi import FastAPI, File, UploadFile, Form
from schemas import Payload
from pdf_parser import build_payload
app = FastAPI()

@app.get("/")
def home():
    return {"message": "API is working"}

@app.post("/analyze")
async def analyze(

    files: list[UploadFile] = File(...),
    prompt: str = Form(...)
):

    payload = await build_payload(files, prompt)

    print("\n========== PAYLOAD ==========")
    print(payload.model_dump_json(indent=2))
    print("=============================\n")

    return {
        "message": "Files processed successfully"
    }