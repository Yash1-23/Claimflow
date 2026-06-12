"""
  Fraud Detection Service 
  rule based fraud scoring 
  
  Why rule first instead of LLM:
  - 80% of fraud patterns are deterministic (duplicates ,round numbers)
  - Zero API cost 
  - Explainable for audits
  - same patterns used by some fraud systems 
  
  
  Severity mapping (matches fraud severity enum in models.py)
  0.0 - 0.3  -> low
  0.3 - 0.6  -> medium
  0.6 - 0.8  -> high
  0.8 - 1.0  -> critical
  
  Fraud Alert row is created only for high/critical severity.
  claim.risk_score is updated for every check.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.models import(
  ExpenseClaim,
  ClaimLineItem,
  Receipt,
  FraudAlert,
  FraudSeverity,
)

# rule  weights 
RULE_WEIGHTS = {
  "duplicate_claim":0.40,
  "round_number":0.15,
  "just_under_limit":0.25,
  "weekend_submission":0.10,
  "high_frequency":0.20,
  "repeated_vendor":0.15,
  "amount_spike":0.20,
  "amount_mismatch":0.30,
  
}

# category limits (mirrior policy pdf)
CATEGORY_LIMITS = {
  "travel": 12000,
  "food": 2000,
  "transport":5000,
  "accommodation":5000,
  "fuel": 6000,
  "medical":50000,
  "communication_bills":5000,
  "training":20000,
}


# Individual Function
def check_duplicates_claim(db:Session, claim:ExpenseClaim) ->bool:
  """Same user+ same total_amount within 30 days = possible duplicate."""
  
  thirty_days_ago = datetime.utcnow() - timedelta(days=30)
  
  
  duplicate = db.query(ExpenseClaim).filter(
    and_(
      ExpenseClaim.user_id == claim.user_id,
      ExpenseClaim.total_amount == claim.total_amount,
      ExpenseClaim.id!=claim.id,
      ExpenseClaim.created_at >= thirty_days_ago,
    )
  ).first()
  
  return duplicate is not None

def check_round_number(claim:ExpenseClaim) -> bool:
  """ Amounts like 1000, 5000, 10000 are statistically unsual for real receipts."""
  amount = float(claim.total_amount)
  return amount >=500 and amount % 500 ==0


def check_just_under_limit(db:Session,claim:ExpenseClaim)-> bool:
    """ANy line item within 2% below its category limit= gaming the threshold"""
    line_items = db.query(ClaimLineItem).filter(
      ClaimLineItem.claim_id==claim.id
    ).all()
    
    for item in line_items:
      category = item.category.value if item.category else None
      limit = CATEGORY_LIMITS.get(category)
      
      
      if limit:
        amount = float(item.amount)
        threshold = limit * 0.98
        if threshold <= amount < limit:
          return True
        
    return False
  
  
  
def check_weekend_submission(claim:ExpenseClaim)->bool:
  """Claims created on saturday(5)/sunday(6) - medium signal"""
  created = claim.created_at or datetime.utcnow()
  return created.weekday() >=5


def check_high_frequency(db:Session,claim:ExpenseClaim)->bool:
  """More than 3 claims by smae user today = possible split-claims"""
  
  today_start = datetime.utcnow().replace(
    hour=0, minute=0, second=0, microsecond=0
  )
  
  count = db.query(func.count(ExpenseClaim.id)).filter(
    and_(
      ExpenseClaim.user_id == claim.user_id,
      ExpenseClaim.created_at >= today_start,
    )
  ).scalar()
  
  return count > 3


def check_repeated_vendor(db:Session,claim:ExpenseClaim) -> bool:
  """ same merchat >5 times in 30 days by smae user (via receipt.extracrted_merchant)"""
  thirty_days_ago = datetime.utcnow() - timedelta(days=30)
  
  #Get merchants on this claim receipts
  merchants = (
    db.query(Receipt.extracted_merchant)
    .join(ClaimLineItem,Receipt.line_item_id == ClaimLineItem.id)
    .filter(
      ClaimLineItem.claim_id == claim.id,
      Receipt.extracted_merchant.isnot(None),
    )
    .all()
    
  )
  
  merchant_names = [m[0] for m in merchants if m[0]]
  if not merchant_names:
    return False
  
  #count each merchant usage across this users claims in last 30 days
  for merchant in merchant_names:
    count = (
      db.query(func.count(Receipt.id))
      .join(ClaimLineItem,Receipt.line_item_id==ClaimLineItem.id)
      .join(ExpenseClaim, ClaimLineItem.claim_id == ExpenseClaim.id)
      .filter(
        ExpenseClaim.user_id == claim.user_id,
        Receipt.extracted_merchant == merchant,
        Receipt.uploaded_at >= thirty_days_ago,
      )
      .scalar()
    )
    
    if count > 5:
      return True
  return False



def check_amount_spike(db:Session,claim:ExpenseClaim) ->bool:
  """Claim 3x larger that user's historical average"""
  avg_amount =db.query(func.avg(ExpenseClaim.total_amount)).filter(
    and_(
      ExpenseClaim.user_id == claim.user_id,
      ExpenseClaim.id!= claim.id,
    )
  ).scalar()
  
  
  if not avg_amount or float(avg_amount) == 0:
    return False # first claim no history
  
  return float(claim.total_amount) > float(avg_amount) *3


