import os
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------
# Load the ONE .env file at the project root, using an explicit
# absolute path instead of relying on the current working directory.
#
# This is the actual root cause of "it worked in my demo but not
# when the API runs it": load_dotenv() with no arguments searches
# upward from the CURRENT WORKING DIRECTORY, not from this file's
# location. That happened to match when someone ran demo.py directly
# from inside ai_service/code/, but broke when uvicorn launches the
# app from the project root instead. Resolving the path from
# __file__ makes this work identically no matter how or from where
# the app is started.
# ---------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[2]  # ai_service/code -> ai_service -> project root
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
