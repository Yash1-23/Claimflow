from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL:str #postgresql connection string
    SECRET_KEY:str   # used to sign JWT  tokens
    ALGORITHM:str = "HS256"   # how JWT is encrypted
    ACCESS_TOKEN_EXPIRE_MINUTES:int = 30
    GROQ_API_KEY:str
    
    class Config:
      env_file = ".env"

settings= Settings()  # setting is one object used everywhere in the project