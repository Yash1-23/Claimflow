import uuid
from datetime import datetime 
from sqlalchemy import (
  Column, String, DateTime,Float,Integer,Boolean,ForeignKey,Enum,Text,Date
)

from sqlalchemy.dialects.postgresql import UUID, JSONB,JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum # for fixed choice like status of claim can be only approved/draft/submitted


class UserRole(str,enum.Enum):
  employee ="employee" 
  manager = "manager"
  finance = "finance"
  admin = "admin"
  
class ClaimStatus(str, enum.Enum):
  draft = "draft"
  submitted = "submitted"
  under_review ="under_review"
  approved ="approved"
  rejected = "rejected"
  paid  = "paid"
  
  
class ExpenseCategory(str, enum.Enum):
  travel = "travel"
  food = "food"
  transport = "transport"
  accommodation = "accommodation"
  other = "other"
  
class ApprovalAction(str, enum.Enum):
  pending = "pending"
  approved = "approved"
  rejected = "rejected"
  

class PolicyCategory(str, enum.Enum):
  travel = "travel"
  food = "food"
  office = "office"
  transport = "transport"
  accommodation= "accommodation"
  other = "other"

  

class User(Base):
  __tablename__ = "users"
  
  
  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  email = Column(String(255), unique=True, nullable=False)
  password_hash = Column(String(255), nullable=False)
  full_name = Column(String(255), nullable=False)
  role = Column(Enum(UserRole),default=UserRole.employee)
  department_id = Column(UUID(as_uuid=True),ForeignKey("departments.id"), nullable=True)
  is_active = Column(Boolean, default=True)
  created_at = Column(DateTime, default=datetime.utcnow) 
  
  department = relationship("Department", back_populates="users",foreign_keys=[department_id])
  claims = relationship("ExpenseClaim", back_populates="user")
   
  
  
class Department(Base):
  __tablename__ = "departments"
  
  id = Column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
  name = Column(String(100), unique=True, nullable=False)
  manager_id  = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True)
  
  users = relationship("User", back_populates="department",foreign_keys="User.department_id") 
  
  
  
class ExpenseClaim(Base):
  __tablename__ = "expense_claims"
  
  
  id = Column(UUID(as_uuid=True),primary_key=True, default=uuid.uuid4)
  user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"),nullable=False)
  title = Column(String(255),nullable=False)
  description = Column(Text, nullable=True)
  total_amount = Column(Float, nullable=False)
  currency = Column(String(3), default="INR")
  status = Column(Enum(ClaimStatus), default=ClaimStatus.draft)
  risk_score = Column(Integer, default=0)
  policy_violations = Column(JSONB, default=list)
  submitted_at = Column(DateTime, nullable=True)
  approved_at = Column(DateTime, nullable=True)
  created_at = Column(DateTime, default = datetime.utcnow)
  
  
  user = relationship("User", back_populates="claims")
  line_items = relationship("ClaimLineItem", back_populates="claim")
  approval_steps = relationship("ApprovalStep", back_populates="claim")
  
  
class ClaimLineItem(Base):
  __tablename__ = "claim_line_items"
    
    
  id = Column(UUID(as_uuid=True),primary_key=True, default=uuid.uuid4)
  claim_id = Column(UUID(as_uuid=True), ForeignKey("expense_claims.id"),nullable=False)
  category = Column(Enum(ExpenseCategory), nullable=True)
  description= Column(String(300), nullable=True)
  amount = Column(Float, nullable=False)
  expense_date = Column(Date, nullable=False)
  is_flagged = Column(Boolean, default=False)
  flag_reason = Column(String(255), nullable=True)
    
    
  claim = relationship("ExpenseClaim", back_populates="line_items")
  receipts = relationship("Receipt",back_populates="line_item",cascade="all, delete-orphan")
        
# this tables stores uploaded receipt files AI extracted data from OCR     
class Receipt(Base):
    __tablename__ = "receipts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    line_item_id = Column(UUID(as_uuid=True), ForeignKey("claim_line_items.id", ondelete="CASCADE"), nullable=False)
    
    # File info
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_url = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(50), nullable=True)
    
    # AI extracted data (OCR agent)
    extracted_amount = Column(Float, nullable=True)
    extracted_date = Column(Date, nullable=True)
    extracted_merchant = Column(String(255), nullable=True)
    ocr_confidence = Column(Float, nullable=True)
    
    # Metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Relationships
    line_item = relationship("ClaimLineItem", back_populates="receipts")
    uploader = relationship("User")
  
# defines spending limits of each category
class Policy(Base):
  __tablename__ = "policies"
  
  id = Column(UUID(as_uuid=True), primary_key=True, default= uuid.uuid4)
  name = Column(String(100), nullable=False)
  category = Column(Enum(ExpenseCategory),nullable=False)
  max_amount = Column(Float, nullable=False)
  description = Column(String(500), nullable=True)
  is_active =Column(Boolean, default=True)
  created_at = Column(DateTime, default=datetime.utcnow)
  

class ApprovalStep(Base):
  __tablename__ = "approval_steps"
  
  
  id = Column(UUID(as_uuid=True), primary_key =True, default=uuid.uuid4)
  claim_id = Column(UUID(as_uuid=True),ForeignKey("expense_claims.id"), nullable=False)  
  approver_id = Column(UUID(as_uuid=True),ForeignKey("users.id"), nullable=False)
  
  
  step_order = Column(Integer,nullable=False) # 1st, 2nd, 3rd approver
  action  = Column(Enum(ApprovalAction),default=ApprovalAction.pending)
  comments = Column(String(500), nullable=True)
  acted_at = Column(DateTime, nullable=True)
  
  claim = relationship("ExpenseClaim", back_populates="approval_steps")
 
 
# It tracks every action taken on claims  
class AuditLog(Base):
  __tablename__ = "audit_logs"
  
  
  id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  user_id = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True)
  action = Column(String(100), nullable=False)
  entity_type = Column(String(50), nullable=False)
  entity_id = Column(UUID(as_uuid=True), nullable=True)
  old_value = Column(JSON,nullable=True)
  new_value = Column(JSON,nullable=True)
  timestamp = Column(DateTime, default=datetime.utcnow)
  
  user = relationship("User")
  

  
  