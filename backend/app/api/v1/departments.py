from fastapi import APIRouter,Depends, HTTPException,status
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.database import get_db
from app.core.security import get_current_user, get_current_manager
from app.models.models import Department,User
from app.schemas.schemas import DepartmentCreate, DepartmentUpdate,DepartmentResponse
from pydantic import BaseModel
from typing import Optional
import uuid


router = APIRouter()



# Department endpoint
@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
  data : DepartmentCreate,
  db:Session = Depends(get_db),
  current_user: User = Depends(get_current_manager), ##logged in manager
):
  
  """Create a new department. Manager/Admin Only
     Logged in manger is automatically set as manager
  """
     
  
  #Check if department name already exists
  existing = db.query(Department).filter(Department.name==data.name).first()
  if existing:
    raise HTTPException(status_code=400, detail="Department already exists")
  


  dept = Department(
    id = uuid.uuid4(),
    name= data.name,
    bau_code=data.bau_code,
    manager_id =current_user.id,
    
    
  )
  
  db.add(dept)
  db.commit()
  db.refresh(dept)
  return dept


@router.get("/",response_model=list[DepartmentResponse])
def list_departments(
  db : Session = Depends(get_db),
  current_user:User = Depends(get_current_user),
  
):
  """ List all departments. All users can view"""
  return db.query(Department).all()

@router.get("/{dept_id}",response_model=DepartmentResponse)
def get_department(
   dept_id: UUID,
   db:Session = Depends(get_db),
   current_user :User = Depends(get_current_user),
):
  
  """Get a single department by ID"""
  
  dept = db.query(Department).filter(Department.id==dept_id).first()
  if not dept:
    raise HTTPException(status_code=404,detail= "Department not found")
  return dept


@router.patch("/{dept_id}",response_model= DepartmentResponse)
def update_department(
  dept_id: UUID,
  data: DepartmentUpdate,
  db:Session = Depends(get_db),
  current_user: User = Depends(get_current_manager)
  
):
  
  """Update department name or manager. Manager/Admin only."""
  
  dept = db.query(Department).filter(Department.id==dept_id).first()
  if not dept:
    raise HTTPException(status_code=404, detail="Department not found")
  
   # Validate new manager_id if provided
  if data.manager_id:
    manager = db.query(User).filter(User.id == data.manager_id).first()
    if not manager:
      raise HTTPException(status_code=404, detail="Manager user not found")
  
  
  if data.name:
    dept.name = data.name 
  if data.manager_id:
    dept.manager_id = data.manager_id
    
  db.commit()
  db.refresh(dept)
  return dept


@router.delete("/{dept_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
  dept_id : UUID,
  db:Session = Depends(get_db),
  current_user:User = Depends(get_current_manager),
  
):
  """ Delete a department. Manger/admin Only."""
  
  dept = db.query(Department).filter(Department.id==dept_id).first()
  if not dept:
    raise HTTPException(status_code=404,detail= "Department not found")
  
  db.delete(dept)
  db.commit()
  return None


@router.post("/{dept_id}/assign-user/{user_id}")
def assign_user_to_department(
  dept_id :UUID,
  user_id: UUID,
  db:Session = Depends(get_db),
  current_user :User= Depends(get_current_manager)
):
  """ Assign a user to a department. Manager/Admin Only"""
  
  dept = db.query(Department).filter(Department.id==dept_id).first()
  if not dept:
    raise HTTPException(status_code= 404, detail="Department not found")
  
  user = db.query(User).filter(User.id == user_id).first()
  
  if not user:
    raise HTTPException(status_code=404, detail= "User not found")
  
  
  user.department_id = dept_id
  db.commit()
  
  return {"message":f"{user.full_name} assgined to {dept.name}"}