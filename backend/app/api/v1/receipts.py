"""Receipts API endpoints"""

import os
from typing import List
import uuid
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,status, UploadFile,File
from sqlalchemy.orm import Session
from uuid import UUID

from  app.core.security import get_current_user
from app.core.database import get_db
from app.models.models import User,ExpenseClaim,ClaimLineItem,Receipt,ClaimStatus
from app.schemas.schemas import ReceiptResponse

router = APIRouter()

UPLOAD_DIR =Path("uploads/receipts")
UPLOAD_DIR.mkdir(parents=True,exist_ok=True)

ALLOWED_MIME_TYPES = {"image/jpeg","image/jpg","image/png","application/pdf"}
MAX_FILE_SIZE = 5*1024*1024 # 5 MB


@router.post("/upload/{line_item_id}",response_model=ReceiptResponse,status_code=status.HTTP_201_CREATED)
async def upload_receipt(
  line_item_id:UUID,
  file:UploadFile =File(...),
  db:Session = Depends(get_db),
  current_user: User = Depends(get_current_user)
):
  """Upload a receipt file for a line item"""
  
  #1. Find line item
  line_item = db.query(ClaimLineItem).filter(ClaimLineItem.id==line_item_id).first()
  if not line_item:
    raise HTTPException(status_code=404, detail="Line item not found ")
  
  # 2. Check ownership via claim
  claim = db.query(ExpenseClaim).filter(ExpenseClaim.id==line_item.claim_id).first()
  if claim.user_id != current_user.id:
    raise HTTPException(status_code=403,detail="Not your claim")
  
  #3. Only draft claim
  if claim.status != ClaimStatus.draft:
    raise HTTPException(status_code=400,detail="Can only upload to draft claims")
  
  #4. validate file type
  if file.content_type not in ALLOWED_MIME_TYPES:
    raise HTTPException(status_code=400, detail="Invalid file type. Allowess: jpeg,jpg,png,pdf")
  
  
  #5. Read & validate size
  contents = await file.read()
  if len(contents) > MAX_FILE_SIZE:
    raise HTTPException(status_code=400, detail="File too large. MAX 5MB") 
  
  
  #6. save file with unique name
  file_extension =os.path.splitext(file.filename)[1]
  unique_filename= f"{uuid.uuid4()}{file_extension}" 
  file_path = UPLOAD_DIR / unique_filename
  
  with open(file_path, "wb") as f:
    f.write(contents)
    
  #7. save to db
  new_receipt = Receipt(
    id=uuid.uuid4(),
    line_item_id=line_item_id,
    file_name=file.filename, 
    file_path=str(file_path),
    file_url=f"/uploads/receipts/{unique_filename}",
    file_size=len(contents),
    mime_type=file.content_type,
    uploaded_by=current_user.id
     
  )
  
  db.add(new_receipt)
  db.commit()
  db.refresh(new_receipt)
  
  return new_receipt


@router.get("/{receipt_id}", response_model=ReceiptResponse)
def get_receipt(
  receipt_id:UUID,
  db:Session = Depends(get_db),
  current_user:User = Depends(get_current_user)
  
):
  """ Get a single receipt by ID"""
  
  #1. Find the Receipt
  receipt = db.query(Receipt).filter(Receipt.id==str(receipt_id)).first()
  if not receipt:
    raise HTTPException(status_code=404, detail="Receipt not found")
  
  #2.check the onwership receipt -> line item-> claim->user
  if receipt.line_item.claim.user_id!= current_user.id:
    raise HTTPException(status_code=403,detail="Not your receipt")
  
  
  return receipt
  
#Get all receipts for a line item
@router.get("/line-item/{line_item_id}", response_model=List[ReceiptResponse])
def get_receipts_for_line_item(
  line_item_id:UUID,
  db:Session =Depends(get_db),
  current_user:User =Depends(get_current_user)
):
  
  """ List all receipts attached to a secific line item"""
  
  # 1. verify line item exists and user owns the claim
  line_item = db.query(ClaimLineItem).filter(
    ClaimLineItem.id==str(line_item_id)
  ).first()
  
  if not line_item:
    raise HTTPException(status_code=404,detail="Line item not found")
  
  if line_item.claim.user_id != current_user.id:
    raise HTTPException(status_code=403,detial="Not your line item")
  
  #2. return all receipts for this line item
  receipts = db.query(Receipt).filter(
    Receipt.line_item_id== str(line_item_id)
  ).all()
  
  return receipts

# Adding a delete endpoint
@router.delete("/{receipts_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
  receipt_id :UUID,
  db:Session = Depends(get_db),
  current_user:User = Depends(get_current_user)
):
  
  ## Delete a single receipt (Onlt if claim is still in draft).
  
  #1.Find the receipt
  receipt = db.query(Receipt).filter(Receipt.id==str(receipt_id)).first()
  if not receipt:
    raise HTTPException(status_code=404, detail="Receipt not found")
  
  #2. Check ownership
  if receipt.line_item.claim.user_id != current_user.id:
    raise HTTPException(status_code=403, detail="Not your receipt")
  
  #3. check claim is still draft (can't modify submitted claim)
  if receipt.line_item.claim.status!=ClaimStatus.draft:
    raise HTTPException(
      status_code=400,
      detail="Cannot delete receipt of submitted/approved claim"
    )
    
  #4. delete pyhsical file from disk
  if receipt.file_path and os.path.exists(receipt.file_path):
    os.remove(receipt.file_path)
    
    
  # delete db record
  db.delete(receipt)
  db.commit()