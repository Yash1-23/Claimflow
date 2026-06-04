from fastapi import APIRouter,Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user,get_current_manager,get_current_admin
from app.models.models import(
  ExpenseClaim,ClaimLineItem,ClaimStatus,
  User,Department,FraudAlert
)
from app.schemas.schemas import (
  EmployeeAnalytics,ManagerAnalytics,AdminAnalytics,
  CategoryBreakdown,MonthlyTrend,UserBrief
)
from uuid import UUID

router = APIRouter()


# Employee Analytics
""" What it does:
    Employee logs in and see
    -> how many claims they submitted
    -> how much is approved,pending ,rejected
    -> which category they spend most on
    -> monthly spending trend
"""

@router.get("/employee/me/summary",response_model=EmployeeAnalytics)
def get_employee_summary(
  db:Session = Depends(get_db),
  current_user:User = Depends(get_current_user),
):
  
  
  # get all claims for logged in employee
  # current_user.id comes from JWT tokens automatically
  all_claims = db.query(ExpenseClaim).filter(
    ExpenseClaim.user_id == current_user.id
  ).all()
  
  # separate claims by status using plain python list filter
  # approved = claims where status is approved
  approved = [c for c in all_claims if c.status== ClaimStatus.approved]
  
  #pending = submitted + under_review combined
  # both means waiting for manager action
  pending = [c for c in all_claims if c.status in [
    ClaimStatus.submitted,
    ClaimStatus.under_review
  ]]
  
  rejected = [c for c in all_claims if c.status ==ClaimStatus.rejected]
  
  # calculate total amount using python sum()
  # sum(c.total_amount for c in list) loops through list and adds amounts
  total_amount = sum(c.total_amount for c in all_claims)
  approved_amount = sum(c.total_amount for c in approved)
  pending_amount =  sum(c.total_amount for c in pending)
  rejected_amount = sum(c.total_amount for c in rejected)
  
  
  # Category Breakdown
  # shows how much employee spend on travel vs food vs medical 
  #step 1: get all claims IDs
  claim_ids = [c.id for c in all_claims]
  
  #step2: get all line items for those claims
  line_items = db.query(ClaimLineItem).filter(
    ClaimLineItem.claim_id.in_(claim_ids)
  ).all()
  
  # step 3: group by category using pythonn dict
  # eg: {"travel":{"count":3,"amount":9000},
  #        "food": {"count":2,"amount":1500}}
  
  category_data = {}
  for item in line_items:
    cat = item.category.value   # eg travel
    if cat not in category_data:
      category_data[cat] ={"count":0,"amount":0}
      
    category_data[cat]["count"] +=1
    category_data[cat]["amount"] +=item.amount
    
    
  by_category= [
    CategoryBreakdown(
      category=cat,
      count=data["count"],
      amount=data["amount"]
    )
    for cat, data in category_data.items()
  ]
  
  
  # Monthly trends
  # showing spending month by month
  
  monthly_data = {}
  for claim in all_claims:
    month_key = claim.created_at.strftime("%b %Y")
    if month_key not in monthly_data:
      monthly_data[month_key] = {"count":0,"amount":0}
      
    monthly_data[month_key]["count"] +=1
    monthly_data[month_key]["amount"] += claim.total_amount
    
    
  monthly_trend = [
    MonthlyTrend(
      month=month,
      count=data["count"],
      amount=data["amount"]
    )
    for month, data in monthly_data.items()
  ]
  
  
  return EmployeeAnalytics(
    total_claims = len(all_claims),
    total_amount = total_amount,
    approved_count =len(approved),
    approved_amount= approved_amount,
    pending_count=len(pending),
    pending_amount = pending_amount,
    rejected_count=len(rejected),
    rejected_amount=rejected_amount,
    by_category = by_category,
    monthly_trend=monthly_trend,
    
  )
  
  
  
# Manager Analytics
# What is does:
# Manager logs in and see their department
# → total claims submitted by team
# → approval rate (how many got approved)
# → average days to process a claim
# → how many fraud alerts in department
# → top 5 employees who claim the most


