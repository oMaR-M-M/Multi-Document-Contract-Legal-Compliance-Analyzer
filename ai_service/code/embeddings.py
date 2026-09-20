from .config import Embedding_model
import numpy as np

#---------------------------------------------------
# embedding the text in the documents
#---------------------------------------------------
def embedding_chunks(chunks):
  embedded_chunks = []

  for chunk in chunks:
    text_chunk = chunk.text
    embedded_text_chunk = Embedding_model.encode(text_chunk)
    embedded_chunks.append(embedded_text_chunk)

  embedded_chunks = np.array(embedded_chunks)

  return embedded_chunks 
#---------------------------------------------------


#---------------------------------------------------
# embedding the query text
#---------------------------------------------------
def embedding_query(query):
  embedded_query = Embedding_model.encode(query)
  embedded_query = np.array(embedded_query)

  return embedded_query
#---------------------------------------------------