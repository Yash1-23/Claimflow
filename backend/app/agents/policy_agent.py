"""
 What It Does:
   when a claim is submitted, this agetn checks it against the compines expense plocy 
   documents stored in ChromaDB.It returns a compliance verdict:
   Approved, Flagged, or Rejected, along with the specific policy rule that 
   was violated (with citation).
   
   - Chat_with_policy: Conversational assistant - answers general policy question OR checks a specific claims, depending on intent
   
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
import re
from json import JSONDecodeError

# groq client
client = Groq(api_key=settings.GROQ_API_KEY)

# Agent function

def check_claim_against_policy(claim_data: dict) -> dict:
  """
  Takes a claim -> fetches relevant policy chunks -> asks Groq to check violations
  
   claim_data example:
    {
      "category": "travel",
      "amount": 8000,
      "employee_level": "junior",
      "description": "Hotel stay in Mumbai"
    }

    returns:
    {
      "verdict": "approved" | "flagged" | "rejected",
      "reason": "explanation",
      "policy_citation": "exact policy text used",
      "allowed_limit": "limit from policy"
    }
  """
  
  # step1 Build Multiple targeted questions 
  # Improves chunk retrieval coverage
  questions =[
    f"What is the {claim_data['category']} expense limit for {claim_data['employee_level']} employee?",
    f"Is {claim_data['description']} allowed under company policy?",
    f"What are the rules for {claim_data['category']} claims?",
  ]
  
  # step 2: Retrieve chunks for each question combine + deduplicate
  all_chunks =[]
  for q in questions:
    chunks = query_policy(q, top_k=3) # returns list[str]
    all_chunks.extend(chunks)
    
  #deduplicate - strings are hasble, set() works 
  all_chunks = list(set(all_chunks))
        
  # step 3 Guard if no chunk found, return Unknown immediately
  # Never let LLM anser with empty context
  if not all_chunks:
    return {
      "claim": claim_data,
      "policy_check":{
      "verdict": "flagged",
      "reason":"No matching policy found for this expense category. Needs manual review.",
      "policy_citation":"N/A",
      "allowed_limit":None,
      },
      "policy_chunks_used":[],
    }
    
  # step 4 Join chunks in to context block
  policy_context = "\n\n--\n\n".join(all_chunks)
  
  # step 5 strict prompt with all explicit "if not found " instruction
  prompt = f"""You are an expense policy DATA EXTRACTOR for ClaimFlow Inc.
Do NOT make the final approve/reject decision. Only EXTRACT facts from the policy.
 
POLICY SECTIONS:
{policy_context}
 
CLAIM:
- Category: {claim_data['category']}
- Amount: Rs {claim_data['amount']}
- Level: {claim_data['employee_level']} (Junior=L1-L3, Senior=L4-L6, Manager=L7-L9, Director=L10+)
- Description: {claim_data['description']}
 
Find the policy row for this level and the COLUMN that matches the description
(e.g. a training course uses the Courses/Certs column, NOT Conference).
 
Extract ONLY these facts as JSON (no verdict, no opinion):
{{
  "limit_found": the numeric limit from the matched column, or null if not in policy,
  "is_eligible": true if this level is allowed this expense, false if restricted (e.g. "Manager+ only"),
  "policy_citation": "the exact policy line you used",
  "matched_column": "which column you matched (e.g. Courses/Certs)"
}}

  
  

"""
  

   #step 6 Call Groq
  response = client.chat.completions.create(
  model = "llama-3.3-70b-versatile",
  messages = [
      {
        "role":"system",
       
        "content": "You extract policy facts as JSON. You never give verdicts. JSON only."
      },
      {
        "role":"user",
        "content":prompt
      },
    ],
    temperature=0.0,
    max_tokens=300,
    response_format={"type":"json_object"},
    
  )
  
  try:
     facts = json.loads(response.choices[0].message.content)
  except json.JSONDecodeError:
    return {
      "claim": claim_data,
      "policy_check":{
      "verdict":"flagged",
      "reason":"Policy agent returned invalid response.Needs manual review.",
      "policy_citation":"N/A",
      "allowed_limit":None,
    },
    "policy_chunks_used":all_chunks
    }
  limit = facts.get("limit_found")
  eligible = facts.get("is_eligible", True)
  citation = facts.get("policy_citation", "N/A")
  column = facts.get("matched_column", "")
  amount = float(claim_data["amount"])
 
  if limit is None:
        verdict = "flagged"
        reason = f"No matching limit found in policy for {claim_data['category']}. Needs manual review."
  elif not eligible:
        verdict = "rejected"
        reason = f"{claim_data['employee_level']} is not eligible for this expense ({column}). Rejected."
  elif amount <= float(limit):
        verdict = "approved"
        reason = f"Matched {column}: limit Rs {limit}. Claim Rs {amount} is within limit, eligible. Approved."
  else:
        verdict = "rejected"
        reason = f"Matched {column}: limit Rs {limit}. Claim Rs {amount} exceeds limit. Rejected."
 
  return {
        "claim": claim_data,
        "policy_check": {
            "verdict": verdict,
            "reason": reason,
            "policy_citation": citation,
            "allowed_limit": limit,
        },
        "policy_chunks_used": all_chunks,
    }
# Intent detection (general questions or claim check)
def detect_intent(user_message:str) ->str:
  """
  Decide if the user is asking GENERAL question about policy.
  or describing a SPECIFIC claim to validate.
  Returns "QUESTION" or "CLAIM".
  
  Rule of thumb : a CLAIM names a specific amount the user actually spent.
  A QUESTION asks about rules/limit/eligibility, even if it contains the word "claim"
  
  """
  
  
   # Cheap pre-check: no number in the message => almost certainly a question.
  has_number = bool(re.search(r"\d", user_message))
  if not has_number:
      return "QUESTION"
      
  response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
      {
        "role": "system",
                "content": """Classify the user's message into exactly one intent.
 
