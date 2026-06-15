"""
  Claim pipline - LangGraph Orchestrator 
  
  Runs the agent pipeline when an employee submits a claim.
     
     fraud_node -> policy_node -> approval_node -> save_node
     
     
  Each node reads/writes a shares state dict. The orchestrator calls your existing agent functions - it does Not reimplement them.
  
After the pipeline runs, the claim status is set to under_review and it waits in the managers queue (human-in-the-loop) 
 - risk score + fraud severity 
 - policy verdict + citation
 - recommendation + priority

The manager then approve/rejects via the existing endpoints
    
"""

from typing import TypedDict, Optional,List
from langgraph.graph import StateGraph,START,END
from sqlalchemy.orm import SQLORMExpression
from datetime import datetime
from app.services.fraud_service import score_claim_fraud_risk,create_fraud_alert_if_needed
from app.agents.policy_agent import check_claim_against_policy
from app.agents.approval_agent import recommend_for_manager
from app.models.models import ClaimStatus



# shared state

class ClaimPipelineState(TypedDict):
  claim_id:str
  
  fraud_score: Optional[float]
  fraud_severity:Optional[str]
  fraud_rules:Optional[str]
  policy_verdict:Optional[str]
  policy_reason: Optional[str]
  recommendation:Optional[str]
  rec_priority:Optional[str]
  rec_reason:Optional[str]
  error:Optional[str]
  
  
#Nodes

def fraud_node(state:ClaimPipelineState,config) ->dict:
  """Run the rule-based fraud agent"""
  
  db = config["configurable"]["db"]
  claim = config["configurable"]["claim"]
  
  try:
    result = score_claim_fraud_risk(db,claim)
    create_fraud_alert_if_needed(db,claim,result)
    return {
      "fraud_score": result["fraud_score"],
      "fraud_severity":result["severity"],
      "fraud_rules": result["triggered_rules"],
    }
    
  except Exception as e:
    return {"error": f"fraud analysis failed:{e}"}
  

def policy_node(state:ClaimPipelineState,config) ->dict:
  """Run the policy RAG agent over ALL line-item categories"""
  
  if state.get("error"):
    return {}
  claim = config["configurable"]["claim"]
  try:
    line_items = claim.line_items
    # collect all categories
    categories = [
      li.category.value for li in line_items if li.category
    ] or ["other"]
    category_str = ", ".join(sorted(set(categories)))
    
    
    employee_level = (
      claim.user.employee_level.value
      if claim.user and claim.user.employee_level
      else "junior"
    )
    
    claim_data = {
      "category":category_str,
      "amount":float(claim.total_amount),
      "employee_level": employee_level,
      "description":claim.description or claim.title or "",
    }
    result = check_claim_against_policy(claim_data)
    verdict_block= result.get("policy_check",{})
    return {
      "policy_verdict":verdict_block.get("verdict","flagged"),
      "policy_reason":verdict_block.get("reason",""),
    }
    
  except Exception as e:
    return {"policy_verdict":"flagged","policy_verdict":f"policy check erro:{e}"}


def approval_node(state:ClaimPipelineState,config)->dict:
  """Run the approval recommendaiton logic"""
  
  claim = config["configurable"]["claim"]
  
  # if fraud analysis failed surface it to manager 
  if state.get("error"):
    return {
      "recommendation":"REVIEW_CAREFULLY",
      "rec_priority": "high",
      "rec_reason": f"Automated analysis incomplete : {state['error']}.Manual review required",
    }  
    
  if state.get("fraud_score") is None:
    return {
      "recommendation": "REVIEW_CAREFULLY",
      "rec_priority":"high",
      "rec_reason": "Fraud analysis unavailable.Manual review required.",
    }
    
  rec =  recommend_for_manager(
    total_amount = float(claim.total_amount),
    risk_score = state.get("fraud_score") or 0.0,
    policy_verdict= state.get("policy_verdict") or "flagged",
  )
  
  return {
    "recommendation":rec["recommendation"],
    "rec_priority":rec["priority"],
    "rec_reason":rec["reason"],
  }
  
  

def save_node(state: ClaimPipelineState,config) ->dict:
  """ persist all agents results onto the claim, set staus under_review"""
  db = config["configurable"]["db"]
  claim = config["configurable"]["claim"]
  
  try:
    claim.risk_score = state.get("fraud_score") or 0.0
    claim.agent_decision = state.get("recommendation")
    claim.agent_reasoning = state.get("rec_reason")
    claim.policy_violations={
      "policy_verdict":state.get("policy_verdict"),
      "policy_reason":state.get("policy_reason"),
      "fraud_severity":state.get("fraud_severity"),
      "fraud_rules":state.get("fraud_rules"),
      "recommendation":state.get("recommendation"),
      "priority":state.get("rec_priority"),
      "processed_at": datetime.utcnow().isoformat(),
      
    }
    
    claim.status = ClaimStatus.under_review
    db.commit()
    db.refresh(claim)
    return {"pipeline_status":"completed"}
  except Exception as e:
    db.rollback()
    return {"error":f"save failed: {e}","pipeline_status":"failed"}
  
  
  
# build graph
def build_claim_pipeline():
  graph = StateGraph(ClaimPipelineState)
  graph.add_node("fraud",fraud_node)
  graph.add_node("policy",policy_node)
  graph.add_node("approval",approval_node)
  graph.add_node("save",save_node)
  
  
  graph.add_edge(START,"fraud")
  graph.add_edge("fraud","policy")
  graph.add_edge("policy","approval")
  graph.add_edge("approval","save")
  graph.add_edge("save",END)
  
  return graph.compile()

 
_pipeline = build_claim_pipeline()   


def run_claim_pipeline(db,claim) ->dict:
  """
  Run the full agent pipeline on a claim
  Return the final pipeline state (for logging/debugging)
  """
  
  initial_state = {"claim_id":str(claim.id)}
  config = {"configurable":{"db":db,"claim":claim}}
  
  return _pipeline.invoke(initial_state,config=config)
    



  