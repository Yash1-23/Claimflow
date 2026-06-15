"""
Approval Agent - ClaimFlow

PURE decision logic. No database, no model imports, no other-agent imports.
Takes plain values in, returns a recommendation dict out.
 
Every claim goes to a MANAGER for the final decision (full human oversight).
The agent does NOT auto-approve or auto-reject. Instead it produces a
RECOMMENDATION so the manager can decide quickly and well-informed.
 

Decision flow:
    policy rejected      -> REJECT            (high)
    fraud >= 0.6         -> REVIEW_CAREFULLY  (high)
    high amount / flagged / medium fraud -> REVIEW_CAREFULLY (medium/high)
    everything clean     -> APPROVE           (low)
    
    
Why this design:
- Enterprises are cautious about fully-automated money decisions.
- The AI agents (fraud, policy) ADVISE; the human DECIDES.
- This keeps a human accountable for every payout while still making
  them dramatically faster via pre-analysis.
 
 
Role model:
- employee : submits claims
- manager  : reviews every claim, makes final approve / reject / flag
- admin    : oversight, sees all data
"""



from datetime import datetime

#Threshold for recommendation strength + queue priority
HIGH_AMOUNT = 50000
FRAUD_HIGH = 0.6
FRAUD_MEDIUM = 0.3



def recommend_for_manager(total_amount: float, risk_score:float,policy_verdict:str) ->dict:
  """
    Produce a recommendation for the manager. Does NOT decide the claim.
    Pure function: plain inputs -> dict output. No side effects.
 
    Args:
        total_amount:   the claim amount
        risk_score:     0.0-1.0 fraud score (computed by fraud agent)
        policy_verdict: "approved" | "flagged" | "rejected" (from policy agent)
 
    Returns:
        {
            "recommendation": "APPROVE" | "REJECT" | "REVIEW_CAREFULLY",
            "priority": "low" | "medium" | "high",
            "reason": str,
            "confidence": float,
            "flags": [str, ...],
            "decided_at": iso timestamp
        }
    """
  flags = []
  risk_score = risk_score or  0.0
  policy_verdict = (policy_verdict or "flagged").lower()
  
  #policy violation -> recommend reject (manager confirms)
  if policy_verdict == "rejected":
    flags.append("policy_violation")
    return _build("REJECT", "high", "Claim violates company policy. Recommend rejection after manager review",0.9,flags)
  
  #High fraud risk -> review carefully (NEVER auto-anything)
  if risk_score >= FRAUD_HIGH:
        flags.append("high_fraud_risk")
        return _build(
            "REVIEW_CAREFULLY", "high",
            f"High fraud risk ({risk_score:.2f}). Investigate before deciding.",
            0.85, flags,
        )
  
  # Medium concerns -> review medium priority
  if total_amount >= HIGH_AMOUNT:
    flags.append("high_amount")
  if policy_verdict=="flagged":
    flags.append("policy_flagged")
  if FRAUD_MEDIUM <= risk_score < FRAUD_HIGH:
    flags.append("medium_fraud_risk")
    
  if flags:
    priority = "high" if total_amount >= HIGH_AMOUNT else "medium"
    return _build("REVIEW_CAREFULLY","medium", "Some signals need attention (amount,policy,or risk),Review before approving.", 0.7,flags)
  
  
  # cleanclaim -> recommend approve,low priority
  return _build("APPROVE","low","Low risk, policy-compliant,normal amount, Recommend approval.",0.8, flags)
    
    
def _build(recommendation, priority,reason,confidence,flags):
  return {
    "recommendation":recommendation,
    "priority": priority,
    "reason":reason,
    "confidence":confidence,
    "flags":flags,
    "decided_at":datetime.utcnow().isoformat(),
  }
