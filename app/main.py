# app/main.py - Version améliorée pour la gestion des emails

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
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configuration du logging pour debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AJOUTEZ CES LIGNES AU DÉBUT
from dotenv import load_dotenv
load_dotenv()  # Charge les variables du fichier .env

from . import crud, models, schemas
from .database import engine
from .dependencies import get_db, get_current_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

# Crée les tables dans la base de données au démarrage de l'application
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="API de Gestion de Projets", version="1.1.0")

# Configuration CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://frontend-gestion-projet.vercel.app",
    "https://backend-gestion-projet-7.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Configuration email - AMÉLIORÉE
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")

# Executor pour les tâches en arrière-plan
email_executor = ThreadPoolExecutor(max_workers=3)

def check_email_config():
    """Fonction pour vérifier la configuration email au démarrage"""
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        logger.error("⚠️  ATTENTION: Configuration email manquante!")
        logger.error("   Vérifiez votre fichier .env")
        logger.error(f"   SMTP_USERNAME: {'✓' if SMTP_USERNAME else '✗'}")
        logger.error(f"   SMTP_PASSWORD: {'✓' if SMTP_PASSWORD else '✗'}")
        return False
    else:
        logger.info("✅ Configuration email OK")
        logger.info(f"   Email configuré: {SMTP_USERNAME}")
        logger.info(f"   Frontend URL: {FRONTEND_URL}")
        return True

# Appeler la vérification au démarrage
email_config_ok = check_email_config()

