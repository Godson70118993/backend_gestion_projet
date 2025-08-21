# app/main.py
from datetime import timedelta, datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, case
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# AJOUTEZ CES LIGNES AU DÉBUT
from dotenv import load_dotenv
load_dotenv()  # Charge les variables du fichier .env

from . import crud, models, schemas
from .database import engine
from .dependencies import get_db, get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

# Crée les tables dans la base de données au démarrage de l'application
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API de Gestion de Projets", version="1.1.0")

# Configuration CORS pour permettre les requêtes depuis différents frontends
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://frontend-gestion-projet.vercel.app", # URL de production du frontend
    "https://backend-gestion-projet-6.onrender.com" # URL de production du backend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Configuration email - maintenant les variables seront chargées depuis .env
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")

# AJOUTEZ CETTE FONCTION DE DEBUG (optionnel)
def check_email_config():
    """Fonction pour vérifier la configuration email au démarrage"""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("⚠️  ATTENTION: Configuration email manquante!")
        print("   Vérifiez votre fichier .env")
        print(f"   SMTP_USERNAME: {'✓' if SMTP_USERNAME else '✗'}")
        print(f"   SMTP_PASSWORD: {'✓' if SMTP_PASSWORD else '✗'}")
    else:
        print("✅ Configuration email OK")
        print(f"   Email configuré: {SMTP_USERNAME}")

# Appeler la vérification au démarrage
check_email_config()

def send_reset_email(email: str, token: str, background_tasks: BackgroundTasks):
    """Envoie l'email de réinitialisation en arrière-plan"""
    background_tasks.add_task(send_email_async, email, token)

def send_email_async(email: str, token: str):
    """Fonction asynchrone pour envoyer l'email avec gestion d'erreur améliorée"""
    try:
        # Vérifier que les credentials email sont configurés
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            print("❌ Configuration email manquante - Email non envoyé")
            print("Vérifiez votre fichier .env et redémarrez l'application")
            return
        
        print(f"🔄 Tentative d'envoi d'email à {email}...")
        print(f"📧 Serveur SMTP: {SMTP_SERVER}:{SMTP_PORT}")
        print(f"👤 Utilisateur: {SMTP_USERNAME}")
        
        # Créer le message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USERNAME
        msg['To'] = email
        msg['Subject'] = "Réinitialisation de votre mot de passe"
        
        # URL de réinitialisation
        reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
        
        # Contenu HTML de l'email
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Réinitialisation de mot de passe</h1>
                </div>
                
                <div style="padding: 30px; background-color: #f9f9f9;">
                    <h2 style="color: #333;">Bonjour,</h2>
                    <p style="color: #666; line-height: 1.6;">
                        Vous avez demandé à réinitialiser votre mot de passe. 
                        Cliquez sur le bouton ci-dessous pour créer un nouveau mot de passe :
                    </p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}" 
                           style="background: #667eea; color: white; padding: 12px 30px; 
                                  text-decoration: none; border-radius: 5px; font-weight: bold;
                                  display: inline-block;">
                            Réinitialiser mon mot de passe
                        </a>
                    </div>
                    
                    <p style="color: #666; line-height: 1.6;">
                        Si le bouton ne fonctionne pas, copiez et collez ce lien dans votre navigateur :<br>
                        <a href="{reset_url}" style="color: #667eea;">{reset_url}</a>
                    </p>
                    
                    <p style="color: #999; font-size: 14px; margin-top: 30px;">
                        Ce lien expire dans 1 heure pour des raisons de sécurité.<br>
                        Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
                    </p>
                </div>
                
                <div style="background: #333; color: white; padding: 20px; text-align: center;">
                    <p style="margin: 0; font-size: 14px;">
                        © 2024 Votre Application de Gestion de Projets
                    </p>
                </div>
            </body>
        </html>
        """
        
        msg.attach(MIMEText(html_body, 'html'))
        
        # Envoyer l'email
        print("🔐 Connexion au serveur SMTP...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        
        print("🔑 Authentification...")
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        print("📤 Envoi de l'email...")
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email de réinitialisation envoyé avec succès à {email}")
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ Erreur d'authentification SMTP: {e}")
        print("🔍 Solutions possibles :")
        print("   1. Vérifiez vos identifiants Gmail")
        print("   2. Utilisez un mot de passe d'application (pas votre mot de passe Gmail)")
        print("   3. Activez la validation en 2 étapes sur votre compte Google")
        print("   4. Créez un nouveau mot de passe d'application")
        
    except smtplib.SMTPConnectError as e:
        print(f"❌ Erreur de connexion SMTP: {e}")
        print("🔍 Vérifiez votre connexion internet et les paramètres SMTP")
        
    except smtplib.SMTPException as e:
        print(f"❌ Erreur SMTP générale: {e}")
        
    except Exception as e:
        print(f"❌ Erreur inattendue lors de l'envoi de l'email: {e}")
        print(f"Type d'erreur: {type(e).__name__}")
        
        
# Le reste de votre code reste identique...
@app.get("/")
def read_root():
    """Point d'entrée de l'API"""
    return {"message": "Bienvenue sur l'API de gestion de projets !"}

# Routes d'authentification
@app.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Inscription d'un nouvel utilisateur"""
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Un compte avec cet email existe déjà"
        )
    
    db_user_username = crud.get_user_by_username(db, username=user.username)
    if db_user_username:
        raise HTTPException(
            status_code=400,
            detail="Ce nom d'utilisateur est déjà pris"
        )
    
    return crud.create_user(db=db, user=user)

