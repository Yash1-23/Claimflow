""" 
  Rule Engine -  deterministic bussiness rules for expenses claims.
  
  - Run before any AI agent ( cheap, fast, predictable)
  - Each rule is a small pure function.
  - Engine collects violations and returns a decision
  
  Why deterministic rules first?
- 5 ms vs 1500 ms (LLM)
- ₹0 cost vs ₹0.30 per call
- 100% predictable vs probabilistic
- LLM reserved for fuzzy reasoning only (OCR, fraud detection)

"""

from datetime import date, timedelta
from typing import List,Any
from dataclasses import dataclass,field
from sqlalchemy.orm import Session
from app.models.models import ExpenseClaim,ClaimLineItem,Receipt


#policy configuration (later :move to DB -driven policies)
CATEGORY_LIMITS ={
  "food":1500,
  "travel":50000,
  "transport":5000,
  "accommodation":10000,
  "other":5000,
}

RECEIPT_REQUIRED_THRESHOLD =2000 # above this , receipt mandatory
MAX_CLAIM_AGE_DAYS = 90         # claims older than this are stale


# Decision 
@dataclass
class Flag:
  severity:str # Block | High | Warning
  rule:str     # machine readable rule name
  message:str  # human-readable message show to manager
  
  
@dataclass
class RuleDecision:
  flags: List[Flag] = field(default_factory=list)
  
  def block(self, rule:str, message:str):
    self.flags.append(Flag(severity="BLOCK",rule=rule,message=message))
    
  def high(self,rule:str, message:str):
    self.flags.append(Flag(severity="HIGH",rule=rule,message=message))
    
  def warning(self,rule:str,message:str):
    self.flags.append(Flag(severity="WARNING",rule=rule ,message=message))
    
  
  @property
  def final_decision(self) -> str:
    """Block -level flags = auto-reject. Everthing else -> manager"""
    if any(f.severity =="BLOCK" for f in self.flags):
       return "rejected"
    return "submitted"
  
  
# Individual rules
def rule_check_category_limits(claim:ExpenseClaim,decision:RuleDecision):
   """ Each line item must respect its category limit"""
   
   for item in claim.line_items:
     limit = CATEGORY_LIMITS.get(item.category.value)
     if limit and item.amount > limit:
       decision.high(
         rule="category_limit",
         message =f"'{item.category.value}' expense rs{item.amount} exceeds limt rs{limit}"
         
       )
       
def rule_check_future_dates(claim:ExpenseClaim,decision:RuleDecision):
  """Cannot claim expenses with future dates"""
  
  today = date.today()
  for item in claim.line_items:
    if item.expense_date> today:
      decision.block(
        rule="future_date",
        message=f"Expense date {item.expense_date} is in the future"
      )
       
       
def rule_check_stale_claims(claim:ExpenseClaim,decision:RuleDecision):
  """CLaims older than MAX_CLAIM_AGE_DAYS are not allowed"""
  cutoff = date.today() - timedelta(days=MAX_CLAIM_AGE_DAYS)
  for item in claim.line_items:
    if item.expense_date <cutoff:
      decision.block(
        rule="stale_claim",
        message=f"Expense date {item.expense_date} is older than {MAX_CLAIM_AGE_DAYS} days"
        
      )
      
def rule_check_receipts_for_high_amounts(
  claim: ExpenseClaim,
  decision:RuleDecision,
  db:Session
):
  """ Line items above receipts threshold MUST have a receipt attached"""
  for item in claim.line_items:
    if item.amount > RECEIPT_REQUIRED_THRESHOLD:
      receipt_count = db.query(Receipt).filter(
        Receipt.line_item_id == item.id
      ).count()
      
      if receipt_count ==0:
        decision.high(
          rule ="missing_receipt",
          message=(
            f"Receipt required for rs{item.amount} expense"
            f"('{item.description})"
          )
        )
       

def rule_check_duplicate(
  claim:ExpenseClaim,
  decision:RuleDecision,
  db:Session
):
  """ Flag if same user submitted a matching claim recently"""
  for item in claim.line_items:
    duplicate = db.query(ClaimLineItem).join(ExpenseClaim).filter(
      ExpenseClaim.user_id == claim.user_id,
      ExpenseClaim.id != claim.id,
      ClaimLineItem.amount == item.amount,
      ClaimLineItem.expense_date == item.expense_date,
      ClaimLineItem.category == item.category,
      
    ).first()
    
    if duplicate:
      decision.warning(
        rule = "possible_duplicate",
        message=f"Possible duplicate: rs{item.amount} on {item.expense_date} ({item.category.value})"
        
      )
      
# 
def run_rules(claim:ExpenseClaim,db:Session) -> RuleDecision:
  """
   Run all rules against a claim. Returns a RulDecision with
   all flags attached.Caller decides what to do with the result
  """
  
  decision =  RuleDecision()
  
  rule_check_future_dates(claim,decision) #BLOCK -run first / It checks  if claims is found future date it blocks
  rule_check_stale_claims(claim, decision) #BLOCK Claim is older than 90 days it blocks
  rule_check_category_limits(claim,decision) #High
  rule_check_receipts_for_high_amounts(claim,decision,db) # high
  rule_check_duplicate(claim, decision,db) #Warning
  
  return decision
  