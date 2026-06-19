"""
Claims Service - Business logic for claims

Why Service Layer?
- API routes only handle HTTP (request/response)
- Business logic lives here (calculations, DB operations, orchestration)
- Easy to test without HTTP
"""

from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from app.services.rule_engine import run_rules
from app.models.models import ExpenseClaim, ClaimLineItem, ClaimStatus
from app.schemas.schemas import ClaimCreate
from app.services.audit_service import log_action
from app.agents.claim_pipeline import run_claim_pipeline


def create_claim(db: Session, user_id: UUID, data: ClaimCreate) -> ExpenseClaim:
    # step 1: calculate total from all line items
    total = sum(item.amount for item in data.line_items)

    # step 2: create the claim
    claim = ExpenseClaim(
        user_id=user_id,
        title=data.title,
        total_amount=total,
        status=ClaimStatus.draft,
    )
    db.add(claim)
    db.flush()  # gets claim.id without committing

    # step 3: create each line item
    for item in data.line_items:
        line_item = ClaimLineItem(
            claim_id=claim.id,
            category=item.category,
            description=item.description,
            amount=item.amount,
            expense_date=item.expense_date,
        )
        db.add(line_item)

    db.commit()
    db.refresh(claim)
    return claim


def get_user_claims(db: Session, user_id: UUID) -> list:
    claims = (
        db.query(ExpenseClaim)
        .filter(ExpenseClaim.user_id == user_id)
        .order_by(ExpenseClaim.created_at.desc())
        .all()
    )
    # fix None policy_violations for old records
    for claim in claims:
        if claim.policy_violations is None:
            claim.policy_violations = []
    return claims


def get_claim_by_id(db: Session, claim_id: UUID, user_id: UUID) -> ExpenseClaim | None:
    return (
        db.query(ExpenseClaim)
        .filter(ExpenseClaim.id == claim_id, ExpenseClaim.user_id == user_id)
        .first()
    )


def submit_claim(db: Session, claim_id: UUID, user_id: UUID) -> ExpenseClaim:
    claim = get_claim_by_id(db, claim_id, user_id)

    if not claim:
        return None

    # Only draft claims can be submitted
    if claim.status != ClaimStatus.draft:
        raise ValueError(f"Claim is already {claim.status}, cannot submit")

    # Guard: must have at least one line item
    if not claim.line_items:
        raise ValueError("Claim must have at least one line item before submitting")

    # ---- STEP 1: rule engine (fast deterministic checks) ----
    decision = run_rules(claim, db)
    now = datetime.utcnow()

    if decision.final_decision == "rejected":
        # Only BLOCK-level rules land here (future dates, stale claim)
        claim.policy_violations = [
            {"severity": f.severity, "rule": f.rule, "message": f.message}
            for f in decision.flags
        ]
        claim.status = ClaimStatus.rejected
        claim.rejected_at = now
        claim.submitted_at = now
        log_action(
            db,
            user_id=user_id,
            action="claim_rejected_auto",
            entity_type="expense_claims",
            entity_id=claim.id,
            old_value={"status": "draft"},
            new_value={"status": "rejected", "reason": "BLOCK rule triggered"},
        )
        db.commit()
        db.refresh(claim)
        return claim

    # ---- STEP 2: mark submitted, then run the AGENT PIPELINE ----
    claim.status = ClaimStatus.submitted
    claim.submitted_at = now
    db.commit()
    db.refresh(claim)

    # Run multi-agent orchestration: fraud -> policy -> approval -> save
    # The pipeline writes risk_score, agent_decision, agent_reasoning,
    # policy_violations (rich dict), and sets status to under_review.
    try:
        pipeline_result = run_claim_pipeline(db, claim)
        print(f"[submit_claim] pipeline result: {pipeline_result}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[submit_claim] PIPELINE FAILED: {e}")
        # claim stays 'submitted' for manual review if pipeline crashes

    db.refresh(claim)

    log_action(
        db,
        user_id=user_id,
        action="claim_submitted",
        entity_type="expense_claims",
        entity_id=claim.id,
        old_value={"status": "draft"},
        new_value={
            "status": claim.status.value if claim.status else "submitted",
            "agent_recommendation": claim.agent_decision,
            "risk_score": claim.risk_score,
        },
    )

    db.commit()
    db.refresh(claim)
    return claim
  
  
  
    
    
  