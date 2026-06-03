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

from pydantic import BaseModel, EmailStr, Field,validator
from typing import Optional, List,Any
from datetime import datetime,date
from uuid import UUID
from enum import Enum


# Enums
class UserRole(str, Enum):
   employee ="employee"
   manager = "manager"
   finance = "finance"
   admin = "admin"
  
class EmployeeLevel(str, Enum):
  L1_L3= "L1-L3"  #junior Employee
  L4_L6 = "L4-L6"  # Senior
  L7_L9 = "L7-L9"  #Manager
  L10_UP ="L10+"   # Diectors and above
  
  
  
  
   
class ClaimStatus(str,Enum):
  draft= "draft"
  submitted = "submitted"
  under_review ="under_review"
  approved = "approved"
  rejected = "rejected"
  paid = "paid"
  on_hold = "on_hold"
  escalated = "escalated"
  appealed = "appealed"
  fraud_alert = "fraud_alert"
  

class ExpenseCategory(str, Enum):
  travel = "travel"
  food = "food"
  transport = "transport"
  accommodation = "accommodation"
  fuel="fuel"
  office_supplies="office_supplies"
  communication_bills ="communication_bills" # wifi
  medical = "medical"
  training = "training"
  other = "other"
  
class ApprovalAction(str, Enum):
  pending = "pending"
  approved = "approved"
  rejected = "rejected"
  on_hold = "on_hold"
  
class BeneficiaryType(str,Enum):
  self_ = "self"
  spouse ="spouse"
  child = "child"
  parent = "parent"
  
  
class CityTier(str, Enum):
  metro = "metro"
  tier2 = "tier2"
  tier3 = "tier3"
  international = "international"
  
class FraudSeverity(str,Enum):
  low = "low"
  medium= "medium"
  high ="high"
  critical = "critical"
  
#User Schema
class UserRegister(BaseModel):
  email: EmailStr
  password : str = Field(min_length=6)
  full_name:str
  role:UserRole = UserRole.employee
  employee_level :EmployeeLevel = EmployeeLevel.L1_L3
  


class UserLogin(BaseModel):
  email:EmailStr
  password:str
  
class UserResponse(BaseModel):
  id :UUID
  email:str
  full_name:str
  role:UserRole
  employee_level:Optional[EmployeeLevel] = None
  department_id : Optional[UUID] = None
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
    
class UserUpdate(BaseModel):
  """Update basic profile details only"""
  employee_level:Optional[EmployeeLevel]=None
  full_name:Optional[str] = None
  department_id: Optional[UUID] = None
class TokenResponse(BaseModel):
  access_token:str
  token_type:str= "bearer"
  

  
#claims schema
class LineItemCreate(BaseModel):
  category: ExpenseCategory
  description: str
  amount : float =Field(gt=0)
  expense_date :date
  beneficiary_type: Optional[BeneficiaryType] = None #for medical claims
  city_tier: Optional[CityTier] = None # for travel/accommodation
  
  
class ClaimCreate(BaseModel):
    title:str
    description:Optional[str] = None
    project_code: Optional[str]= None
    line_items: List[LineItemCreate]
    
class ClaimStatusUpdate(BaseModel):
  """Manager usses this to apptove/reject/hold a claim"""
  status: ClaimStatus
  comments: Optional[str] = None
  on_hold_reason: Optional[str]=None

class ClaimAppeal(BaseModel):
  """Employee uses this to appeal a rejection"""
  appeal_reason: str
  
  
class LineItemResponse(BaseModel):
    id: UUID
    category: ExpenseCategory
    description: str
    amount: float
    expense_date: date
    is_flagged:bool
    flag_reason: Optional[str] = None
    policy_id:Optional[UUID] =None
    beneficiary_type: Optional[BeneficiaryType] = None
    city_tier: Optional[CityTier] = None
    claimed_amount:Optional[float] =None
    extracted_amount:Optional[float] = None
    amount_mismatch:bool = False
    
  
    class Config:
      from_attributes=True
  
