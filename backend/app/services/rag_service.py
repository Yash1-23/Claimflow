import  pdfplumber
import chromadb
import re
from sentence_transformers import SentenceTransformer
from pathlib import Path
import uuid

UPLOAD_DIR = Path("app/agents/policy_docs")

# chromadb saves the vectors 
CHROMA_DIR = Path("app/agents/chroma_policy_db")

# load models 
embedder = SentenceTransformer("all-MiniLM-L6-v2")

#chromaDB client - persist_directory means data survives server restarts
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# A "collection" is like a table in chromaDB - stroes all policy chunks
collection = chroma_client.get_or_create_collection(name="policy_docs")

# cleaning text
def clean_chunk(text:str)->str:
  text = re.sub(r'\s+',' ',text)
  text = text.strip()
  return text


# Ingestion function
def ingest_policy_pdf(filename:str) -> dict:   
  """ 
  Reads the policy PDF, splits into chunks, embed them,stores in chromaDB,
  Call this Once to load your polikcy.After that ChromaDB remembers it.
  
  """
  pdf_path = UPLOAD_DIR / filename
  
  if not pdf_path.exists():
    raise FileNotFoundError(f"PDF not found at {pdf_path}")
  
  # step A: extract all text from pdf using pdfplumber
  raw_text = ""
  with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
      text =  page.extract_text()
      if text:
        raw_text += text + "\n"
        
  # step B - split the text into chunks of 500 characters with 50 char overlap
  chunks= []
  chunk_size=500
  overlap = 50


  start = 0
  while start < len(raw_text):
    end = start+ chunk_size
    chunk = raw_text[start:end]
    chunks.append(chunk)
    start = end - overlap     # overlap- go back 50 chars before next chunk
    
  # step 3  - Embed each chunk 
  embeddings = embedder.encode(chunks).tolist() # tolist() converts numpy array ->plain python list 
  
  # step 4 - store chunks + embeddings in chromaDB
  collection.add(
    documents=chunks,    # raw text 
    embeddings=embeddings, # vectors
    ids=[str(uuid.uuid4()) for _ in chunks] #unique ID per chunk
    
  )
  
  return {
    "status":"success",
    "filename":filename,
    "chunks_stored":len(chunks)
  }
  
# Query Function
def query_policy(question: str, top_k: int=3) -> list[str]:
  """
   Takes a question  about an expense claim -> return top matching policy chunks.
   
  """
  # Embed the question (same model, so vectors are comparable)
  question_embedding = embedder.encode(question).tolist()
  
  # search chromDB for the most similar chunks
  results = collection.query(
    query_embeddings=[question_embedding],
    n_results=top_k
  )
  print("DEBUG results:",results["documents"])
  return results["documents"][0]

  
# Temporary debug function - Delete after use
 
def debug_check_chromadb():
  """check what actualy in chromadb
  """
  count = collection.count()
  print(f"\n{'='*50}")
  print(f"ChromaDB status")
  print(f"{'='*50}")
  print(f"collection name: {collection.name}")
  print(f"total chunks stored: {count}")
  print(f"ChromDB path: {CHROMA_DIR.absolute()}")
  print(f"Path exists: {CHROMA_DIR.exists()}")
  
  if count > 0:
    
    #show first chunk
    sample = collection.peek(limit=1)
    print(f"\n first chunkk preview")
    print(f" ID: { sample['ids'][0]}")
    print(f"text: {sample['documents'][0][:200]}...")
    
  else:
    print(f"\n ChromaDB is EMPTY")
    
  print(f"{'='*50}\n")
  
  return {"count":count, "path":str(CHROMA_DIR.absolute())}
  
      