# app/dependencies.py
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt, ExpiredSignatureError
from sqlalchemy.orm import Session
from . import crud, models
from .database import SessionLocal
import logging

# Configuration des logs
logger = logging.getLogger(__name__)

# Clé secrète pour signer les tokens JWT (en production, utilisez une clé plus complexe et stockez-la de manière sécurisée)
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 180

# Configuration du bearer token
security = HTTPBearer()

def get_db():
    """Dépendance pour obtenir une session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_access_token(data: dict, expires_delta: timedelta = None):
    """Crée un token JWT"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # Debug amélioré
    logger.info(f"Token généré pour user_id: {data.get('sub')}")
    logger.info(f"Token expire le: {expire}")
    logger.debug(f"Token généré: {encoded_jwt[:50]}...")  # Afficher seulement les premiers caractères
    
    return encoded_jwt

def verify_token_expiry(token: str) -> dict:
    """Vérifie l'expiration du token et retourne des infos de debug"""
    try:
        # Décoder sans vérifier la signature pour obtenir les infos d'expiration
        payload = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = payload.get('exp')
        
        if exp_timestamp:
            exp_date = datetime.utcfromtimestamp(exp_timestamp)
            current_time = datetime.utcnow()
            time_diff = current_time - exp_date
            
            debug_info = {
                "exp_timestamp": exp_timestamp,
                "exp_date": exp_date.isoformat(),
                "current_time": current_time.isoformat(),
                "time_difference_seconds": time_diff.total_seconds(),
                "is_expired": current_time > exp_date,
                "user_id": payload.get('sub')
            }
            
            return debug_info
        
        return {"error": "No expiration timestamp found"}
        
    except Exception as e:
        return {"error": f"Cannot decode token: {str(e)}"}

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Dépendance pour obtenir l'utilisateur actuel à partir du token JWT"""
    
    try:
        token = credentials.credentials
        logger.info(f"Token reçu, longueur: {len(token)}")
        
        # Nettoyer le token en cas de doublon de "bearer"
        if token.lower().startswith('bearer '):
            token = token[7:]  # Enlever "bearer " du début
            logger.info(f"Token nettoyé, nouvelle longueur: {len(token)}")
        
        # Vérifier l'expiration avant de décoder
        debug_info = verify_token_expiry(token)
        if debug_info.get("is_expired"):
            logger.warning(f"Token expiré: {debug_info}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "Token has expired",
                    "expired_at": debug_info.get("exp_date"),
                    "current_time": debug_info.get("current_time"),
                    "expired_since_seconds": debug_info.get("time_difference_seconds")
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Décoder le token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        
        if user_id is None:
            logger.error("Token ne contient pas de 'sub' (user_id)")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalid: missing user identifier",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"Token validé pour user_id: {user_id}")
        
    except ExpiredSignatureError:
        logger.warning("Token expiré (ExpiredSignatureError)")
        debug_info = verify_token_expiry(token)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Token has expired",
                "expired_at": debug_info.get("exp_date"),
                "current_time": debug_info.get("current_time"),
                "message": "Please login again to get a new token"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.error(f"JWT Error: {e}")
        logger.error(f"Token problématique: {token[:50]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        # Re-lever les HTTPException sans les modifier
        raise
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la validation du token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Récupérer l'utilisateur en base de données
    try:
        user = crud.get_user_by_id(db, user_id=int(user_id))
        if user is None:
            logger.error(f"Utilisateur non trouvé en base: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.info(f"Utilisateur authentifié: {user.id}")
        return user
        
    except ValueError:
        logger.error(f"user_id invalide (ne peut pas être converti en int): {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'utilisateur: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error",
        )

def create_refresh_token(user_id: int) -> str:
    """Crée un refresh token avec une durée de vie plus longue"""
    expire = datetime.utcnow() + timedelta(days=7)  # 7 jours pour le refresh token
    to_encode = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_refresh_token(token: str) -> int:
    """Vérifie un refresh token et retourne l'user_id"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        
        return int(user_id)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

# Fonction utilitaire pour déboguer les tokens
def debug_token_info(token: str) -> dict:
    """Fonction utilitaire pour déboguer un token"""
    try:
        # Décoder sans vérification pour debug
        payload = jwt.decode(token, options={"verify_signature": False})
        
        info = {
            "payload": payload,
            "token_length": len(token),
            "algorithm_used": payload.get("alg", "Non spécifié"),
        }
        
        # Vérifier l'expiration
        exp_timestamp = payload.get('exp')
        if exp_timestamp:
            exp_date = datetime.utcfromtimestamp(exp_timestamp)
            current_time = datetime.utcnow()
            info.update({
                "expiration_date": exp_date.isoformat(),
                "current_time": current_time.isoformat(),
                "is_expired": current_time > exp_date,
                "time_until_expiry_seconds": (exp_date - current_time).total_seconds()
            })
        
        return info
    except Exception as e:
        return {"error": str(e)}