from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine,Base
from app.api.v1 import users,claims


Base.metadata.create_all(bind=engine)

app = FastAPI(
  title = "ClaimFlow API",
  description="Expense Claim Management System",
  version = "1.0.0"
  
)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
   
app.include_router(users.router, prefix="/api/v1/users",tags=["Users"]) 
app.include_router(claims.router,prefix="/api/v1/claims",tags=["claims"])
@app.get("/")
def root():
  return {"message": "ClaimFlow API is running"}

@app.get("/health")
def health():
  return {"status":"ok"} 
      
