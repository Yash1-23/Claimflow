from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional,List
from app.agents.policy_agent import check_claim_against_policy,chat_with_policy
from app.services.rag_service import ingest_policy_pdf,debug_check_chromadb
from app.core.security import get_current_user,require_role

router = APIRouter(tags=["Policy RAG"])

# 1.Request schema
# pydantic model -defines what the request body must look like

class IngestionRequest(BaseModel):
  filename: str # claimflow policy pdf
  
class PolicyCheckRequest(BaseModel):
  category:str
  amount:float
  employee_level:str 
  description:str

class ChatMessage(BaseModel):
  role:str
  content:str
  
class ChatRequest(BaseModel):
  message:str
  conversation_history:Optional[List[ChatMessage]] = None

# 2.Ingestion Endpoint
#Only admin can call this - you dont want employee re-indexing the policy
# call this ONCE after placing the PDF in app/agents/policy_docs/

@router.post("/ingest-policy")
def ingest_policy(
  request: IngestionRequest,
  current_user = Depends(require_role("admin"))
  # require_role("admin") only admin JWT token can  call this endpoint
  
):
  """
  Reads the policy PDF and stores all chunks in ChromDB.
  Run this once after placing the pdf in app/agents/uploads.
  After this, chromDB remembers everything no need to run again
  unless policy document changes.
  """
  
  try:
    result = ingest_policy_pdf(request.filename)
    return result
  
  except Exception as e:
    raise HTTPException(status_code=500,detail=f"ingestion failed: {str(e)}")
 
 
# chatRequest
@router.post("/chat-policy")
def chat_policy_endpoint(
  request:ChatRequest,
  current_user=Depends(get_current_user)
): 
  
  """ Natural language policy checker.
      Example: I spent 4500 on hotel in Hyderbad, I'm a senior employee
  """
  try:
    history=None
    if request.conversation_history:
      history = [m.model_dump() for m in request.conversation_history]
      
    result= chat_with_policy(request.message,request.conversation_history)
    return result
  except Exception as e:
    raise HTTPException(status_code=500,detail=f"Chat policy failed: {str(e)}")
  
    
  
# 3. Policy check endpoint
# Any logged-in user can call this

@router.post("/check-policy")
def check_policy(
  request: PolicyCheckRequest,
  current_user=Depends(get_current_user)
  
):
  """ 
  Checks a claim against the policy document stored in ChromaDB.
  Returns verdict: approved/flagged/rejected with policy citation.
  """
  
  try:
     # Convert Pydantic model → plain dict for the agent
     # Why .model_dump()? agent expects a dict, not a Pydantic object
      claim_data = request.model_dump()
      
      result = check_claim_against_policy(claim_data)
      
      return result
    
  except Exception as e:
    raise HTTPException(status_code=500,detail=f"Policy check failed: {str(e)}")
 
 
  

@router.get("/debug-chromadb")
def debug_chromadb_status(
  current_user =Depends(get_current_user)
):
  """Check chromdb status show if chunks exist"""
  return debug_check_chromadb()
    
    