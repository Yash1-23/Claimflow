""" Claims API endpoints"""

from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.security import get_current_user
from app.core.database import get_db
from app.schemas.schemas import ClaimCreate, ClaimResponse
from app.services.claim_service import (
  create_claim,
  get_user_claims,
  get_claim_by_id,
  submit_claim
)

from app.models.models import User

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


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claims(
  claim_id: UUID,
  db:Session =Depends(get_db),
  current_user: User =Depends(get_current_user)
):
  claim = get_claim_by_id(db, claim_id, current_user.id)
  if not claim:
    raise HTTPException(status_code=404, details="Claim not found")
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
  
  