class ClaimResponse(BaseModel):
  id: UUID
  title:str
  total_amount:float
  description:Optional[str]
  currency :str
  status: ClaimStatus
  risk_score: float =0.0
  project_code :Optional[str] =None
  submitted_at:Optional[datetime]
  approved_at:Optional[datetime]
  rejected_at: Optional[datetime]
  paid_at :Optional[datetime]
  created_at : datetime
  
  # AI results
  agent_decision: Optional[str] = None
  agent_reasoning: Optional[str] =None
  # violations
  policy_violations:Optional[List[Any]] = []
  # Appeal
  appeal_reason:Optional[str] = None
  appeal_deadline:Optional[datetime]= None
  
  #on hold
  on_hold_reason: Optional[str] = None
  on_hold_deadline:Optional[datetime] = None
  #Nested
  line_items: List[LineItemResponse] = []
  user: Optional[UserBrief]=None
  
  @validator('policy_violations', pre=True,always=True)
  def fix_none_violations(cls,v):
    return v if v is not None else []
  
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
  
  #OCR results
  extracted_amount:Optional[float] =None
  extracted_date:Optional[date]=None
  extracted_merchant:Optional[str]=None
  ocr_confidence:Optional[float]=None
  
  #Tamper detection
  is_tampered: Optional[bool] =None
  tamper_confidence: Optional[float] = None
  
  uploaded_at: datetime
  uploaded_by:UUID
  
  class Config:
    from_attributes=True
    

# Department Schemas
class DepartmentCreate(BaseModel):
  name:str
  bau_code : Optional[str] = None    #BAU-ENG-2026 -Engineering department    BAU-HR-2026 - HR department
  

class DepartmentUpdate(BaseModel):
  name :Optional[str] = None
  bau_code : Optional[str] = None
  manager_id : Optional[UUID] = None
  

class DepartmentResponse(BaseModel):
  id:UUID
  name:str
  bau_code : Optional[str] = None
  manager_id:Optional[UUID] = None
  
  
  class Config:
    from_attributes=True
    
    
    
#policy  approval rule schema
class PolicyApprovalRuleCreate(BaseModel):
  min_amount: Optional[float] = 0
  max_amount:Optional[float] = None
  approver_role:str # manager ,financehead,
  requires_secondary: bool = False
  secondary_role:Optional[str] = None
  tat_days: int = 2
  
class PolicyApprovalRuleResponse(BaseModel):
  id: UUID
  policy_id: UUID
  min_amount: float
  max_amount:Optional[float]
  approver_role:str
  requires_secondary:bool
  secondary_role:Optional[str]
  tat_days:int #trun around time in days
  
  class Config:
    from_attributes =True
    
    
    
# Policy Beneficiary RUle schemas
class PolicyBeneficiaryRuleCreate(BaseModel):
  beneficiary_type: BeneficiaryType
  annual_limit:Optional[float]=None
  per_claim_limit:Optional[float]=None
  hospitalization_limit: Optional[float]=None
  submission_days: Optional[int]=None
  
class PolicyBeneficiaryRuleResponse(BaseModel):
    id:                    UUID
    policy_id:             UUID
    beneficiary_type:      BeneficiaryType
    annual_limit:          Optional[float]
    per_claim_limit:       Optional[float]
    hospitalization_limit: Optional[float]
    submission_days:       Optional[int]

    class Config:
        from_attributes = True
    
#policy schema
class PolicyCreate(BaseModel):
  name:str
  description :Optional[str] =None
  category: ExpenseCategory
  max_amount_per_claim:  Optional[float] = None
  max_amount_per_year:   Optional[float] = None
  max_amount_per_event:  Optional[float] = None
  hospitalization_limit: Optional[float] = None

  requires_receipt: bool =True

      # Policy identity
  policy_code:    Optional[str]      = None   # CF-POL-EXP-2026-S02
  version:        str                = "1.0"
  effective_date: Optional[datetime] = None
  review_date:    Optional[datetime] = None
   # Submission rules
  submission_deadline_days: Optional[int]  = None
  max_extension_days:       Optional[int]  = None
  late_claim_rule:          Optional[str]  = None

    # Project code
  requires_project_code:   bool           = False
  project_code_min_amount: Optional[float] = None

    # Nested rules (optional on create)
  approval_rules:    List[PolicyApprovalRuleCreate]    = []
  beneficiary_rules: List[PolicyBeneficiaryRuleCreate] = []
