import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import CHUNK_SIZE, CHUNK_OVERLAP
from schemas import Chunk


# for the target documents
splitter  = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)


# for the requerements documents 
# Splits on '.' that end a sentence, but NOT on a '.' sandwiched between digits (e.g. "REQ-1.1", "TLS 1.3").
_SENTENCE_SPLIT_RE = re.compile(r'(?<!\d)\.(?!\d)')


def chunk_pages(document, is_requirement: bool = False) -> list[Chunk]:
  Chunks = []
  seen_requirement_texts = set() # to remove the redundancy.

  for page in document.pages:
    if is_requirement:
      text_chunks = [
        piece.strip()
        for piece in _SENTENCE_SPLIT_RE.split(page.text)
        if piece.strip()
    ]
    else:
      text_chunks = splitter.split_text(page.text)

    for idx, piece in enumerate(text_chunks):
      #---------------------------------------------------
      # normalize(lowercaseliters) and remove the redundancy
      #---------------------------------------------------
      if is_requirement:
        normalized = piece.strip().lower()
        if normalized in seen_requirement_texts:
          continue
        seen_requirement_texts.add(normalized)
      #---------------------------------------------------

      #---------------------------------------------------
      # Chunk metadata
      #---------------------------------------------------
      chunk_id = (
        f'{document.document_id}'
        f'-{page.page_number}'
        f'-{idx}'
      )
      chunk = Chunk(
        chunk_id=chunk_id,
        document_id=document.document_id,
        filename=document.filename,
        document_type=document.document_type,
        page_number=page.page_number,
        section_title=page.section_title,
        text=piece,
      )
      #---------------------------------------------------
      Chunks.append(chunk)
  return Chunks
