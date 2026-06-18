from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine,Base
from app.api.v1 import users,claims,receipts,departments,analytics
from fastapi.staticfiles import StaticFiles
from app.api.v1.rag import router as rag_router
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

Base.metadata.create_all(bind=engine)

#Rate Limiter
limiter = Limiter(key_func= get_remote_address)



app = FastAPI(
  title = "ClaimFlow API",
  description="Expense Claim Management System",
  version = "1.0.0"
  
)

# Add limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# this for to see pdf this creates staticfile link we can see in browser using that link
app.mount("/uploads",StaticFiles(directory="uploads"),name="uploads")
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)
   
app.include_router(users.router, prefix="/api/v1/users",tags=["Users"]) 
app.include_router(claims.router,prefix="/api/v1/claims",tags=["claims"])
app.include_router(receipts.router,prefix="/api/v1/receipts",tags=["receipts"])
app.include_router(departments.router,prefix="/api/v1/departments",tags=["Departments"])
app.include_router(analytics.router,prefix="/api/v1/analytics",tags=["Analytics"])
app.include_router(rag_router,prefix="/api/v1/rag",tags=["Policy RAG"])
@app.get("/")
def root():
  return {"message": "ClaimFlow API is running"}

@app.get("/health")
def health():
  return {"status":"ok"} 
      