@router.get("/manager/department/{dept_id}/summary",response_model=ManagerAnalytics)
def get_manager_summary(
  dept_id:UUID,
  db:Session = Depends(get_db),
  current_user:User = Depends(get_current_manager),
):
  
  #get department name
  dept = db.query(Department).filter(Department.id==dept_id).first()
  dept_name= dept.name if dept else "Unknwon"
  
  # get all user  in this department
  dept_users = db.query(User).filter(
    User.department_id == dept_id
  ).all()
  
  #get their IDs as a list
  user_ids = [u.id for u  in dept_users]
  
  # get all claims form these users
  all_claims = db.query(ExpenseClaim).filter(
    ExpenseClaim.user_id.in_(user_ids)
  ).all()
  
  #basic counts
  total_claims = len(all_claims)
  total_amount = sum(c.total_amount for c in all_claims)
  approved = [c for c in all_claims if c.status == ClaimStatus.approved]
  approved_count = len(approved)
  
  
  # approved_rate = approved / total *100
  #eg. 8 approved out of 10 =80%
  approval_rate =(
    round((approved_count / total_claims) * 100, 2)
    if total_claims > 0 else 0.0
  )
  
  
  # average processing time in days
  # processing time = approved_at - submitted_at
  
  processing_days = []
  for c in all_claims:
    if c.approved_at and c.submitted_at:
      diff = (c.approved_at - c.submitted_at).days
      processing_days.append(diff)
      
  
  avg_processing_days =(
    round(sum(processing_days) / len(processing_days),2)
    if processing_days else 0.0
  )
  
  
  #count unresolved fraud alerts for this department
  claim_ids = [c.id for c in all_claims]
  fraud_flagged = db.query(FraudAlert).filter(
    FraudAlert.claim_id.in_(claim_ids),
    FraudAlert.is_resolved == False
    
  ).count()
  
  
  #category breakdown - same logic as employee
  line_items = db.query(ClaimLineItem).filter(
    ClaimLineItem.claim_id.in_(claim_ids)
  ).all()
  
  category_data =[]
  for item in line_items:
    cat = item.category.value
    if cat not in category_data:
      category_data[cat] = {"count":0,"amount":0}
    category_data[cat]["count"] +=1
    category_data[cat]["amount"] += item.amount
    
  
  by_category = [
    CategoryBreakdown(
      category=cat,
      count=data["count"],
      amount=data["amount"]
    )
    for cat, data in category_data.items()
  ]
  
   # top 5 claim by total amount
   # step1:  build dict of user_id -> total amount
  user_totals ={}
  for claim in all_claims:
    uid = claim.user_id
    if uid not in user_totals:
      user_totals[uid] = 0
    user_totals[uid] += claim.total_amount
    
    
    # step2 :sort by amount take top5
  top_user_ids = sorted(
      user_totals,
      key =user_totals.get,
      reverse=True
    )[:5]
    
    #step3 : fetch those users from db
  top_users = db.query(User).filter(
      User.id.in_(top_user_ids)
      
    ).all()
    
  top_claimants =[
      UserBrief(
        id=U.id,
        full_name=U.full_name,
        email=U.email
      )
      for U in top_users
    ]
    
  return ManagerAnalytics(
      department_name= dept_name,
      total_claims = total_claims,
      total_amount = total_amount,
      approval_rate = approval_rate,
      avg_processing_days = avg_processing_days,
      fraud_flagged=fraud_flagged,
      by_category=by_category,
      top_claimants=top_claimants,
    )
    