def test_smtp_connection():
    """Teste la connexion SMTP au démarrage"""
    if not email_config_ok:
        return False
        
    try:
        logger.info("🔄 Test de connexion SMTP...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.quit()
        logger.info("✅ Connexion SMTP réussie!")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur de connexion SMTP: {e}")
        return False

# Test de la connexion au démarrage
smtp_ok = test_smtp_connection()

async def send_reset_email_async(email: str, token: str):
    """Version asynchrone améliorée pour envoyer l'email"""
    
    def send_email_sync():
        """Fonction synchrone pour l'envoi d'email"""
        try:
            if not email_config_ok:
                logger.error("❌ Configuration email manquante - Email non envoyé")
                return False
            
            logger.info(f"🔄 Envoi d'email de réinitialisation à {email}...")
            
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['From'] = SMTP_USERNAME
            msg['To'] = email
            msg['Subject'] = "🔐 Réinitialisation de votre mot de passe"
            
            # URL de réinitialisation - CORRECTION ICI
            reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
            logger.info(f"🔗 URL de réinitialisation: {reset_url}")
            
            # Contenu HTML amélioré
            html_body = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Réinitialisation de mot de passe</title>
            </head>
            <body style="margin: 0; padding: 0; font-family: 'Arial', sans-serif; background-color: #f5f5f5;">
                <table style="width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff;">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center;">
                            <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: bold;">
                                🔐 Réinitialisation de mot de passe
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px 30px; background-color: #ffffff;">
                            <h2 style="color: #333333; margin: 0 0 20px 0; font-size: 20px;">Bonjour,</h2>
                            
                            <p style="color: #666666; line-height: 1.6; margin: 0 0 25px 0; font-size: 16px;">
                                Vous avez demandé à réinitialiser votre mot de passe pour votre compte de gestion de projets.
                            </p>
                            
                            <p style="color: #666666; line-height: 1.6; margin: 0 0 30px 0; font-size: 16px;">
                                Cliquez sur le bouton ci-dessous pour créer un nouveau mot de passe sécurisé :
                            </p>
                            
                            <!-- Button -->
                            <div style="text-align: center; margin: 40px 0;">
                                <a href="{reset_url}" 
                                   style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                          color: #ffffff; 
                                          padding: 15px 35px; 
                                          text-decoration: none; 
                                          border-radius: 8px; 
                                          font-weight: bold;
                                          font-size: 16px;
                                          display: inline-block;
                                          box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);">
                                    ✨ Réinitialiser mon mot de passe
                                </a>
                            </div>
                            
                            <!-- Alternative link -->
                            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea;">
                                <p style="color: #666666; margin: 0 0 10px 0; font-size: 14px; font-weight: bold;">
                                    Le bouton ne fonctionne pas ?
                                </p>
                                <p style="color: #666666; margin: 0; font-size: 14px; line-height: 1.5;">
                                    Copiez et collez ce lien dans votre navigateur :<br>
                                    <a href="{reset_url}" style="color: #667eea; word-break: break-all;">{reset_url}</a>
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Security info -->
                    <tr>
                        <td style="padding: 30px; background-color: #fff3cd; border-top: 1px solid #ffeaa7;">
                            <div style="display: flex; align-items: flex-start;">
                                <span style="font-size: 20px; margin-right: 15px;">⚠️</span>
                                <div>
                                    <p style="color: #856404; margin: 0 0 10px 0; font-weight: bold; font-size: 14px;">
                                        Informations importantes :
                                    </p>
                                    <ul style="color: #856404; margin: 0; padding-left: 20px; font-size: 13px;">
                                        <li>Ce lien expire dans <strong>1 heure</strong> pour votre sécurité</li>
                                        <li>Si vous n'avez pas demandé cette réinitialisation, ignorez cet email</li>
                                        <li>Votre mot de passe actuel reste inchangé tant que vous n'en créez pas un nouveau</li>
                                        <li>Utilisez un mot de passe fort avec au moins 8 caractères</li>
                                    </ul>
                                </div>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #2c3e50; color: #ffffff; padding: 25px; text-align: center;">
                            <p style="margin: 0 0 10px 0; font-size: 16px; font-weight: bold;">
                                Gestion de Projets
                            </p>
                            <p style="margin: 0; font-size: 12px; opacity: 0.8;">
                                © 2024 - Tous droits réservés
                            </p>
                        </td>
                    </tr>
                </table>
            </body>
            </html>
            """
            
            # Version texte simple pour compatibilité
            text_body = f"""
            Réinitialisation de votre mot de passe
            
            Bonjour,
            
            Vous avez demandé à réinitialiser votre mot de passe.
            
            Cliquez sur ce lien pour créer un nouveau mot de passe :
            {reset_url}
            
            Ce lien expire dans 1 heure pour des raisons de sécurité.
            
            Si vous n'avez pas demandé cette réinitialisation, ignorez cet email.
            
            Cordialement,
            L'équipe Gestion de Projets
            """
            
            # Attacher les deux versions
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # Envoyer l'email avec retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔐 Tentative {attempt + 1}/{max_retries} - Connexion au serveur SMTP...")
                    
                    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=30)
                    server.set_debuglevel(1)  # Active le debug SMTP
                    server.starttls()
                    
                    logger.info("🔑 Authentification...")
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                    
                    logger.info("📤 Envoi de l'email...")
                    server.send_message(msg)
                    server.quit()
                    
                    logger.info(f"✅ Email envoyé avec succès à {email} (tentative {attempt + 1})")
                    return True
                    
                except smtplib.SMTPRecipientsRefused as e:
                    logger.error(f"❌ Adresse email refusée: {email} - {e}")
                    return False
                    
                except smtplib.SMTPAuthenticationError as e:
                    logger.error(f"❌ Erreur d'authentification SMTP (tentative {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        logger.error("🔍 Solutions possibles :")
                        logger.error("   1. Vérifiez que la validation en 2 étapes est activée")
                        logger.error("   2. Utilisez un mot de passe d'application Gmail")
                        logger.error("   3. Vérifiez que l'accès aux apps moins sécurisées est désactivé")
                        return False
                    
                except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:
                    logger.error(f"❌ Erreur de connexion SMTP (tentative {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        logger.info(f"⏳ Attente de 5 secondes avant la prochaine tentative...")
                        import time
                        time.sleep(5)
                    else:
                        return False
                        
                except Exception as e:
                    logger.error(f"❌ Erreur inattendue (tentative {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        return False
                        
            return False
            
        except Exception as e:
            logger.error(f"❌ Erreur critique lors de l'envoi de l'email: {e}")
            return False
    
    # Exécuter la fonction synchrone dans un thread
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(email_executor, send_email_sync)

def send_reset_email(email: str, token: str, background_tasks: BackgroundTasks):
    """Ajoute la tâche d'envoi d'email en arrière-plan"""
    background_tasks.add_task(send_reset_email_background, email, token)

async def send_reset_email_background(email: str, token: str):
    """Tâche en arrière-plan pour envoyer l'email"""
    try:
        success = await send_reset_email_async(email, token)
        if success:
            logger.info(f"✅ Tâche d'email terminée avec succès pour {email}")
        else:
            logger.error(f"❌ Échec de l'envoi d'email pour {email}")
    except Exception as e:
        logger.error(f"❌ Erreur dans la tâche d'arrière-plan d'email: {e}")

