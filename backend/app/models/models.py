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
  
class EmployeeLevel(str, enum.Enum):
  L1_L3 = "L1-L3"    #Junior
  L4_L6  = "L4-L6"   # Senior
  L7_L9  = "L7-L9"   # Manager
  L10_UP = "L10+"     # Director and above
class ClaimStatus(str, enum.Enum):
  draft = "draft"
  submitted = "submitted"
  under_review ="under_review"
  approved ="approved"
  rejected = "rejected"
  paid  = "paid"
  on_hold      = "on_hold"      # waiting for more docs
  escalated    = "escalated"    # approver missed SLA
  appealed     = "appealed"     # employee contested rejection
  fraud_alert  = "fraud_alert"  # AI flagged suspicious

  
  
class ExpenseCategory(str, enum.Enum):
    travel              = "travel"
    food                = "food"
    transport           = "transport"
    accommodation       = "accommodation"
    fuel                = "fuel"
    office_supplies     = "office_supplies"
    communication_bills = "communication_bills"
    medical             = "medical"
    training            = "training"
    other               = "other"
  
  
class ApprovalAction(str, enum.Enum):
  pending = "pending"
  approved = "approved"
  rejected = "rejected"
  on_hold =  "on_hold"
  

class BeneficiaryType(str, enum.Enum):
    self_  = "self"
    spouse = "spouse"
    child  = "child"
    parent = "parent"

class CityTier(str, enum.Enum):
    metro         = "metro"
    tier2         = "tier2"
    tier3         = "tier3"
    international = "international"
class FraudSeverity(str, enum.Enum):
    low      = "low"       # 0.0 - 0.3
    medium   = "medium"    # 0.3 - 0.6
    high     = "high"      # 0.6 - 0.8
    critical = "critical"  # 0.8 - 1.0


  

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
  
  # employee level for policy limits
  employee_level = Column(Enum(EmployeeLevel),default=EmployeeLevel.L1_L3, nullable=True)
  
  #relationship
  department = relationship("Department", back_populates="users",foreign_keys=[department_id])
  claims = relationship("ExpenseClaim", back_populates="user")
   
  

#Department
class Department(Base):
  __tablename__ = "departments"
  
  id = Column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
  name = Column(String(100), unique=True, nullable=False)
  manager_id  = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=True)
  
  #department BAU code for project code requirement eg: BAU-ENF-2026,
  bau_code = Column(String(50),nullable=True)
  users = relationship("User", back_populates="department",foreign_keys="User.department_id") 
  manager = relationship("User",foreign_keys=[manager_id])
  
  
class ExpenseClaim(Base):
  __tablename__ = "expense_claims"
  
  
  id = Column(UUID(as_uuid=True),primary_key=True, default=uuid.uuid4)
  user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"),nullable=False)
  title = Column(String(255),nullable=False)
  description = Column(Text, nullable=True)
  total_amount = Column(Float, nullable=False)
  currency = Column(String(3), default="INR")
  status = Column(Enum(ClaimStatus), default=ClaimStatus.draft,nullable=False)
  risk_score = Column(float, default=0) # 0.0 to 1.0 fraud score
  policy_violations = Column(JSONB, default=list)
  submitted_at = Column(DateTime, nullable=True)
  approved_at = Column(DateTime, nullable=True)
  rejected_at = Column(DateTime,nullable=True)
  created_at = Column(DateTime, default = datetime.utcnow)
  
   # project code — required for claims above Rs 1000
  project_code = Column(String(50), nullable=True)  # PRJ-2026-042
  
  # AI agent decision and RAG reasoning
  agent_decision    = Column(String(20), nullable=True)  # approve/reject/escalate
  agent_reasoning   = Column(Text, nullable=True)        # LLM explanation
  rag_policy_chunks = Column(JSONB, nullable=True)        # match policy chunks

  #payment tracking
  paid_at = Column(DateTime, nullable=True)
  payment_reference = Column(String(100),nullable=True)
  
  
  #appealing tracking
  appeal_deadline= Column(DateTime,nullable=True) #7 days from rejection
  appeal_reason = Column(Text, nullable=True)
  
  # on holding tracking
  on_hold_reason =  Column(Text,nullable=True)
  on_hold_deadline = Column(DateTime,nullable=True) # employee has 5 days to response
  
  #relationships
  user = relationship("User", back_populates="claims")
  line_items = relationship("ClaimLineItem", back_populates="claim",cascade="all, delete-orphan")
  approval_steps = relationship("ApprovalStep", back_populates="claim")
  fraud_alerts = relationship("FraudAlert",back_populates="claim") 
  