@router.get("/manager/pending-claims")
def get_manager_pending_claims(
  db:Session = Depends(get_db),
  current_user:User= Depends(get_current_manager),
):
  
  """
     Manager sees all pending claims in their department.
     pending = submitted + under_review
     Ordered by oldest first so manager handles urget ones first
  """
  
  dept_users = db.query(User).filter(
    User.department_id== current_user.department_id
  ).all()
  user_ids = [U.id for U in dept_users]
  
  pending_claims = db.query(ExpenseClaim).filter(
    ExpenseClaim.user_id.in_(user_ids),
    ExpenseClaim.status.in_([
      ClaimStatus.submitted,
      ClaimStatus.under_review
    ])
  ).order_by(ExpenseClaim.submitted_at.asc()).all()
  
  
  return {
    "pending_count":len(pending_claims),
    "claims":[
      {
        "id": str(c.id),
        "title": c.title,
        "total_amount":c.total_amount,
        "status":c.status.value,
        "submitted_at":c.submitted_at,
        "user_id":str(c.user_id),
      }
      for c in pending_claims
    ]
  }
   
   
 # Admin Analystics
## What it does:
# Admin sees entire company:
# → total claims across all departments
# → total approved, pending, rejected amounts
# → which department spends most
# → which category is most claimed
# → monthly trend company wide


@router.get("/admin/company/summary", response_model=AdminAnalytics)
def get_admin_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    # get ALL claims in company
    all_claims = db.query(ExpenseClaim).all()

    # basic totals
    total_claims   = len(all_claims)
    total_amount   = sum(c.total_amount for c in all_claims)
    total_approved = sum(c.total_amount for c in all_claims if c.status == ClaimStatus.approved)
    total_pending  = sum(c.total_amount for c in all_claims if c.status in [
        ClaimStatus.submitted, ClaimStatus.under_review
    ])
    total_rejected = sum(c.total_amount for c in all_claims if c.status == ClaimStatus.rejected)

    # unresolved fraud alerts company wide
    fraud_alerts = db.query(FraudAlert).filter(
        FraudAlert.is_resolved == False
    ).count()

    # BY DEPARTMENT 
    # shows which department spends most
    # Step 1: build maps for quick lookup
    all_users = db.query(User).all()
    all_depts = db.query(Department).all()

    # dept_id → dept name
    dept_name_map = {d.id: d.name for d in all_depts}

    # user_id → dept name
    user_dept_map = {}
    for u in all_users:
        if u.department_id:
            user_dept_map[u.id] = dept_name_map.get(
                u.department_id, "Unknown"
            )

    # group claims by department
    dept_data = {}
    for claim in all_claims:
        dept_name = user_dept_map.get(claim.user_id, "Unknown")
        if dept_name not in dept_data:
            dept_data[dept_name] = {"count": 0, "amount": 0}
        dept_data[dept_name]["count"]  += 1
        dept_data[dept_name]["amount"] += claim.total_amount

    by_department = [
        {
            "department": dept,
            "count":      data["count"],
            "amount":     data["amount"]
        }
        for dept, data in dept_data.items()
    ]

    # by category — all line items company wide
    all_line_items = db.query(ClaimLineItem).all()

    category_data = {}
    for item in all_line_items:
        cat = item.category.value
        if cat not in category_data:
            category_data[cat] = {"count": 0, "amount": 0}
        category_data[cat]["count"]  += 1
        category_data[cat]["amount"] += item.amount

    by_category = [
        CategoryBreakdown(
            category=cat,
            count=data["count"],
            amount=data["amount"]
        )
        for cat, data in category_data.items()
    ]

    # monthly trend company wide
    monthly_data = {}
    for claim in all_claims:
        month_key = claim.created_at.strftime("%b %Y")
        if month_key not in monthly_data:
            monthly_data[month_key] = {"count": 0, "amount": 0}
        monthly_data[month_key]["count"]  += 1
        monthly_data[month_key]["amount"] += claim.total_amount

    monthly_trend = [
        MonthlyTrend(
            month=month,
            count=data["count"],
            amount=data["amount"]
        )
        for month, data in monthly_data.items()
    ]

    return AdminAnalytics(
        total_claims   = total_claims,
        total_amount   = total_amount,
        total_approved = total_approved,
        total_pending  = total_pending,
        total_rejected = total_rejected,
        fraud_alerts   = fraud_alerts,
        by_department  = by_department,
        by_category    = by_category,
        monthly_trend  = monthly_trend,
    )
