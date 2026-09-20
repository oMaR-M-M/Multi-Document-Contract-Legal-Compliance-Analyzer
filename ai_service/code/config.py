import os
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# ai_service/code -> ai_service -> project root
ROOT_DIR = Path(__file__).resolve().parents[2]  
load_dotenv(ROOT_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not set. Copy .env.example to .env at the "
        "project root and fill in a valid key."
    )

# Chunk_file variables
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# Embedding_file variables
Embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


# Reasoning_file variables
from langchain_groq import ChatGroq

llm = ChatGroq(
    model=MODEL_NAME,
    temperature=0,
    api_key=GROQ_API_KEY,
    max_tokens=4096,
)


# pipeline_file variables
REQUIREMENTS_TYPE = "compliance_requirements"

TARGET_TYPES = (
    "privacy_policy",
    "vendor_nda",
    "terms_of_services",
)

# Batches for sending to the llm
REQUIREMENTS_BATCH_SIZE = 3

# Dimension of the embeddings
dim = 384

REQ_PREFIX_TO_DOC = {
    "2": "vendor_nda",
    "3": "terms_of_services",
    "4": "privacy_policy",
}

MIN_REQ_SCORE = 0.25
REQ_REL_SCORE = 0.70

USE_CHAT_HISTORY = False
DEBUG_RETRIEVAL = False