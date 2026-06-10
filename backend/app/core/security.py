from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from passlib.context import CryptContext

from app.core.config import settings

from fastapi import Depends,HTTPException,status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User,UserRole


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") #bycrpt it is the safest way to stor password
http_bearer = HTTPBearer()

def hash_password(password:str) ->str: #hash password convert plain password into hashedpassword
  return pwd_context.hash(password)


def verify_password(plain_password:str, hashed_password:str) ->bool:
  return pwd_context.verify(plain_password, hashed_password)

# this function will create access token for user when they logs in successfully and return the token to the user
def create_access_token(data:dict, expires_delta: Optional[timedelta] = None):
  to_encode = data.copy()
  if expires_delta:
    expire = datetime.utcnow() + expires_delta
  else:
    expire =  datetime.utcnow() + timedelta(minutes= settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
  to_encode.update({"exp":expire})
  return jwt.encode(to_encode, settings.SECRET_KEY,algorithm=settings.ALGORITHM)

# it verifies user request token is real and not expried
def decode_access_token(token:str):
  try:
    payload = jwt.decode(token, settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
    return payload
  except JWTError:
    return None


def get_current_user(
  credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
  db:Session = Depends(get_db)
):
  
  token = credentials.credentials
  payload = decode_access_token(token)
  if not payload:
    raise HTTPException(status_code=401,detail="invalid or expired token")
  
  user_id = payload.get("sub")
  if not user_id:
    raise HTTPException(status_code=401, detail="Invalid token")
  
  user = db.query(User).filter(User.id == user_id).first()
  if not user:
    raise HTTPException(status_code=401, detail="User not found")
  
  
  return user


def get_current_manager(
  current_user: User = Depends(get_current_user)
)-> User:
  
  """ Dependency to ensure the current user is a manager.
      used to protect manger-only endpoints like approve/reject/pending
  """
  
  if current_user.role != UserRole.manager:
    raise HTTPException(
      status_code = status.HTTP_403_FORBIDDEN,
      detail = "Only managers can access this resource"
    )
    
  return current_user

def get_current_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Only admin can access"""
    if current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this resource"
        )
    return current_user
  
  
def require_role(*allowed_roles: str):
    """
    Dependency that checks if current user has one of the allowed roles.
    
    Usage:
        Depends(require_role("admin"))
        Depends(require_role("admin", "finance"))
    """
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

  
  