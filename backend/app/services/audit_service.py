"""
Aduit  service - writes to audit_log table.
Call this after every important state changes
  
"""

from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.models import AuditLog

def log_action(
   db:Session,
   user_id:UUID,
   action:str,
   entity_type:str,
   entity_id:UUID,
   old_value:dict = None,
   new_value:dict= None
  
):
  """
    write one audit log row
     action -> what happened eg. "claim_submitted"
     entity_type-> what table eg."expense_claim"
     entity_id -> which record eg."claim.id"
     old_value -> before state eg. {"status":"draft"}
     new_vlaue -> after state eg.{"status": "submitted}
  """
  print(f"log_action called: {action} for {entity_id}")
  log = AuditLog(
    user_id = user_id,
    action=action,
    entity_type="expense_claims",
    entity_id=entity_id,
    old_value=old_value,
    new_value=new_value,
    timestamp=datetime.utcnow()
  )
  db.add(log)
  
  


