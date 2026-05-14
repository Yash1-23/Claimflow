from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ClaimFlow")


#temporary stroage
claims_db = []
claim_counter = 1 #gives a each claim a unique id


class Claim(BaseModel):
    title:str
    amount: float
    category: str

@app.get("/")
def home():
    return {'message': "ClaimFlow is running"}
  
  
@app.post("/claims")
def create_claim(claim:Claim):
  global claim_counter
  new_claim = {
    "id": claim_counter,
    "title": claim.title,
    "amount": claim.amount,
    "category": claim.category,
    "status":"draft"
  }
  claims_db.append(new_claim)
  claim_counter +=1
  
  return{
    "message":"claim created successfully",
    "claim":new_claim
  }
  
  
  
@app.get("/claims")
def get_claims():
  return {
    "total":len(claims_db),
    "claims":claims_db
  }
  

# New -get one claim by ID
@app.get("/claims/{claim_id}")
def get_claim(claim_id: int):
  for claim in claims_db:
    if claim["id"] == claim_id:
      return claim
  return {"error": "Claim is not found"}

@app.patch("/claims/{claim_id}/cancel") #patch is used for partiall updates to an existing resources
def cancel_claim(claim_id:int):
  for index, claim in enumerate(claims_db):
    if claim['id'] == claim_id:
      if claim["status"] == "submitted":
        return  {"error":"cannot cancelled submitted claim"}
      
      claim['status'] = "cancelled"
      return {"message": f"Claim  {claim_id} cancelled!","claim":claim}
  return {"error": "Claim not found"}
      
      