@app.post("/login", response_model=schemas.Token)
def login_user(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Connexion d'un utilisateur et création d'un token d'accès"""
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

# Routes pour la réinitialisation de mot de passe
@app.post("/forgot-password", response_model=schemas.ForgotPasswordResponse)
async def forgot_password(
    request: schemas.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Endpoint pour demander une réinitialisation de mot de passe"""
    
    # Vérifier si l'utilisateur existe
    user = crud.get_user_by_email(db, request.email)
    if not user:
        # Pour des raisons de sécurité, on ne révèle pas si l'email existe
        return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}
    
    # Créer un token de réinitialisation
    token = crud.create_password_reset_token(db, user.id)
    
    # Envoyer l'email en arrière-plan
    send_reset_email(request.email, token, background_tasks)
    
    return {"message": "Si cet email existe, un lien de réinitialisation a été envoyé."}

@app.post("/reset-password", response_model=schemas.ResetPasswordResponse)
async def reset_password(
    request: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Endpoint pour réinitialiser le mot de passe avec un token"""
    
    # Valider le nouveau mot de passe
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=400, 
            detail="Le mot de passe doit contenir au moins 8 caractères"
        )
    
    # Utiliser le token pour changer le mot de passe
    success = crud.use_reset_token(db, request.token, request.new_password)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Token invalide ou expiré"
        )
    
    return {"message": "Mot de passe réinitialisé avec succès"}

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
    status: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère toutes les tâches d'un projet (avec filtre optionnel par statut)"""
    tasks = crud.get_tasks_by_project(db, project_id=project_id, user_id=current_user.id)
    
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

# Route pour les statistiques utilisateur - OPTIMISÉE
@app.get("/stats")
def get_user_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Récupère les statistiques de l'utilisateur avec des requêtes de base de données optimisées"""
    user_id = current_user.id
    now = datetime.utcnow()

    # Compter les projets
    total_projects = db.query(models.Project).filter(models.Project.owner_id == user_id).count()
    
    # Compter les tâches par statut directement dans la base de données
    tasks_counts = db.query(
        func.count(case((models.Task.status == "a_faire", 1))),
        func.count(case((models.Task.status == "en_cours", 1))),
        func.count(case((models.Task.status == "termine", 1))),
        func.count(case(((models.Task.due_date < now) & (models.Task.status != "termine"), 1)))
    ).join(models.Project).filter(models.Project.owner_id == user_id).first()
    
    tasks_a_faire, tasks_en_cours, tasks_terminees, tasks_en_retard = tasks_counts if tasks_counts else (0, 0, 0, 0)
    total_tasks = tasks_a_faire + tasks_en_cours + tasks_terminees
    
    # Récupérer le projet le plus récent
    latest_project = db.query(models.Project).filter(models.Project.owner_id == user_id).order_by(models.Project.created_at.desc()).first()

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