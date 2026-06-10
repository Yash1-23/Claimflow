"""
 What It Does:
   when a claim is submitted, this agetn checks it against the compines expense plocy 
   documents stored in ChromaDB.It returns a compliance verdict:
   Approved, Flagged, or Rejected, along with the specific policy rule that 
   was violated (with citation).
   
Why i used RAG:
   Instead of harding rules like "travel limit = 5000", we store the actual policy PDF in 
   chromaDB.The agent retrievs the relevant policy section and lets the LLM reasons over them,
   This means:
   - Policy updates = just re-index the document, no code changes
   - citation  = the agent quoutes the exact policy text it used 
   - Handles edge cases = LLM reasons about ambigous situation.
   
   
"""

from app.services.rag_service import query_policy
from groq import Groq
from app.core.config import Settings,settings
import os
import json

# groq client
client = Groq(api_key=settings.GROQ_API_KEY)

# Agent function

def check_claim_against_policy(claim_data:dict) -> dict:
  """_
    Takes a claim -> fetches  relevant policy chunks -> asks Groq to check violations
    
    claims_data ex:
    {
      "category":"travel",
      "amount": 8000,
      "employee_level":"junior",
      "description":"Hotel stay in Mumbai"
      }
      
    return:
    {
      "verdict":"approved" | "flagged" | "rejected",
      "reason":"explantion",
      "policy_citation":"exact policy text used",
      "allowed_limit":"limit from policy"
    }
  """
  
  # step 1: Build natural language questions from claim data
  question = (
    f"Is a {claim_data['category'] } expense of Rs {claim_data['amount']}"
    f"allowed for a {claim_data['employee_level']} employee? "
    f"Description: {claim_data['description']}"
  )
  
  # step2 : retrieve top 3 matching policy chunks from chromaDB
  policy_chunks= query_policy(question,top_k=3)
  
  #step3: join chunks into one context block
  # we paste this prompt so LLM can read the policy
  policy_context = "\n\n---\n\n".join(policy_chunks)
  
  # step4: build the prompt
  # "Based ONLY on policy documents" _> stops LLM from making up rules
  prompt = f"""You are a strict company expense policy compliance checker for claimflow Inc.
  
RETRIEVED POLICY SECTIONS:
{policy_context}

EXPENSE CLAIM TO VALIDATE:
- Category: {claim_data['category']}
- Amount: Rs {claim_data['amount']}
- Employee Level: {claim_data['employee_level']}
- Description: {claim_data['description']}

TASK:
Based ONLY on the retrieved policy sections above, check if this claim is compliant.
Do NOT use any outside knowledge. Only use whar is written in th policy sections.


Respond in this exact JSON fromat:
{{
  "verdict":"approved" or "flagged" or "rejected",
  "reason": "clear explantion of why approved, flagged, or rejected",
  "policy_citation":"copy the exact policy text you need to make this decision",
  "allowed_limit":"the exact limit from policy for this category and level, or null if not found"
}}

Verdict definitions:
- approved: claim is within policy limits
- flagged: claim need manager review (borderline or missing info)
- rejected: claim clearly violated policy
  """
  
  # step 5: call Groq LLM
  response= client.chat.completions.create(
    model ="llama-3.3-70b-versatile",
    messages=[{"role":"user","content":prompt}],
    response_format ={"type":"json_object"},
  )
  
  # step 6: parse Json responses
  result = json.loads(response.choices[0].message.content)
  
  # step7: Return result
  return {
    "claim": claim_data,
    "policy_check":result,
    "policy_chunks_used":policy_chunks
  }

  
  




