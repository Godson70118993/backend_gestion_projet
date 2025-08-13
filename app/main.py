# app/main.py
from datetime import timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import engine
from .dependencies import get_db, get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

# Création des tables dans la base de données
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API de Gestion de Projets", version="1.0.0")

# Configuration CORS UNIQUE - permettre à la fois React et Vite
origins = [
    "http://localhost:3000",    # React dev server
    "http://127.0.0.1:3000",
    "http://localhost:5173",    # Vite dev server  
    "http://127.0.0.1:5173",
    "https://frontend-gestion-projet.vercel.app/", # URL de production de l'application Vite
    "https://backend-gestion-projet-3.onrender.com"  # URL de production de l'API
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Bienvenue sur l'API de gestion de projets !"}

# Routes d'authentification
@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Inscription d'un nouvel utilisateur"""
    # Vérifier si l'email existe déjà
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Un compte avec cet email existe déjà"
        )
    
    # Vérifier si le nom d'utilisateur existe déjà
    db_user_username = crud.get_user_by_username(db, username=user.username)
    if db_user_username:
        raise HTTPException(
            status_code=400,
            detail="Ce nom d'utilisateur est already pris"
        )
    
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.Token)
def login_user(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Connexion d'un utilisateur"""
    user = crud.authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Connexion d'un utilisateur (route alternative pour /token)"""
    user = crud.authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """Récupère les informations de l'utilisateur connecté"""
    return current_user

# Routes pour les projets
@app.get("/projects", response_model=list[schemas.Project])
def get_my_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère tous les projets de l'utilisateur connecté"""
    projects = crud.get_projects_by_user(db, user_id=current_user.id, skip=skip, limit=limit)
    return projects

@app.post("/projects", response_model=schemas.Project)
def create_project(
    project: schemas.ProjectCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée un nouveau projet"""
    return crud.create_project(db=db, project=project, user_id=current_user.id)

@app.get("/projects/{project_id}", response_model=schemas.Project)
def get_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère un projet spécifique"""
    project = crud.get_project_by_id(db, project_id=project_id, user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    return project

@app.put("/projects/{project_id}", response_model=schemas.Project)
def update_project(
    project_id: int,
    project_update: schemas.ProjectUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Met à jour un projet"""
    project = crud.update_project(db, project_id=project_id, project_update=project_update, user_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    return project

@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime un projet"""
    success = crud.delete_project(db, project_id=project_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    return {"message": "Projet supprimé avec succès"}

# Routes pour les tâches
@app.get("/projects/{project_id}/tasks", response_model=list[schemas.Task])
def get_project_tasks(
    project_id: int,
    status: Optional[str] = None,  # Filtrer par statut optionnel
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère toutes les tâches d'un projet (avec filtre optionnel par statut)"""
    tasks = crud.get_tasks_by_project(db, project_id=project_id, user_id=current_user.id)
    
    # Filtrer par statut si spécifié
    if status:
        tasks = [task for task in tasks if task.status.value == status]
    
    return tasks

@app.post("/projects/{project_id}/tasks", response_model=schemas.Task)
def create_task(
    project_id: int,
    task: schemas.TaskCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crée une nouvelle tâche dans un projet"""
    db_task = crud.create_task(db=db, task=task, project_id=project_id, user_id=current_user.id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Projet non trouvé")
    return db_task

@app.get("/tasks/{task_id}", response_model=schemas.Task)
def get_task(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère une tâche spécifique"""
    task = crud.get_task_by_id(db, task_id=task_id, user_id=current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return task

@app.put("/tasks/{task_id}", response_model=schemas.Task)
def update_task(
    task_id: int,
    task_update: schemas.TaskUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Met à jour une tâche"""
    task = crud.update_task(db, task_id=task_id, task_update=task_update, user_id=current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return task

@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Supprime une tâche"""
    success = crud.delete_task(db, task_id=task_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    return {"message": "Tâche supprimée avec succès"}

# Route de santé pour vérifier que l'API fonctionne
@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Route pour les statistiques utilisateur avec les nouveaux statuts
@app.get("/stats")
def get_user_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère les statistiques de l'utilisateur avec les dates et statuts"""
    projects = crud.get_projects_by_user(db, user_id=current_user.id)
    
    total_projects = len(projects)
    
    # Compter les tâches par statut
    all_tasks = []
    for project in projects:
        all_tasks.extend(project.tasks)
    
    total_tasks = len(all_tasks)
    tasks_a_faire = len([task for task in all_tasks if task.status.value == "a_faire"])
    tasks_en_cours = len([task for task in all_tasks if task.status.value == "en_cours"])
    tasks_terminees = len([task for task in all_tasks if task.status.value == "termine"])
    
    # Tâches en retard (échéance dépassée)
    from datetime import datetime
    now = datetime.utcnow()
    tasks_en_retard = len([
        task for task in all_tasks 
        if task.due_date and task.due_date < now and task.status.value != "termine"
    ])
    
    # Projet le plus récent
    latest_project = max(projects, key=lambda p: p.created_at) if projects else None
    
    return {
        "user_since": current_user.created_at,
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "tasks_by_status": {
            "a_faire": tasks_a_faire,
            "en_cours": tasks_en_cours,
            "terminees": tasks_terminees
        },
        "tasks_en_retard": tasks_en_retard,
        "latest_project": {
            "title": latest_project.title,
            "created_at": latest_project.created_at
        } if latest_project else None
    }

# Route pour obtenir les statuts disponibles
@app.get("/task-statuses")
def get_task_statuses():
    """Récupère la liste des statuts possibles pour les tâches"""
    return {
        "statuses": [
            {"value": "a_faire", "label": "À faire"},
            {"value": "en_cours", "label": "En cours"},
            {"value": "termine", "label": "Terminé"}
        ]
    }