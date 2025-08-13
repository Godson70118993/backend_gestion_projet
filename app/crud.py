# app/crud.py
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from . import models, schemas

# Configuration pour le hachage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash un mot de passe"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie si un mot de passe correspond à son hash"""
    return pwd_context.verify(plain_password, hashed_password)

# CRUD pour les utilisateurs
def get_user_by_email(db: Session, email: str):
    """Récupère un utilisateur par son email"""
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    """Récupère un utilisateur par son nom d'utilisateur"""
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(db: Session, user_id: int):
    """Récupère un utilisateur par son ID"""
    return db.query(models.User).filter(models.User.id == user_id).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Crée un nouvel utilisateur"""
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    """Authentifie un utilisateur"""
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

# CRUD pour les projets
def get_projects_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Récupère les projets d'un utilisateur"""
    return db.query(models.Project).filter(models.Project.owner_id == user_id).offset(skip).limit(limit).all()

def get_project_by_id(db: Session, project_id: int, user_id: int):
    """Récupère un projet par son ID (seulement si il appartient à l'utilisateur)"""
    return db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == user_id
    ).first()

def create_project(db: Session, project: schemas.ProjectCreate, user_id: int):
    """Crée un nouveau projet avec date de création automatique"""
    db_project = models.Project(**project.dict(), owner_id=user_id)
    # created_at sera automatiquement défini par SQLAlchemy
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    print(f"Projet '{db_project.title}' créé le: {db_project.created_at}")  # Debug
    return db_project

def update_project(db: Session, project_id: int, project_update: schemas.ProjectUpdate, user_id: int):
    """Met à jour un projet"""
    db_project = get_project_by_id(db, project_id, user_id)
    if not db_project:
        return None
    
    update_data = project_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db.commit()
    db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: int, user_id: int):
    """Supprime un projet"""
    db_project = get_project_by_id(db, project_id, user_id)
    if not db_project:
        return False
    
    db.delete(db_project)
    db.commit()
    return True

# CRUD pour les tâches
def get_tasks_by_project(db: Session, project_id: int, user_id: int):
    """Récupère les tâches d'un projet (seulement si le projet appartient à l'utilisateur)"""
    project = get_project_by_id(db, project_id, user_id)
    if not project:
        return []
    return project.tasks

def get_task_by_id(db: Session, task_id: int, user_id: int):
    """Récupère une tâche par son ID (seulement si elle appartient à l'utilisateur)"""
    return db.query(models.Task).join(models.Project).filter(
        models.Task.id == task_id,
        models.Project.owner_id == user_id
    ).first()

def create_task(db: Session, task: schemas.TaskCreate, project_id: int, user_id: int):
    """Crée une nouvelle tâche avec date de création automatique"""
    # Vérifier que le projet appartient à l'utilisateur
    project = get_project_by_id(db, project_id, user_id)
    if not project:
        return None
    
    db_task = models.Task(**task.dict(), project_id=project_id)
    # created_at sera automatiquement défini par SQLAlchemy
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    print(f"Tâche '{db_task.title}' créée le: {db_task.created_at} avec le statut: {db_task.status}")  # Debug
    return db_task

def update_task(db: Session, task_id: int, task_update: schemas.TaskUpdate, user_id: int):
    """Met à jour une tâche"""
    db_task = get_task_by_id(db, task_id, user_id)
    if not db_task:
        return None
    
    update_data = task_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

def delete_task(db: Session, task_id: int, user_id: int):
    """Supprime une tâche"""
    db_task = get_task_by_id(db, task_id, user_id)
    if not db_task:
        return False
    
    db.delete(db_task)
    db.commit()
    return True