def check_amount_mismatch(db:Session,claim:ExpenseClaim) -> bool:
  """OCR extracted amount differs from claim amount (set by OCR)"""
  mismatched = db.query(ClaimLineItem).filter(
    and_(
      ClaimLineItem.claim_id==claim.id,
      ClaimLineItem.amount_mismatch==True,
    )
  ).first()
  
  return mismatched is not None

# Severity 
def get_severity(score:float) -> FraudSeverity:
  """ Map fraud score to Fraud Severity enum bands"""
  if score >= 0.8:
    return FraudSeverity.critical
  elif score >=0.6:
    return FraudSeverity.high
  elif score >= 0.3:
    return FraudSeverity.medium
  return FraudSeverity.low

def score_claim_fraud_risk(db:Session, claim:ExpenseClaim)->dict:
  """
  Run all fraud rules, aggregate weighted score, update claim.rist_score.
  
  return:
      {
        "claim_id": str,
        "fraud_score":0.0-1.0,
        "severity:"low" | "medium" | "high" | "critical",
        "triggered_rules":[..],
        "details": {rules:explanation},
        "checked_at": timestamp
      }
  """
  
  triggered = []
  details ={}
  
  
  if check_duplicates_claim(db,claim):
    triggered.append("duplicate_claim")
    details ["duplicate_claim"] = "Same amount submitted within 30 days"
    
  if check_round_number(claim):
    triggered.append("round_number")
    details ["round_number"] = f"Amount Rs {claim.total_amount} is suspiciously round"
  
  if check_just_under_limit(db,claim):
    triggered.append("just_under_limit")
    details ["just_under_limit"] = "Line item within 2% of category limit"
    
  if check_weekend_submission(claim):
    triggered.append("weekend_submission")
    details ["weekend_submission"] = "Claim created on weekend"
    
  
  if check_high_frequency(db,claim):
    triggered.append("high_frequency")
    details["high_frequency"] = "More than 3 claims submitted today"
    
  if check_repeated_vendor(db,claim):
    triggered.append("repeated_vendor")
    details["repeated_vendor"] = "Same merchant user >5 times this month"
    
  if check_amount_spike(db,claim):
    triggered.append("amount_spike")
    details["amount_spike"]="Amount is 3x user's historical  average"
    
  if check_amount_mismatch(db,claim):
    triggered.append("amount_mismatch")
    details["amount_mismatch"]="OCR amount differs from claimed amount"
    
    
  # Aggregate weighted score 
  fraud_score = min(
    sum(RULE_WEIGHTS[rule] for rule in triggered),
    1.0
  )
  
  severity = get_severity(fraud_score)
  
  # update claims risk_score cloumn
  claim.risk_score = fraud_score
  db.commit()
  
  return {
        "claim_id": str(claim.id),
        "fraud_score": round(fraud_score, 2),
        "severity": severity.value,
        "triggered_rules": triggered,
        "details": details,
        "checked_at": datetime.utcnow().isoformat(),
    }

# Fraud Alert creation
def create_fraud_alert_if_needed(db: Session, claim: ExpenseClaim, fraud_result: dict):
    """
    If severity is high or critical, persist a FraudAlert row for audit trail.
    Returns the alert or None.
    """
    if fraud_result["severity"] not in ("high", "critical"):
        return None

    alert = FraudAlert(
        claim_id=claim.id,
        fraud_score=fraud_result["fraud_score"],
        severity=FraudSeverity(fraud_result["severity"]),
        reasons=fraud_result["triggered_rules"],  # JSONB stores the list directly
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert