# If all_req_chunks and all_doc_chunks are empty the user can not send any thing
# if there is no query the user can not send any thing 
import faiss
from langchain_classic.memory import ConversationBufferMemory
from .config import REQUIREMENTS_TYPE, TARGET_TYPES, REQUIREMENTS_BATCH_SIZE, dim
from .config import REQ_PREFIX_TO_DOC, MIN_REQ_SCORE, REQ_REL_SCORE, DEBUG_RETRIEVAL
from shared.schemas import Evidence, Payload, Finding, ComplianceReport, ComplianceStatus
from .chunking import chunk_pages
from .embeddings import embedding_chunks, embedding_query
from .retriever import search
from .reasoning import reasoning, route_query


# Stores all chunk objects for requirements and documents respectively.
all_req_chunks = []
all_doc_chunks = []

# Documents that were already chunked. The same files arrive with every request,
# without this check every query added a new copy of every chunk to the lists above
# (top-k then returned copies of the same clause and the report lost findings).
_seen_docs = set()


# Initialize LLM memory.
memory = ConversationBufferMemory(return_messages=True)


# Does this requirement clause apply to the document types the user asked about?
# Clauses that belong to no single document (section 5 / bullets) always apply.
def _req_applies(req_chunk, target_types) -> bool:
    req_doc_type = REQ_PREFIX_TO_DOC.get(req_chunk.section_title[:1])
    if req_doc_type is None or not target_types or "all" in target_types:
        return True
    return req_doc_type in target_types


# Report returned when no requirement is relevant to the query (no LLM call, nothing to guess).
def _no_match_report(query: str) -> ComplianceReport:
    return ComplianceReport(
        status=ComplianceStatus.INSUFFICIENT_EVIDENCE,
        summary="No requirement in the compliance requirements document is relevant to this query, so it cannot be assessed.",
        findings=[
            Finding(
                finding_id="F-001",
                severity="LOW",
                status=ComplianceStatus.INSUFFICIENT_EVIDENCE,
                requirement=query,
                document="N/A",
                page=0,
                section="N/A",
                evidence="No relevant requirement was found.",
                analysis="None of the requirements in the compliance requirements document matches this query.",
                recommendation="Rephrase the query, or add the missing requirement to the compliance requirements document.",
            )
        ],
    )


