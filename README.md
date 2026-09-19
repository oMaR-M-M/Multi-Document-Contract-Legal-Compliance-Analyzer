# Multi-Document Contract & Legal Compliance Analyzer

---

## 1. Project Description

An enterprise document audit agent that ingests multiple legal agreements — NDAs, Terms of Service, and Privacy Policies — and audits them against a central compliance requirements document.

Reviewing contracts for compliance is slow and error-prone. A requirement like *"all customer data must be encrypted at rest using AES-256"* lives in one document, while the clause that satisfies (or violates) it lives somewhere in a completely different contract. Finding those connections by hand means reading every document and holding all the rules in your head at once.

This system automates that cross-document comparison. You give it a question, it figures out which requirements are relevant, finds the matching clauses in the right contracts, and returns a structured compliance report — with the exact document, page, section, and quoted text behind every single finding.

### Core Capabilities

**Metadata filtering** — Instead of searching all documents blindly, the agent first determines which *types* of documents are relevant to your question. Asking about an NDA only searches NDA content, which cuts noise and improves precision.

**Multi-hop retrieval** — For compliance questions, the agent doesn't just search once. It first finds the relevant *requirement*, then uses that requirement to search for supporting or contradicting *evidence* in the target contracts. Two hops, connecting two separate documents.

**Grounded reporting** — Every finding must cite real evidence. The LLM is instructed to use only the retrieved text, never external knowledge, and to mark a requirement `INSUFFICIENT_EVIDENCE` rather than guess. Output is validated against a strict schema before it's returned.

### Example

> **Query:** *"Does the Privacy Policy comply with our encryption requirements at rest and in transit?"*

> **Result:** `NON_COMPLIANT` — The system matched `REQ-1.1` (AES-256 at rest, TLS 1.3 in transit), retrieved the Privacy Policy's *Data Security Measures* section on page 1, and found that while TLS 1.3 is correctly used in transit, data at rest uses **AES-128** instead of the required AES-256.

---

## 2. AI Service

The AI layer is a retrieval-augmented generation (RAG) pipeline built with LangChain, FAISS, and Groq. It lives in `ai_service/` and exposes a single entry point: `analyse(query, files)`.

### Architecture

```
                        User Query + Payload Documents
                                     |
                                     v
                       ┌─────────────────────────────┐
                       │   Document Type Classifier  │
                       └─────────────────────────────┘
                         /                         \
         (compliance_requirements)          (NDA / Privacy / TOS)
                       /                             \
                      v                               v
          ┌────────────────────┐            ┌────────────────────┐
          │ Sentence Splitter  │            │  Character Text    │
          │  & Deduplication   │            │      Splitter      │
          └────────────────────┘            └────────────────────┘
                      |                               |
                      v                               v
             [ all_req_chunks ]                [ all_doc_chunks ]
                      |                               |
                      |                               v
                      |                      ┌──────────────────┐
                      |                      │  LLM Query Router│
                      |                      │  route_query()   │
                      |                      └──────────────────┘
                      |                               |
                      |                  is_requirement_check + target_doc_types
                      |                               |
                      |                               v
                      |                      ┌──────────────────┐
                      |                      │ Metadata Filter  │
                      |                      │filtered_doc_chunks│
                      |                      └──────────────────┘
                      |                               |
                      v                               v
              FAISS [ index_req ]             FAISS [ index_doc ]
                      \                               /
                       \                             /
                        v                           v
                    ╔═══════════════════════════════════╗
                    ║      is_requirement_check?        ║
                    ╚═══════════════════════════════════╝
                       /                             \
                 (True)                               (False)
                     /                                   \
                    v                                     v
   ┌──────────────────────────────────┐    ┌────────────────────────────┐
   │  PATH A: MULTI-HOP RETRIEVAL     │    │  PATH B: DIRECT SEARCH     │
   │                                  │    │                            │
   │  1. Search query → index_req     │    │  1. Search query →         │
   │     (Hop 1, top-2)               │    │     index_doc              │
   │  2. Deduplicate unique reqs      │    │  2. Retrieve top-5         │
   │  3. Embed requirement text       │    │     evidence chunks        │
   │  4. Search req → index_doc       │    │                            │
   │     (Hop 2, top-3 per req)       │    │                            │
   └──────────────────────────────────┘    └────────────────────────────┘
                     \                                   /
                      \                                 /
                       v                               v
        ┌──────────────────────────────────────────────────────────┐
        │          REASONING & FACT-CHECKING ENGINE                │
        │                                                          │
        │  Evidence Chunks + Target Reqs + Conversation Memory     │
        │                          |                               │
        │                          v                               │
        │            Structured LLM Prompt Execution               │
        │                          |                               │
        │                          v                               │
        │           Pydantic Schema Output Validation              │
        │                          |                               │
        │                          v                               │
        │                [ ComplianceReport JSON ]                 │
        └──────────────────────────────────────────────────────────┘
```

