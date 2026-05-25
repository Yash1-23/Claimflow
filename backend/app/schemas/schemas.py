"""
Pydantic schemas - define the shape of API requests and responses.

DIFFERENCE FROM MODELS:
- models.py = database tables (SQLALchemy)
-schema.py = JSON shapes for API (Pydantic)

WHy we need both:
- Block invalid input (eg. bad email format)
- Hide sensitive fields (eg.password hash)
- Auto- generate swagger docs
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime,date
from uuid import UUID
from enum import Enum


# Enums
class UserRole(str, Enum):
   employee ="employee"
   manager = "manager"
   finance = "finance"
   admin = "admin"
   
class ClaimStatus(str,Enum):
  draft= "draft"
  submitted = "submitted"
  under_review ="under_review"
  approved = "approved"
  rejected = "rejected"
  paid ="paid"
  

class ExpenseCategory(str, Enum):
  travel = "travel"
  food = "food"
  transport = "transport"
  accommodation = "accommodation"
  other = "other"
  
#User Schema
class UserRegister(BaseModel):
  email: EmailStr
  password : str = Field(min_length=6)
  full_name:str
  role:UserRole = UserRole.employee
  


class UserLogin(BaseModel):
  email:EmailStr
  password:str
  
class UserResponse(BaseModel):
  id :UUID
  email:str
  full_name:str
  role:UserRole
  is_active:bool
  created_at:datetime
  
  class Config:
    from_attributes =True 
    
class UserBrief(BaseModel):
  """Minimal user info for embedding in other responses"""
  id :UUID
  full_name :str
  email:str
  
  class Config:
    from_attributes = True 
class TokenResponse(BaseModel):
  access_token:str
  token_type:str= "bearer"
  
#claims schema
class LineItemCreate(BaseModel):
  category: ExpenseCategory
  description: str
  amount : float =Field(gt=0)
  expense_date :date
  
  
class ClaimCreate(BaseModel):
    title:str
    line_items: List[LineItemCreate]
  
class LineItemResponse(BaseModel):
    id: UUID
    category: ExpenseCategory
    description: str
    amount: float
    expense_date: date
  
  
    class Config:
      from_attributes=True
  
class ClaimResponse(BaseModel):
  id: UUID
  title:str
  total_amount:float
  description:Optional[str]
  currency :str
  status: ClaimStatus
  submitted_at:Optional[datetime]
  approved_at:Optional[datetime]
  created_at : datetime
  line_items: List[LineItemResponse] = []
  user: Optional[UserBrief]=None
  class Config:
    from_attributes =True
    
class ReceiptResponse(BaseModel):
  """Response when receipts is uploaded or fetched"""
  id : UUID
  line_item_id: UUID
  file_name:str
  file_url:str
  file_size:Optional[int] = None
  mime_type: Optional[str]=None
  
  extracted_amount:Optional[float] =None
  extracted_date:Optional[date]=None
  extracted_merchant:Optional[str]=None
  ocr_confidence:Optional[float]=None
  
  uploaded_at: datetime
  uploaded_by:UUID
  
  class Config:
    from_attributes=True
    

    
    
    
    
  
  
  
