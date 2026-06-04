from fastapi import APIRouter,Depends,HTTPException, status
from uuid import UUID
from sqlalchemy.orm import Session
from app.core.database import get_db 
from app.core.security import hash_password,verify_password,create_access_token,get_current_manager
from app.models.models import User,UserRole,EmployeeLevel
from app.schemas.schemas import UserRegister,UserLogin,UserResponse,EmployeeLevel



router = APIRouter()

@router.post("/register", response_model =UserResponse)
def register(user: UserRegister, db: Session = Depends(get_db)):
  existing = db.query(User).filter(User.email==user.email).first()
  if existing:
    raise HTTPException(status_code=400, detail="Email already registerd")
  
  new_user =User(
    full_name = user.full_name,
    email=user.email,
    password_hash = hash_password(user.password),
    role = user.role
    
  )
  db.add(new_user)
  db.commit()
  db.refresh(new_user)
  return new_user


@router.post("/login")
def login(user : UserLogin, db:Session=Depends(get_db)):
  db_user = db.query(User).filter(User.email == user.email).first()
  if not db_user or not verify_password(user.password,db_user.password_hash):
    raise HTTPException(status_code=401, detail="Invalid credentials")
  
  token = create_access_token({"sub":str(db_user.id)})
  return {"access_token": token, "token_type":"bearer"}

    
@router.patch("/{user_id}/set-level")
def set_employee_level(
    user_id: UUID,
    level: EmployeeLevel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_manager),
):
    """Admin/Manager sets employee level. Manager/Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.employee_level = level
    db.commit()
    db.refresh(user)
    return {"message": f"{user.full_name} level set to {level.value}"}