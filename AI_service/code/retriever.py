#---------------------------------------------------
# find the most matching Evidence with the query
#---------------------------------------------------
def search(query, index, chunks, top_k=5):
    top_k = min(top_k, len(chunks))
    
    score, indices = index.search(query.reshape(1, -1), top_k)
    retrieved_chunks = [chunks[i] for i in indices[0]]

    return retrieved_chunks, score[0]
#---------------------------------------------------