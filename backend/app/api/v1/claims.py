""" Claims API endpoints - thin HTTP Handlers, bussiness logic lives in services folder"""
import uuid
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.orm import Session, joinedload
from uuid import UUID
from app.core.security import get_current_user,get_current_manager
from app.core.database import get_db
from datetime import datetime
from app.models.models import User,ApprovalAction,ApprovalStep,ExpenseClaim,ClaimLineItem
from app.schemas.schemas import ClaimCreate, ClaimResponse,ClaimStatus
from app.services.claim_service import (
  create_claim,
  get_user_claims,
  get_claim_by_id,
  submit_claim
)
from app.services.audit_service import log_action
from app.services.approval_service import approve_claim_service,reject_claim_service

router = APIRouter()


@router.post("/", response_model=ClaimResponse)
def create_new_claim(
  data:ClaimCreate,
  db:Session = Depends(get_db),
  current_user: User =Depends(get_current_user)
):
  
  return create_claim(db,current_user.id,data)

@router.get("/",response_model=list[ClaimResponse])
def list_my_claims(
  db:Session = Depends(get_db),
  current_user :User =Depends(get_current_user)
):
  return get_user_claims(db, current_user.id)



@router.get("/pending",response_model=list[ClaimResponse])
def get_pending_claims(
  db:Session = Depends(get_db),
  current_user:User = Depends(get_current_manager) # it checks the role user or manager
):
  """ Get all claims with status='submitted wating for manager approval.
      ONLY accessible by managers
  """
  
  #1. Query all submitted claims
  pending_claims = db.query(ExpenseClaim).options(
    joinedload(ExpenseClaim.user),
    joinedload(ExpenseClaim.line_items)
    ).filter(
    ExpenseClaim.status.in_([ClaimStatus.submitted,ClaimStatus.under_review])
  ).all()
  
  return pending_claims
  
  
  
@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claims(
  claim_id: UUID,
  db:Session =Depends(get_db),
  current_user: User =Depends(get_current_user)
):
  claim = get_claim_by_id(db, claim_id, current_user.id)
  if not claim:
    raise HTTPException(status_code=404, detail="Claim not found")
  return claim

@router.post("/{claim_id}/submit",response_model=ClaimResponse)
def submit(
  claim_id:UUID,
  db:Session= Depends(get_db),
  current_user :User =Depends(get_current_user)
  
):
  try:
    claim = submit_claim(db,claim_id,current_user.id)
    if not claim:
      raise HTTPException(status_code=404, detail="Claim not found")
    return claim
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
  
 
 
@router.post("/{claim_id}/approve", response_model = ClaimResponse)
def approve_claim(
  claim_id:UUID,
  db:Session = Depends(get_db), 
  current_user :User= Depends(get_current_manager)
):
  """ Approve a submitted claim. Manager-Only action.
      Records approval in ApprovalStep table for audit trail.
  """
  try:
    return approve_claim_service(db,claim_id,current_user.id)
  except ValueError as e:
    if "not found" in str(e).lower():
      raise HTTPException(status_code=404, detail=str(e))
    raise HTTPException(status_code=400,detail=str(e))
  
  
 

  
@router.post("/{claim_id}/reject", response_model=ClaimResponse)
def reject_claim(
  claim_id:UUID,
  comments:str, # rejection reason is required
  db:Session= Depends(get_db),
  current_user:User=Depends(get_current_manager)
  
):
  """Reject a submitted claim, Manager-Only action
     Rejection reason is required for audit trail.
  """
 
  try:
      return reject_claim_service(db, claim_id, current_user.id, comments)
  except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
  

@router.delete("/{claim_id}", status_code=status.HTTP_204_NO_CONTENT) 
def delete_claim(
  claim_id: UUID,
  db:Session =Depends(get_db),
  current_user: User =Depends(get_current_user)
):
  """ Delete the claim. Only the owner can delete,and only if status is 'draft"""
  
  #find the claim
  claim = db.query(ExpenseClaim).filter(
    ExpenseClaim.id == claim_id
  ).first()
  
  
  #check if exists
  if not claim:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail="Claim not found"
    )
  
  # check ownership
  if claim.user_id !=current_user.id:
    raise HTTPException(
      status_code= status.HTTP_403_FORBIDDEN,
      detail="You don't have permission to delete this claim"
    )
    
  
  # only allow delete id status is 'draft'
  if claim.status != ClaimStatus.draft:
    raise HTTPException(
      status_code = status.HTTP_400_BAD_REQUEST,
      detail = f"Cannot delete claim with status '{claim.status.value}',Only draft claims can be deleted."
      
    )
    
  # Delete line item first (FK constriant)
  db.query(ClaimLineItem).filter(
    ClaimLineItem.claim_id==claim_id
  ).delete()
  
  db.delete(claim)
  db.commit()
  
  return None



    