class PolicyUpdate(BaseModel):
  name: Optional[str] = None
  description: Optional[str] = None 
  category: Optional[ExpenseCategory] =None
  requires_receipt: Optional[bool] = None
  is_active:Optional[bool]= None
  version:          Optional[str]           = None
  effective_date:   Optional[datetime]      = None
  review_date:      Optional[datetime]      = None

  max_amount_per_claim:  Optional[float] = None
  max_amount_per_year:   Optional[float] = None
  max_amount_per_event:  Optional[float] = None
  hospitalization_limit: Optional[float] = None

  submission_deadline_days: Optional[int]  = None
  max_extension_days:       Optional[int]  = None
  late_claim_rule:          Optional[str]  = None

  requires_project_code:   Optional[bool]  = None
  project_code_min_amount: Optional[float] = None
  
class PolicyResponse(BaseModel):
  id:UUID
  name:str
  description:Optional[str]
  category:ExpenseCategory
  is_active:bool
  created_by:UUID
  created_at:datetime
  updated_at:datetime
  
  #policy identity
  policy_code: Optional[str]
  version: str
  effective_date: Optional[datetime]
  review_date:Optional[datetime]
  
  #amount limits
  max_amount_per_claim:  Optional[float]
  max_amount_per_year:   Optional[float]
  max_amount_per_event:  Optional[float]
  hospitalization_limit: Optional[float]
  requires_receipt:      bool

    # Submission rules
  submission_deadline_days: Optional[int]
  max_extension_days:       Optional[int]
  late_claim_rule:          Optional[str]

    # Project code
  requires_project_code:   bool
  project_code_min_amount: Optional[float]

    # File
  policy_text: Optional[str] = None
  file_path:   Optional[str] = None

    # Nested
  approval_rules:    List[PolicyApprovalRuleResponse]    = []
  beneficiary_rules: List[PolicyBeneficiaryRuleResponse] = []

  
  class Config:
    from_attributes =True
    
    
# Approval step schemas
class ApprovalStepResponse(BaseModel):
    id : UUID
    claim_id:   UUID
    approver_id: UUID
    step_order: int
    action:     ApprovalAction
    comments:   Optional[str]      = None
    acted_at:   Optional[datetime] = None
    due_at:     Optional[datetime] = None
    is_overdue: bool               = False

    class Config:
        from_attributes = True
   
  
# Fraud Alert schemas
class FraudAlertResponse(BaseModel):
  id: UUID
  claim_id: UUID
  fraud_score: float
  severity: FraudSeverity
  reasons: Optional[List[Any]] = []
  is_resolved:bool
  resolved_at: Optional[datetime] =None
  resolution: Optional[str] =None
  created_at: datetime
  
  class Config:
    from_attributes= True
    
class FraudAlertResolve(BaseModel):
  """Compliance team uses this to resolve a fraud alert"""
  
  resolution:str # what decided after review
  
  

# Analytics schema

class CategoryBreakdown(BaseModel):
  category: str
  count:int
  amount:float
  
class MonthlyTrend(BaseModel):
  month:str
  amount:float
  count:int
  

class EmployeeAnalytics(BaseModel):
  """Response for GET /analytics/employee/me/summary"""
  total_claims: int
  total_amount: float
  approved_count: int
  approved_amount:float
  pending_count:int  # submitted + under review
  pending_amount:float
  rejected_count:int
  rejected_amount:float
  by_category:List[CategoryBreakdown] =[]
  monthly_trend: List[MonthlyTrend] = []

class ManagerAnalytics(BaseModel):
    """Response for GET /analytics/manager/department/{dept_id}/summary"""
    department_name:  str
    total_claims:     int
    total_amount:     float
    approval_rate:    float    # percentage
    avg_processing_days: float
    fraud_flagged:    int
    by_category:      List[CategoryBreakdown] = []
    top_claimants:    List[UserBrief]         = []

class AdminAnalytics(BaseModel):
    """Response for GET /analytics/admin/company/summary"""
    total_claims:     int
    total_amount:     float
    total_approved:   float
    total_pending:    float
    total_rejected:   float
    fraud_alerts:     int
    by_department:    List[dict]              = []
    by_category:      List[CategoryBreakdown] = []
    monthly_trend:    List[MonthlyTrend]      = []

 
