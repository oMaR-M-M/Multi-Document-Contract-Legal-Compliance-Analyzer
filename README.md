# Multi-Document Contract & Legal Compliance Analyzer

An enterprise document audit agent that ingests multiple agreements
(e.g., NDAs, Terms of Service, and Privacy Policies) and conducts
cross-document compliance assessments using RAG, multi-hop retrieval,
metadata routing, and automated claim verification.

## Project structure

```
.
├── backend/        FastAPI service: receives uploads, parses PDFs, calls the AI service
├── ai_service/      RAG pipeline: chunking, embeddings, retrieval, LLM reasoning (Groq)
├── frontend/        Static HTML/JS client (served separately, e.g. VS Code Live Server)
├── shared/          Pydantic schemas shared by backend and ai_service (single source of truth)
├── examples/        Sample PDFs for manual testing
├── .env.example     Template for required environment variables
└── requirements.txt
```

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in a valid `GROQ_API_KEY`
   (get one at https://console.groq.com). **Never commit `.env`.**
3. Run the backend from the **project root**:
   ```bash
   uvicorn backend.main:app --reload
   ```
4. Serve `frontend/index.html` with a static server (e.g. VS Code's
   Live Server extension on port 5500) and open it in the browser.
   If you serve it from a different origin, update `allow_origins`
   in `backend/main.py` accordingly.

## Notes

- All request/response schemas live in `shared/schemas.py` — both
  `backend` and `ai_service` import from there, so there is exactly
  one definition of `Payload`, `Document`, etc.
- `ai_service/code/config.py` loads `.env` from the project root
  using an absolute path, so it works the same whether you run the
  API with uvicorn or run `ai_service/code/demo.py` directly.
