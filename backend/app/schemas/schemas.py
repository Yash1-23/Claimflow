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
  status: ClaimStatus
  created_at : datetime
  line_items: List[LineItemResponse] = []
  
  class Config:
    from_attributes =True
    
    
    
  
  
  