### Pipeline Stages

#### Stage 1 — Ingestion & Chunking (`chunking.py`)

Documents arrive as a `Payload` of `Document` objects, each containing pages with text, page numbers, and section titles. They're split into chunks using **two different strategies** depending on type:

| Document type | Strategy | Why |
|---|---|---|
| `compliance_requirements` | Regex sentence split + deduplication | Each requirement is an atomic rule that must be evaluated independently |
| Contracts (NDA, Privacy, TOS) | `RecursiveCharacterTextSplitter` (1000 chars, 150 overlap) | Legal clauses need surrounding context to be interpreted correctly |

The requirement splitter uses a regex that deliberately **does not** split on periods between digits:

```python
_SENTENCE_SPLIT_RE = re.compile(r'(?<!\d)\.(?!\d)')
```

This matters. A naive `.split(".")` would shatter `REQ-1.1: ...encrypted using TLS 1.3 protocol` into three broken fragments — `REQ-1`, `1: ...TLS 1`, and `3 protocol` — which caused the model to evaluate against a nonexistent "TLS 1" standard. Deduplication also runs here, since policy documents repeat boilerplate across pages.

Every chunk carries full metadata (`document_id`, `filename`, `document_type`, `page_number`, `section_title`), which is what makes precise citations possible later.

#### Stage 2 — Embedding & Indexing (`embeddings.py`, `config.py`)

Chunks are encoded with `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions). Vectors are L2-normalized and stored in FAISS `IndexFlatIP` indexes, so inner product becomes cosine similarity.

Two separate indexes are built per request:
- `index_req` — all requirement chunks
- `index_doc` — only the *filtered* contract chunks for this query

#### Stage 3 — Query Routing (`reasoning.py`)

Before any retrieval happens, the query goes to the LLM for intent classification, returning a `QueryIntent`:

```python
class QueryIntent(BaseModel):
    is_requirement_check: bool
    target_doc_types: list[str]
```

- **`is_requirement_check`** — Is this a compliance check ("does X comply with...") or a plain factual lookup ("what does the NDA say about...")? This decides which retrieval path runs.
- **`target_doc_types`** — Which document types matter here: `privacy_policy`, `vendor_nda`, `terms_of_services`, or `all`. This is the metadata filter.

The filter falls back safely: if it produces an empty set, the pipeline reverts to searching all documents rather than returning nothing.

#### Stage 4 — Retrieval (`pipeline.py`, `retriever.py`)

**Path A — Multi-hop (compliance checks):**

1. **Hop 1:** Search the query against `index_req` → retrieve top-2 relevant requirements
2. Deduplicate the matched requirement texts
3. **Hop 2:** For *each* requirement, embed it and search `index_doc` → retrieve top-3 evidence chunks
4. Deduplicate evidence across requirements

This is what makes the system cross-document: the query touches the *requirements* file, but the evidence comes from the *contracts*. Two documents that never reference each other get connected through the embedding space.

**Path B — Direct search (factual lookups):**

A single search of the query against `index_doc`, returning top-5 evidence chunks. No requirement hop, because there's no rule to check against.

Both paths converge on the same reasoning step.

#### Stage 5 — Reasoning & Report Generation (`reasoning.py`)

Retrieved evidence is formatted into labeled blocks with full provenance:

```
Evidence 1:
Document: Customer_Privacy_Policy_v4.pdf
Page: 1
Section: Data Security Measures
Similarity Score: 0.87
Text: ...
```

This goes to the LLM alongside the target requirements and the conversation history from `ConversationBufferMemory`, under a system prompt with strict grounding rules:

1. Use ONLY the provided requirements and evidence
2. Do NOT use external knowledge
3. Do NOT invent document names, page numbers, sections, or evidence
4. If evidence is insufficient, return `INSUFFICIENT_EVIDENCE`
5. Produce one `Finding` for every requirement

Output is constrained through LangChain's `with_structured_output(ComplianceReport)`, so the response is validated against the Pydantic schema before it's ever returned — malformed output fails loudly instead of silently passing bad data downstream.

### Data Schemas (`schemas.py`)

```python
class Finding(BaseModel):
    finding_id: str          # "F-001"
    severity: Severity       # HIGH | MEDIUM | LOW
    status: ComplianceStatus # COMPLIANT | PARTIALLY_COMPLIANT |
                             # NON_COMPLIANT | INSUFFICIENT_EVIDENCE
    requirement: str         # the exact requirement evaluated
    document: str            # source filename
    page: int                # source page
    section: str             # source section title
    evidence: str            # exact quoted supporting text
    analysis: str            # why this status was assigned
    recommendation: str      # concrete remediation action

