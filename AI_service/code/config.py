import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "openai/gpt-oss-20b")

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

