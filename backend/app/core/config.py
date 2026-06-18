from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL:str #postgresql connection string
    SECRET_KEY:str= "claimflow-super-secert-key-2026"  # used to sign JWT  tokens
    ALGORITHM:str = "HS256"   # how JWT is encrypted
    ACCESS_TOKEN_EXPIRE_MINUTES:int = 30
    GROQ_API_KEY:str
    
    class Config:
      env_file = ".env"
      extra= "ignore"

settings= Settings()  # setting is one object used everywhere in the project