# Main function that links chunking, embedding, retrieval, and reasoning.
def analyse(query: str, files: Payload):
    # route the query
    intent = route_query(query)
    qin_req = intent.is_requirement_check
    target_types = intent.target_doc_types

    req_chunks = []
    doc_chunks = []

    #---------------------------------------------------
    # convert requerments and docs to chunks.
    #---------------------------------------------------
    for document in files.documents:
        if (document.document_id, document.filename) in _seen_docs:
            continue
        _seen_docs.add((document.document_id, document.filename))

        if document.document_type == REQUIREMENTS_TYPE:
            req_chunks = chunk_pages(document, True)
            all_req_chunks.extend(req_chunks)
        else:
            doc_chunks = chunk_pages(document, False)
            all_doc_chunks.extend(doc_chunks)
    #---------------------------------------------------
    

    #---------------------------------------------------

    #---------------------------------------------------
    if "all" in target_types or not target_types:
        filtered_doc_chunks = all_doc_chunks
    else:
        filtered_doc_chunks = [c for c in all_doc_chunks if c.document_type in target_types]
        if not filtered_doc_chunks:
            filtered_doc_chunks = all_doc_chunks
    #---------------------------------------------------


    #---------------------------------------------------
    # Embede requerments, docs and query and index save.
    #---------------------------------------------------
    # The doc index holds ALL documents: in the requirements flow the document type
    # is decided per requirement (see below), so filtering is done after the search.
    req_embedded = embedding_chunks(all_req_chunks).astype("float32")
    doc_embedded = embedding_chunks(all_doc_chunks).astype("float32")
    query_embedded = embedding_query(query).astype("float32")

    faiss.normalize_L2(req_embedded)
    faiss.normalize_L2(doc_embedded)
    faiss.normalize_L2(query_embedded.reshape(1, -1))

    index_doc = faiss.IndexFlatIP(dim)
    index_req = faiss.IndexFlatIP(dim)

    index_doc.add(doc_embedded)
    index_req.add(req_embedded)
    #---------------------------------------------------


    #---------------------------------------------------
    # if user's prompt in the requirements
    #---------------------------------------------------
    if qin_req:
        # requirement text -> the evidence found for THIS requirement only
        evidence_by_req = {}

        # hop 1: the relevant requirements, one search per topic of the query
        # (a dict keeps the order and removes the duplicates)
        picked_reqs = {}
        for topic in (intent.topics or [query]):
            topic_embedded = embedding_query(topic).astype("float32")
            faiss.normalize_L2(topic_embedded.reshape(1, -1))

            retrieved_reqs, req_scores = search(topic_embedded, index_req, all_req_chunks, top_k=len(all_req_chunks))

            if DEBUG_RETRIEVAL:
                print(f"[retrieval] topic: {topic!r}")
                for rc, s in list(zip(retrieved_reqs, req_scores))[:6]:
                    print(f"    {float(s):.3f}  {rc.section_title[:60]}")

            hits = [
                (rc, float(s)) for rc, s in zip(retrieved_reqs, req_scores)
                if s >= MIN_REQ_SCORE and _req_applies(rc, target_types)
            ]
            if not hits:
                continue

            best_score = hits[0][1]
            for rc, s in hits[:(2 if intent.topics else 4)]:
                if s >= best_score * REQ_REL_SCORE:
                    picked_reqs.setdefault(rc.chunk_id, rc)

        if not picked_reqs:
            report = _no_match_report(query)
            memory.save_context({"input": query}, {"output": report.summary})
            return report

        # hop 2: the evidence for every requirement, only from the document type it applies to
        for rc in picked_reqs.values():
            req_text = rc.text
            req_text_embedded = embedding_query(req_text).astype("float32")
            faiss.normalize_L2(req_text_embedded.reshape(1, -1))

            req_doc_type = REQ_PREFIX_TO_DOC.get(rc.section_title[:1])   # None = applies to every document

            retrieved_docs, doc_scores = search(req_text_embedded, index_doc, all_doc_chunks, top_k=len(all_doc_chunks))

            evidence = []
            per_type_count = {}
            per_type_limit = 5 if req_doc_type else 2
            for dc, s in zip(retrieved_docs, doc_scores):
                if req_doc_type and dc.document_type != req_doc_type:
                    continue
                if per_type_count.get(dc.document_type, 0) >= per_type_limit:
                    continue
                per_type_count[dc.document_type] = per_type_count.get(dc.document_type, 0) + 1
                evidence.append(Evidence(score=float(s), metadata=dc, text=dc.text))

            evidence_by_req[req_text] = evidence

        report = reasoning(evidence_by_req, memory)
        memory.save_context({"input": query}, {"output": report.summary})
        return report
    #---------------------------------------------------


    #---------------------------------------------------
    # if user's prompt in the documnets
    #---------------------------------------------------
    else:
        evidence = []
        allowed_types = {c.document_type for c in filtered_doc_chunks}
        
        retrieved_docs, doc_scores = search(query_embedded, index_doc, all_doc_chunks, top_k=len(all_doc_chunks))
        
        for rc, s in zip(retrieved_docs, doc_scores):
            if rc.document_type not in allowed_types:
                continue
            evidence.append(
                Evidence(score=float(s), metadata=rc, text=rc.text)
            )
            if len(evidence) == 5:
                break
            
        report = reasoning({query: evidence}, memory)
        
        memory.save_context({"input": query}, {"output": report.summary})
        return report
    #---------------------------------------------------


# clear every thing when the user refrech the page.
def refrech():
    # Clear stored chunk lists.
    all_req_chunks.clear()
    all_doc_chunks.clear()
    _seen_docs.clear()

    # Clear LLM memory
    memory.clear()