# Routes d'authentification...

@app.post("/forgot-password", response_model=schemas.ForgotPasswordResponse)
async def forgot_password(
    request: schemas.ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Endpoint amélioré pour demander une réinitialisation de mot de passe"""
    
    logger.info(f"🔄 Demande de réinitialisation pour: {request.email}")
    
    # Vérifier la configuration email
    if not email_config_ok:
        logger.error("❌ Configuration email manquante")
        raise HTTPException(
            status_code=500,
            detail="Service d'email non configuré. Contactez l'administrateur."
        )
    
    # Vérifier si l'utilisateur existe
    user = crud.get_user_by_email(db, request.email)
    if not user:
        logger.warning(f"⚠️ Tentative de réinitialisation pour email inexistant: {request.email}")
        # Pour la sécurité, on renvoie toujours le même message
        return {"message": "Si cet email existe dans notre système, un lien de réinitialisation a été envoyé."}
    
    logger.info(f"✅ Utilisateur trouvé: {user.username} (ID: {user.id})")
    
    try:
        # Créer un token de réinitialisation
        token = crud.create_password_reset_token(db, user.id)
        logger.info(f"🔑 Token de réinitialisation créé: {token[:10]}...")
        
        # Envoyer l'email en arrière-plan
        send_reset_email(request.email, token, background_tasks)
        
        logger.info(f"📧 Tâche d'email ajoutée en arrière-plan pour {request.email}")
        
        return {"message": "Si cet email existe dans notre système, un lien de réinitialisation a été envoyé."}
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la création du token ou envoi d'email: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne du serveur. Veuillez réessayer plus tard."
        )

@app.post("/reset-password", response_model=schemas.ResetPasswordResponse)
async def reset_password(
    request: schemas.ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """Endpoint pour réinitialiser le mot de passe avec un token"""
    
    logger.info(f"🔄 Tentative de réinitialisation avec token: {request.token[:10]}...")
    
    # Validation renforcée du nouveau mot de passe
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=400, 
            detail="Le mot de passe doit contenir au moins 8 caractères"
        )
    
    if not any(c.islower() for c in request.new_password):
        raise HTTPException(
            status_code=400, 
            detail="Le mot de passe doit contenir au moins une lettre minuscule"
        )
    
    if not any(c.isupper() for c in request.new_password):
        raise HTTPException(
            status_code=400, 
            detail="Le mot de passe doit contenir au moins une lettre majuscule"
        )
    
    if not any(c.isdigit() for c in request.new_password):
        raise HTTPException(
            status_code=400, 
            detail="Le mot de passe doit contenir au moins un chiffre"
        )
    
    # Utiliser le token pour changer le mot de passe
    try:
        success = crud.use_reset_token(db, request.token, request.new_password)
        
        if not success:
            logger.warning(f"⚠️ Échec de réinitialisation avec token: {request.token[:10]}...")
            raise HTTPException(
                status_code=400, 
                detail="Token invalide, expiré ou déjà utilisé"
            )
        
        logger.info(f"✅ Mot de passe réinitialisé avec succès pour token: {request.token[:10]}...")
        return {"message": "Mot de passe réinitialisé avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lors de la réinitialisation: {e}")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne du serveur. Veuillez réessayer plus tard."
        )

# Route de test pour l'email (à supprimer en production)
@app.post("/test-email")
async def test_email(email: str = "test@example.com"):
    """Route de test pour vérifier l'envoi d'emails"""
    if not email_config_ok:
        return {"error": "Configuration email manquante"}
    
    try:
        success = await send_reset_email_async(email, "test-token-123")
        return {"success": success, "message": "Test d'email terminé"}
    except Exception as e:
        return {"error": str(e)}
        
        
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