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
      "verdict": "flagged",
      "reason":"No matching policy found for this expense category. Needs manual review.",
      "policy_citation":"N/A",
      "allowed_limit":None
    }
    
  # step 4 Join chunks in to context block
  policy_context = "\n\n--\n\n".join(all_chunks)
  
  # step 5 strict prompt with all explicit "if not found " instruction
  prompt = f"""You are a strict expense policy compliance checker for ClaimFlow Inc.

RETRIEVED POLICY SECTIONS:
{policy_context}

EXPENSE CLAIM TO VALIDATE:
- Category: {claim_data['category']}
- Amount: Rs {claim_data['amount']}
- Employee Level: {claim_data['employee_level']}
- Description: {claim_data['description']}

STRICT RULES:
1. Use ONLY the policy sections above. Do NOT use any outside knowledge.
2. If the retrieved sections do not mention this category or limit, set verdict to "flagged".
3. Always copy the exact policy line you used in policy_citation.
4. Never guess a limit that is not written above.
5. CRITICAL: Extract the numeric limit from policy. Compare mathematically:
   - claim amount <= limit → approved
   - claim amount > limit → rejected
   - limit unclear → flagged

BEFORE answering, do this check:
- Policy limit found: [extract the number]
- Claim amount: Rs {claim_data['amount']}
- Is {claim_data['amount']} <= limit? → verdict

Respond in this exact JSON format (no extra text):
{{
  "verdict": "approved" or "flagged" or "rejected",
  "reason": "Policy limit is Rs X, claim amount is Rs {claim_data['amount']}, which is [within/above] the limit.",
  "policy_citation": "copy the exact policy text used",
  "allowed_limit": "numeric limit from policy or null"
}}
"""
  

   #step 6 Call Groq
  response = client.chat.completions.create(
  model = "llama-3.3-70b-versatile",
  messages = [
      {
        "role":"system",
        "content": "You are a policy compliance checker.Answer strictly in JSON only. No preamble, no explanation outside JSON."
      },
      {
        "role":"user",
        "content":prompt
      }
    ],
    temperature=0.0,
    response_format={"type":"json_object"}
    
  )
  
  try:
    result = json.loads(response.choices[0].message.content)
    return {
      "claim": claim_data,
      "policy_check": result,
      "policy_chunks_used":all_chunks
    }
  except json.JSONDecodeError:
    return {
      "verdict":"flagged",
      "reason":"Policy agent returned invalid response.Needs manual review.",
      "policy_citation":"N/A",
      "allowed_limit":None
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
  "category": "Accommodation or Travel or Food or Medical or Fuel or Communication or Office Supplies",
  "amount": number or null,
  "employee_level": "Junior or Senior or Manager or Director or null",
  "description": "brief description of the expense"
}
If any field is missing, set it to null."""
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        temperature=0.0,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def chat_with_policy(user_message: str, conversation_history: list = None) -> dict:
    """
    Conversational policy checker with memory of previous messages
    """
    # Fix mutable default - create fresh list per call
    if conversation_history is None:
        conversation_history = []

    # Step 1: Add user message to history
    conversation_history.append({
        "role": "user",
        "content": user_message
    })

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
            "bot_reply": bot_reply,
            "conversation_history": conversation_history,
            "parsed_so_far": claim_data
        }

    # Step 5: All fields found - run policy check (ONCE)
    result = check_claim_against_policy(claim_data)

    return {
        "status": "complete",
        "user_message": user_message,
        "parsed_claim": claim_data,
        "policy_check": result["policy_check"],   
        "conversation_history": conversation_history
    }