class ClaimLineItem(Base):
  __tablename__ = "claim_line_items"
    
    
  id = Column(UUID(as_uuid=True),primary_key=True, default=uuid.uuid4)
  claim_id = Column(UUID(as_uuid=True), ForeignKey("expense_claims.id"),nullable=False)
  category = Column(Enum(ExpenseCategory), nullable=False)
  description= Column(String(300), nullable=True)
  amount = Column(Float, nullable=False)
  expense_date = Column(Date, nullable=False)
  is_flagged = Column(Boolean, default=False)
  flag_reason = Column(String(255), nullable=True)
    
    
  # Which policy was applied for this line item
  policy_id =  Column(UUID(as_uuid=True), ForeignKey("policies.id"),nullable=True)
  
  #for medical claims - who is beneficiary
  beneficiary_type = Column(Enum(BeneficiaryType),nullable=True)
  
  
  # for accomodation/travel - wich city tier
  city_tier = Column(Enum(CityTier), nullable=True)
  
  
  # OCR vs claimed amount mismatch tracking
  claimed_amount = Column(Float, nullable=True)
  extracted_amount = Column(Float,nullable=True)
  amount_mismatch = Column(Boolean,default=False)
  
  #relationships    
  claim = relationship("ExpenseClaim", back_populates="line_items")
  policy = relationship("Policy")
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
    
    # Ai image tamper detection
    is_tampered = Column(Boolean,nullable=True)
    tamper_confidence= Column(Float, nullable=True)
    
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
  description = Column(String(500), nullable=True)
  file_path =Column(String,nullable=True)
  policy_text = Column(Text, nullable=True)
  is_active =Column(Boolean, default=True)
  created_by = Column(UUID(as_uuid=True),ForeignKey("users.id"),nullable=False)
  
  created_at = Column(DateTime, default=datetime.utcnow)
  updated_at = Column(DateTime, default=datetime.utcnow,onupdate=datetime.utcnow)
  
  #policy identity
  policy_code =  Column(String(50),unique=True,nullable=True)
  version = Column(String(10),default="1.0")
  effective_date = Column(DateTime, nullable=True)
  review_date = Column(DateTime,nullable=True)
  
  #amount limits-multiple types from PDF
  max_amount_per_claim = Column(Float,nullable=True)
  max_amount_per_year   = Column(Float, nullable=True)
  max_amount_per_event  = Column(Float, nullable=True)
  hospitalization_limit = Column(Float, nullable=True)
  requires_receipt      = Column(Boolean, default=True)
  
  #submission deadline rules
  submission_deadline_days = Column(Integer, nullable=True)  # 7, 30, days
  max_extension_days       = Column(Integer, nullable=True)
  late_claim_rule          = Column(Text, nullable=True)
   
   
  #project code requirement
  requires_project_code   = Column(Boolean, default=False)
  project_code_min_amount = Column(Float, nullable=True)  # Rs 1000 threshold
  
  
  # relationships
  approval_rules    = relationship("PolicyApprovalRule",    back_populates="policy", cascade="all, delete-orphan")
  beneficiary_rules = relationship("PolicyBeneficiaryRule", back_populates="policy", cascade="all, delete-orphan")

# Policy Approval Rule
# who approves based on claim amount

class PolicyApprovalRule(Base):
  __tablename__ = "policy_approval_rules"
  
  id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  policy_id          = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
  min_amount         = Column(Float, default=0)
  max_amount         = Column(Float, nullable=True)        # None = no upper limit
  approver_role      = Column(String(50), nullable=False)  # manager, finance_head, cfo
  requires_secondary = Column(Boolean, default=False)
  secondary_role     = Column(String(50), nullable=True)
  tat_days           = Column(Integer, default=2)          # turnaround time in days

  policy = relationship("Policy", back_populates="approval_rules")


#Policy Beneficiary rule
#medical limits per beneficiary type

class PolicyBeneficiaryRule(Base):
  __tablename__ = "policy_beneficiary_rules"
  
  id  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
  policy_id  = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
  beneficiary_type  = Column(Enum(BeneficiaryType), nullable=False)
  annual_limit   = Column(Float, nullable=True)
  per_claim_limit   = Column(Float, nullable=True)
  hospitalization_limit = Column(Float, nullable=True)
  submission_days       = Column(Integer, nullable=True)

  #relationship
  policy = relationship("Policy", back_populates="beneficiary_rules")
  


  




class ApprovalStep(Base):
  __tablename__ = "approval_steps"
  
  
  id = Column(UUID(as_uuid=True), primary_key =True, default=uuid.uuid4)
  claim_id = Column(UUID(as_uuid=True),ForeignKey("expense_claims.id"), nullable=False)  
  approver_id = Column(UUID(as_uuid=True),ForeignKey("users.id"), nullable=False)
  
  
  step_order = Column(Integer,nullable=False) # 1st, 2nd, 3rd approver
  action  = Column(Enum(ApprovalAction),default=ApprovalAction.pending)
  comments = Column(String(500), nullable=True)
  acted_at = Column(DateTime, nullable=True)
  
  #SLA tracking
  due_at = Column(DateTime,nullable=True) #when step must be completed
  is_overdue = Column(Boolean,default=False) # set by background job
  
  #relationship
  claim = relationship("ExpenseClaim", back_populates="approval_steps")
  approver =  relationship("User")
 
 
#Fruad Alert
# AI fraud detection results
class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id    = Column(UUID(as_uuid=True), ForeignKey("expense_claims.id"), nullable=False)
    fraud_score = Column(Float, nullable=False)               # 0.0 to 1.0
    severity    = Column(Enum(FraudSeverity), nullable=False)
    reasons     = Column(JSONB, nullable=True)                # list of flag reasons
    is_resolved = Column(Boolean, default=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution  = Column(Text, nullable=True)                 # compliance decision
    created_at  = Column(DateTime, default=datetime.utcnow)

    claim    = relationship("ExpenseClaim", back_populates="fraud_alerts")
    resolver = relationship("User")

 
 
 
 
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
  
  
  

  
  