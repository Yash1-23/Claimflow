
""" 
Claims Service - Bussiness logic for claims

Why Service Layer?
- API route should only handle HTTP( request/response)
- Bussiness logic lives here (calculations, DB operations, orchestration)
- Easy to test without HTTP
"""

from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from app.services.rule_engine import run_rules
from sqlalchemy.orm import Session
from app.models.models import ExpenseClaim, ClaimLineItem,ClaimStatus
from app.schemas.schemas import ClaimCreate
from app.services.audit_service import log_action


def create_claim(db:Session, user_id: UUID,data: ClaimCreate) -> ExpenseClaim:
  # step1. calculate total from all line item
  total = sum(item.amount for item in data.line_items)
  
  #step 2:create the claim
  claim = ExpenseClaim(
    user_id = user_id,
    title=data.title,
    total_amount=total,
    status=ClaimStatus.draft
  )
  db.add(claim)
  db.flush() #ggets the claim.id  without  commiting
  
  #step 3: create each line item
  for item in data.line_items:
    line_item  = ClaimLineItem(
      claim_id = claim.id,
      category = item.category,
      description=item.description,
      amount=item.amount,
      expense_date = item.expense_date
      
    )
    db.add(line_item)
    
  db.commit()
  db.refresh(claim)
  return claim

def get_user_claims(db:Session,user_id:UUID)->list:
  return (
      db.query(ExpenseClaim)
      .filter(ExpenseClaim.user_id == user_id)
      .order_by(ExpenseClaim.created_at.desc())
      .all()
  )
  #fix None policy_violations for old records
  for claim in claims:
      if claim.policy_violations is None:
        claim.policy_violations =[]
  return claims
      
  

def get_claim_by_id(db:Session,claim_id:UUID, user_id:UUID)-> ExpenseClaim | None:
  return(
    db.query(ExpenseClaim)
    .filter(ExpenseClaim.id== claim_id,ExpenseClaim.user_id==user_id)
    .first()
  )
  
def submit_claim(db:Session,claim_id:UUID,user_id:UUID) -> ExpenseClaim:
  claim = get_claim_by_id(db,claim_id,user_id)
  
  if not claim:
    return None
  
  
  #Only draft claims can be submitted
  if claim.status != ClaimStatus.draft:
    raise ValueError(f"Claim is already {claim.status},cannot submit")
  
  # Gaurd : must have at least one lineitem 
  if not claim.line_items:
    raise ValueError("Claim must have at least on line item before submitting")


  # Run rules 
  decision = run_rules(claim,db)
  now = datetime.utcnow()
  
  #store all flags so manger sees them 
  claim.policy_violations= [
    {"severity":f.severity, "rule":f.rule,"message":f.message}
    for f in decision.flags
  ]
  
  if decision.final_decision== "rejected":
    #ony Block -level lands here (future dates, stale claim)
    claim.status = ClaimStatus.rejected
    claim.rejected_at=now
    claim.submitted_at=now
    log_action(
       db,
       user_id=user_id,
       action="claim_rejected_auto",
       entity_type="expense_claim",
       entity_id=claim.id,
       old_value={"status":"draft"},
       new_value={"status":"rejected","reason":"BLOCK rule triggered"}
     )
  else:
    # everything else -> manger review, with flags attached
    claim.status = ClaimStatus.submitted
    claim.submitted_at= now
    db.commit()
    db.refresh(claim)
    
    
    # Run multiagent orchestration : fraud -> policy -> approval -> save
    # The pipeline writes risk_score,agent_decision, agent_reasoning,
    # policy_violations, and sets status to under_review
    
    try:
      pipeline_result= run_claim_pipeline(db,claim)
    except Exception as e:
      # if the pipeline fails, the claim stays 'submitted' for manual review.
      pipeline_result = {"error":str(e)}
      
    db.refresh(claim)
    log_action(
      db,
      user_id=user_id,
      action="claim_submitted",
      entity_type="expense_claims",
      entity_id=claim.id,
      old_value={"status":"draft"},
      new_value={
        "status": claim.status.value if claim.status else "submitted",
        "agent_recommendation":claim.agent_decision,
        "risk_score":claim.risk_score,
      },
      
    )
    
  db.commit()
  db.refresh(claim)
  return claim
  
  
  
    
    
  