"CLAIM"   = the user describes a SPECIFIC expense they actually spent, with a concrete amount.
            Examples: "I spent 5000 on a hotel", "claim 8900 for a training course",
            "I paid 1200 for cab to airport".
 
"QUESTION"= the user asks ABOUT policy: rules, limits, eligibility, what is covered.
            This is a QUESTION even if it contains the word "claim".
            Examples: "what can I claim?", "what policies can an employee claim?",
            "what's the travel limit for juniors?", "am I eligible for flights?",
            "how much can I claim for training?".
 
KEY RULE: If there is no specific amount the user personally spent, it is a QUESTION.
"What can I claim" = QUESTION. "I spent 5000" = CLAIM.
 
Return ONLY this JSON: {"intent": "CLAIM" or "QUESTION"}""",

        
        
      },
      {"role":"user","content":user_message},
      
    ],
    temperature=0.0,
    response_format={"type":"json_object"},
    
  )

  try: 
    return json.loads(response.choices[0].message.content).get(
      "intent","QUESTION"
      )
  except json.JSONDecodeError:
    return "QUESTION"
    
    
#GENERAL POLICY Q&A (answer from retrieved chunks)
def answer_policy_question(user_message: str) -> dict:
    """Answer a general policy question using RAG (no field extraction)."""
    chunks = query_policy(user_message, top_k=4)
 
    if not chunks:
        return {
            "answer": "I couldn't find anything in the policy document about that. Please rephrase or ask about a specific category (travel, accommodation, food, medical, fuel, training, etc.).",
            "policy_chunks_used": [],
        }
 
    policy_context = "\n\n---\n\n".join(chunks)
 
    prompt = f"""You are a helpful company expense policy assistant for ClaimFlow Inc.
 
RETRIEVED POLICY SECTIONS:
{policy_context}
 
EMPLOYEE QUESTION:
{user_message}
 
INSTRUCTIONS:
- Answer using ONLY the policy sections above. No outside knowledge.
- Be clear and concise. Use the actual numbers and limits from the policy.
- If the question is about a specific level, give that level's limits.
- If the policy sections don't cover the question, say so honestly.
- Quote the relevant limits but explain them in plain language.
 
Answer the employee's question directly and helpfully."""
 
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful, accurate expense policy assistant. Answer only from the provided policy context."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
 
    return {
        "answer": response.choices[0].message.content.strip(),
        "policy_chunks_used": chunks,
    }
       
  
def parse_claim_from_text(user_message: str) -> dict:
    """
    Uses Groq to extract structured claim data from natural language.
    """
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """Extract expense claim details from the user message.
Return ONLY this JSON, no extra text:
{
  "category": "Accommodation or Travel or Food or Medical or Fuel or Communication or Office Supplies or Training",
  "amount": number or null,
  "employee_level": "Junior or Senior or Manager or Director or null",
  "description": "brief description of the expense"
}
If any field is missing, set it to null.""",
            },
            {
                "role": "user",
                "content": user_message
            },
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def chat_with_policy(user_message: str, conversation_history: list = None) -> dict:
    """
    Conversational policy checker with memory of previous messages
    - Geneeral questions -> answer from policy (RAG)
    - Specific claim -> extract fields, check compliance
    """
    # Fix mutable default - create fresh list per call
    if conversation_history is None:
        conversation_history = []

    # Step 1: Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    
    
    
     # ROUTE: is this a question or a claim?
    intent = detect_intent(user_message)
 
    # --- GENERAL QUESTION: just answer ---
    if intent == "QUESTION":
        qa = answer_policy_question(user_message)
        conversation_history.append({"role": "assistant", "content": qa["answer"]})
        return {
            "status": "answered",
            "mode": "question",
            "bot_reply": qa["answer"],
            "conversation_history": conversation_history,
            "policy_chunks_used": qa["policy_chunks_used"],
        }
 

    # Step 2: Build full conversation context
    full_context = "\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in conversation_history
        if isinstance(m,dict) and 'role' in m and 'content' in m 
    ])

    # Step 3: Extract structured data from natural language
    claim_data = parse_claim_from_text(full_context)

    # Step 4: Check for missing required fields
    missing = [k for k, v in claim_data.items() if v is None]
    if missing:
        missing_questions = {
            "category": "What type of expense is this? (Travel, Accommodation, Food, Medical, Fuel, Communication, Office Supplies, Training and Education)",
            "amount": "How much did you spend? (amount in Rs)",
            "employee_level": "What is your employee level? (Junior, Senior, Manager, Director)",
            "description": "Can you briefly describe the expense?"
        }
        first_missing = missing[0]
        bot_reply = missing_questions[first_missing]

        conversation_history.append({
            "role": "assistant",
            "content": bot_reply
        })

        return {
            "status": "incomplete",
            "mode":"claim",
            "bot_reply": bot_reply,
            "conversation_history": conversation_history,
            "parsed_so_far": claim_data,
        }

    # Step 5: All fields found - run policy check (ONCE)
    result = check_claim_against_policy(claim_data)

    return {
        "status": "complete",
        "mode":"claim",
        "user_message": user_message,
        "parsed_claim": claim_data,
        "policy_check": result["policy_check"],   
        "conversation_history": conversation_history,
    }