""" Claims API endpoints"""
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


router = APIRouter()



@router.get("/pending", response_model=list[ClaimResponse])
def get_pending_claims(
    db : Session = Depends(get_db),
    current_user: User = Depends(get_current_manager)
):
    """
    Get all claims with status='submitted' waiting for manager approval.
    Only accessible by managers.
    """
    
    # 1. Query all submitted claims
    pending_claims = db.query(ExpenseClaim).filter(
        ExpenseClaim.status == ClaimStatus.submitted
    ).all()
    
    # 2. Return list
    return pending_claims


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
    ExpenseClaim.status == ClaimStatus.submitted
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
  
  #1. Find the claim
  claim = db.query(ExpenseClaim).filter(
    ExpenseClaim.id== claim_id
  ).first()
  
  if not claim:
    raise HTTPException(
      status_code = status.HTTP_404_NOT_FOUND,
      detail = "Claim not found"
    )
    
  #2. check status - only submitted claims can be approved
  if claim.status != ClaimStatus.submitted:
    raise HTTPException(
      status_code =status.HTTP_400_BAD_REQUEST,
      detail = f"Cannot approve claim with status '{claim.status.value}'. Only submitted claims can be approved"
    )
  
  #3. Update claims status & timestamp
  claim.status = ClaimStatus.approved
  claim.approved_at = datetime.utcnow() 
  
  #4. create approval step record (audit trail)
  approval_step =  ApprovalStep(
    id =uuid.uuid4(),
    claim_id =claim.id,
    approver_id =current_user.id,
    step_order =1,
    action = ApprovalAction.approved,
    comments=None,
    acted_at = datetime.utcnow()
    
    
  )
  db.add(approval_step)
  
  #5. commit return updated claims
  db.commit()
  db.refresh(claim)
  return claim

  
  
  
 
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



    