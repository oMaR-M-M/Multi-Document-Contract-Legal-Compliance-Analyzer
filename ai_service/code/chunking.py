import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .config import CHUNK_SIZE, CHUNK_OVERLAP
from shared.schemas import Chunk


# for the target documents
splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)


_REQ_SPLIT_RE = re.compile(r'(?m)^(?=\d+\.(?:\d+\.?)*\s+[A-Z]|REQ-\d|•)')
_REQ_KEEP_RE = re.compile(r'^(?:[2-5]\.\d|REQ-\d|•)')


_SENTENCE_SPLIT_RE = re.compile(r'(?<!\d)\.(?!\d)')

_HEADER_RE = re.compile(r'\A(?:[^\n]*\n)?[^\n]*\|\s*Page\s*\d+[ \t]*\n?')

_BULLET_RE = re.compile(r'(?m)^[•●▪◦\u2022\u25cf\uf0b7\x7f][ \t]*\n?')


def _split_requirements(text):
  pieces = [
    piece.strip()
    for piece in _REQ_SPLIT_RE.split(text)
    if _REQ_KEEP_RE.match(piece.strip())
  ]
  if pieces:
    return pieces
  return [
    piece.strip()
    for piece in _SENTENCE_SPLIT_RE.split(text)
    if piece.strip()
  ]


def _join_pages(document):
  joined = ""
  page_starts = []
  for page in document.pages:
    page_starts.append((len(joined), page))
    page_text = _BULLET_RE.sub("• ", _HEADER_RE.sub("", page.text)).strip()
    joined += page_text + "\n"
  return joined, page_starts


def _page_at(page_starts, position):
  current = page_starts[0][1]
  for start, page in page_starts:
    if start <= position:
      current = page
  return current


def chunk_pages(document, is_requirement: bool = False) -> list[Chunk]:
  Chunks = []
  seen_requirement_texts = set()

  full_text, page_starts = _join_pages(document)

  if is_requirement:
    text_chunks = _split_requirements(full_text)
  else:
    text_chunks = splitter.split_text(full_text)

  cursor = 0
  for idx, piece in enumerate(text_chunks):
    #---------------------------------------------------
    # the page where this chunk starts (needed for the citation)
    #---------------------------------------------------
    position = full_text.find(piece[:80], cursor)
    if position == -1:
      position = cursor
    cursor = position + 1
    page = _page_at(page_starts, position)
    #---------------------------------------------------

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
    section_title = page.section_title
    if is_requirement and _REQ_KEEP_RE.match(piece):
      section_title = piece.split("\n", 1)[0].strip()
    chunk = Chunk(
      chunk_id=chunk_id,
      document_id=document.document_id,
      filename=document.filename,
      document_type=document.document_type,
      page_number=page.page_number,
      section_title=section_title,
      text=piece,
    )
    #---------------------------------------------------
    Chunks.append(chunk)
  return Chunks
