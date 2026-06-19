import  pdfplumber
import chromadb
import re
from sentence_transformers import SentenceTransformer
from pathlib import Path
import uuid
import os

UPLOAD_DIR = Path("app/agents/policy_docs")
CHROMA_DIR = Path("app/agents/chroma_policy_db")
 
# Default policy file to auto-ingest if the store is empty.
# Set POLICY_PDF env var to override the filename.
DEFAULT_POLICY_PDF = os.getenv("POLICY_PDF", "claimflow_enterprise_policy.pdf")
 
# ---- lazy singletons (created on first use, NOT at import) ----
_embedder = None
_chroma_client = None
_collection = None
 
#embeddings
def get_embedder():
    """Load the embedding model on first use (keeps startup fast + low memory)."""
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder
 
 
def get_collection():
    """Get (or create) the ChromaDB collection. Auto-ingests policy if empty."""
    global _chroma_client, _collection
    if _collection is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _chroma_client.get_or_create_collection(name="policy_docs")
        # If empty (e.g. fresh Railway container), re-ingest the default policy.
        try:
            if _collection.count() == 0:
                _auto_ingest_if_available()
        except Exception as e:
            print(f"[rag_service] auto-ingest check failed: {e}")
    return _collection
 
 
def _auto_ingest_if_available():
    """Ingest the default policy PDF on first boot if it exists in the repo."""
    pdf_path = UPLOAD_DIR / DEFAULT_POLICY_PDF
    if pdf_path.exists():
        print(f"[rag_service] ChromaDB empty - auto-ingesting {DEFAULT_POLICY_PDF}")
        ingest_policy_pdf(DEFAULT_POLICY_PDF)
    else:
        print(f"[rag_service] No default policy at {pdf_path}; ingest manually via /ingest-policy")
 
#cleaning text
def clean_chunk(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()
 
 
def ingest_policy_pdf(filename: str) -> dict:
    """Read policy PDF, chunk, embed, store in ChromaDB."""
    pdf_path = UPLOAD_DIR / filename
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at {pdf_path}")
 
    # extract text
    raw_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                raw_text += text + "\n"
 
    # chunk (500 chars, 50 overlap)
    chunks = []
    chunk_size, overlap = 500, 50
    start = 0
    while start < len(raw_text):
        end = start + chunk_size
        chunks.append(raw_text[start:end])
        start = end - overlap
 
    # embed (lazy model) + store
    embedder = get_embedder()
    embeddings = embedder.encode(chunks).tolist()
 
    # use the raw collection (avoid recursion into auto-ingest)
    global _chroma_client, _collection
    if _collection is None:
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _chroma_client.get_or_create_collection(name="policy_docs")
 
    _collection.add(
        documents=chunks,
        embeddings=embeddings,
        ids=[str(uuid.uuid4()) for _ in chunks],
    )
 
    return {"status": "success", "filename": filename, "chunks_stored": len(chunks)}
 
# Query function
def query_policy(question: str, top_k: int = 3) -> list[str]:
    """Return top matching policy chunks for a question."""
    collection = get_collection()
    embedder = get_embedder()
    question_embedding = embedder.encode(question).tolist()
    results = collection.query(query_embeddings=[question_embedding], n_results=top_k)
    docs = results.get("documents", [[]])
    return docs[0] if docs else []
 
 
def debug_check_chromadb():
    collection = get_collection()
    count = collection.count()
    return {"count": count, "path": str(CHROMA_DIR.absolute())}