class ComplianceReport(BaseModel):
    status: ComplianceStatus # overall posture
    summary: str             # 2-4 sentence overview
    findings: list[Finding]
```

Every finding is traceable back to a specific page and section of a specific document.

### Conversation Memory

`ConversationBufferMemory` is injected into the reasoning prompt as `chat_history`, so follow-up questions retain context from earlier turns. `refrech()` clears both the chunk stores and the memory — called when the user refreshes the page to start a clean session.

### Project Structure

```
ai_service/
├── config.py        # Env vars, LLM + embedding model init, constants
├── schemas.py       # Pydantic models for all data structures
├── chunking.py      # Document → Chunk conversion (two strategies)
├── embeddings.py    # Text → vector encoding
├── retriever.py     # FAISS similarity search
├── reasoning.py     # Query routing + LLM reasoning + prompts
├── pipeline.py      # analyse() — orchestrates the full flow
├── demo.py          # Local test runner
└── payload.json     # Sample input documents
```

### Tech Stack

| Component | Technology |
|---|---|
| LLM | Groq — `openai/gpt-oss-20b` |
| Orchestration | LangChain |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| Vector Store | FAISS (`IndexFlatIP`, cosine similarity) |
| Validation | Pydantic |
| Chunking | LangChain `RecursiveCharacterTextSplitter` |

### Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
MODEL_NAME=openai/gpt-oss-20b
```

Run the demo(Test AI):

```bash
cd ai_service
python demo.py
```

### Usage

```python
from schemas import Payload
from pipeline import analyse, refrech

payload = Payload(**your_documents_dict)

report = analyse(
    query="Does the Privacy Policy comply with our encryption requirements?",
    files=payload
)

print(report.status)    # ComplianceStatus.NON_COMPLIANT
print(report.summary)
for finding in report.findings:
    print(finding.requirement, "→", finding.status)

refrech()  # clear session state
```

For follow-up questions in the same session, send an empty document list — previously indexed content is reused:

```python
report = analyse(query="What about the NDA?", files=Payload(documents=[]))
```

---

## 3. Back-End

*Coming soon.*

---

## 4. Front-End

*Coming soon.*

---

## 5. Contributors

This project was built by a team of four.

| Name | Role | Contribution | Links |
|---|---|---|---|
| **Omar Mohamed** | AI / ML | RAG pipeline, multi-hop retrieval, LLM reasoning & prompt engineering | [@oMaR-M-M](https://github.com/oMaR-M-M) |
| **Omar Karam** | Front-End & Back-End | API layer, session handling, document ingestion endpoints | [@8-Omoshikiii-8](https://github.com/8-Omoshikiii-8) |
| **Omar shokry** | Back-End | [Contribution] | [@Omar-Mohamed-2006](https://github.com/Omar-Mohamed-2006) |
| **Abdullah Sami** | Front-End | [Contribution] | [Alex-RavenHolm](https://github.com/Alex-RavenHolm) |

---
