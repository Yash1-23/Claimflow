
"""
Approval service - business logic for claim approval workflow.

This file holds the BRAIN of approve/reject.
The API file (claims.py) becomes a thin wrapper that just calls these.

No FASTAPI imports here.NO @router,NO HTTPException,NO Depends, services are pure python- they don't know HTTP exists.
"""
import uuid
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.models import ExpenseClaim, ApprovalStep, ApprovalAction
from app.schemas.schemas import ClaimStatus
from app.services.audit_service import log_action

def approve_claim_service(
  db:Session ,
  claim_id:UUID,
  approver_id:UUID
) -> ExpenseClaim:
  """_summary_
   Approve a submitted claim.
  Args:
      db (Session): _description_
      claim_id (UUID): _description_
      approver_id (UUID): _description_

  Raises:
      ValueError: On business rule violation (caller maps to HTTP errors)
  


  """
  
  #1. Find the claim
  claim = db.query(ExpenseClaim).filter(
    ExpenseClaim.id== claim_id
  ).first()
  
  if not claim:
    raise ValueError("Claim not found")
  
    
  #2. check status - only submitted claims can be approved
  if claim.status not in  (ClaimStatus.submitted,ClaimStatus.under_review):
    raise ValueError(
      f"Cannot approve claim with status '{claim.status.value}'."
      f"Only submitted or under_review claims can be approved."
    )
  
  #3. Update claims status & timestamp
  claim.status = ClaimStatus.approved
  claim.approved_at = datetime.utcnow() 
  
  #4. create approval step record (audit trail)
  approval_step =  ApprovalStep(
    id =uuid.uuid4(),
    claim_id =claim.id,
    approver_id =approver_id,
    step_order =1,
    action = ApprovalAction.approved,
    comments=None,
    acted_at = datetime.utcnow()
    
    
  )
  db.add(approval_step)
  
  
  log_action(
    db,
    user_id=approver_id,
    action="claim_approved",
    entity_type="expense_claims",
    entity_id=claim.id,
    old_value={"status":"submitted"},
    new_value={"status":"approved"}
  )
  #5. commit return updated claims
  db.commit()
  db.refresh(claim)
  return claim


def reject_claim_service(
  db:Session,
  claim_id:UUID,
  approver_id:UUID,
  comments:str, # rejection reason is required
  
  
)->ExpenseClaim:
  """Reject a submitted claim, Manager-Only action
     Rejection reason is required for audit trail.
  """
  
  #1. Find the claim
  claim = db.query(ExpenseClaim).filter(
    ExpenseClaim.id == claim_id
  ).first()
  
  if not claim:
    raise ValueError("Claim not found"
    )
    
  #2. Only submitted claims can be rejected
  if claim.status not in (ClaimStatus.submitted,ClaimStatus.under_review):
    raise ValueError(
      f"Cannot reject claim with status '{claim.status.value}'. Only submitted or under_review claim can be rejected."
      
    )
  #3. validate comments not empty
  if not comments or not comments.strip():
    raise ValueError(
    "Rejection reason is required"
    )
  
  #4.update status
  claim.status = ClaimStatus.rejected
  claim.rejected_at=datetime.utcnow()
  
  #5.Aduit trail
  approval_step = ApprovalStep(
    id=uuid.uuid4(),
    claim_id=claim.id,
    approver_id = approver_id,
    step_order=1,
    action=ApprovalAction.rejected,
    comments=comments,
    acted_at =datetime.utcnow()
  )
  db.add(approval_step)
  
  
  # add Audit log
  log_action(
    db,
    user_id=approver_id,
    action="claim_rejected",
    entity_type="expense_claims",
    entity_id=claim.id,
    old_value={"status": "submitted"},
    new_value={"status": "rejected", "reason": comments}
  )
  #6.commit
  db.commit()
  db.refresh(claim)
  return claim