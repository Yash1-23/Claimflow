
""" 
Claims Service - Bussiness logic for claims

Why Service Layer?
- API route should only handle HTTP( request/response)
- Bussiness logic lives here (calculations, DB operations)
- Easy to test without HTTP
"""

from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import ExpenseClaim, ClaimLineItem,ClaimStatus
from app.schemas.schemas import ClaimCreate


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
      .filter(ExpenseClaim)
      .order_by(ExpenseClaim.user_id == user_id)
      .all()
  )
  

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
  
  claim.status = ClaimStatus.submitted
  claim.submitted_at = datetime.utcnow()
  
  
  db.commit()
  db.refresh(claim)
  return claim
  
  
  
    
    
  