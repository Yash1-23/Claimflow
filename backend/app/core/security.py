from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") #bycrpt it is the safest way to stor password

def hash_password(password:str) ->str: #hash password convert plain password into hashedpassword
  return pwd_context.hash(password)


def verify_password(plain_password:str, hashed_password:str) ->bool:
  return pwd_context.verify(plain_password, hashed_password)

# this function will create access token for user when they logs in successfully and return the token to the user
def create_access_token(data:dict, expries_delta: Optional[timedelta] = None):
  to_encode = data.copy()
  if expries_delta:
    expire = datetime.utcnow() + expries_delta
  else:
    expire =  datetime.utcnow() + timedelta(minutes= settings.ACCESS_TOKEN_EXPIRE_MINTUES)
    
  to_encode.update({"exp":expire})
  return jwt.encode(to_encode, settings.SECRET_KEY,algorithm=settings.ALGORITHM)

# it verifies user request token is real and not expried
def decode_access_token(token:str):
  try:
    payload = jwt.decode(token, settings.SECRET_KEY,algorithms=[settings.ALGORITHM])
    return payload
  except JWTError:
    return None

