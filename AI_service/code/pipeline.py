# If all_req_chunks and all_doc_chunks are empty the user can not send any thing
# if there is no query the user can not send any thing 
import faiss
from langchain_classic.memory import ConversationBufferMemory
from config import REQUIREMENTS_TYPE, TARGET_TYPES, REQUIREMENTS_BATCH_SIZE, dim
from schemas import Evidence, Payload
from chunking import chunk_pages
from embeddings import embedding_chunks, embedding_query
from retriever import search
from reasoning import reasoning, route_query


# Stores all chunk objects for requirements and documents respectively.
all_req_chunks = []
all_doc_chunks = []


# Initialize LLM memory.
memory = ConversationBufferMemory(return_messages=True)


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
    req_embedded = embedding_chunks(all_req_chunks).astype("float32")
    doc_embedded = embedding_chunks(filtered_doc_chunks).astype("float32")
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
        evidence = []
        target_req_texts = []
        
        retrieved_reqs, req_scores = search(query_embedded, index_req, all_req_chunks, top_k=2)
        
        unique_req_texts = list(set([rc.text for rc in retrieved_reqs]))
        
        for req_text in unique_req_texts:
            target_req_texts.append(req_text)
            req_text_embedded = embedding_query(req_text).astype("float32")
            faiss.normalize_L2(req_text_embedded.reshape(1, -1))
            
            retrieved_docs, doc_scores = search(req_text_embedded, index_doc, filtered_doc_chunks, top_k=3)
            
            for rc, s in zip(retrieved_docs, doc_scores):
                if not any(e.text == rc.text for e in evidence):
                    evidence.append(Evidence(score=float(s), metadata=rc, text=rc.text))
                
        report = reasoning(target_req_texts, evidence, memory)
        memory.save_context({"input": query}, {"output": report.summary})
        return report
    #---------------------------------------------------


    #---------------------------------------------------
    # if user's prompt in the documnets
    #---------------------------------------------------
    else:
        evidence = []
        
        retrieved_docs, doc_scores = search(query_embedded, index_doc, filtered_doc_chunks, top_k=5)
        
        for rc, s in zip(retrieved_docs, doc_scores):
            evidence.append(
                Evidence(score=float(s), metadata=rc, text=rc.text)
            )
            
        report = reasoning([query], evidence, memory)
        
        memory.save_context({"input": query}, {"output": report.summary})
        return report
    #---------------------------------------------------


# clear every thing when the user refrech the page.
def refrech():
    # Clear stored chunk lists.
    all_req_chunks.clear()
    all_doc_chunks.clear()

    # Clear LLM memory
    memory.clear()
