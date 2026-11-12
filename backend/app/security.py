from datetime import datetime, timedelta, timezone
import secrets
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

password_hash = PasswordHash.recommended()

def encrypt(token):
    return Fernet(settings().token_key.encode()).encrypt(token.encode()).decode()

def decrypt(token):
    return Fernet(settings().token_key.encode()).decrypt(token.encode()).decode()

def issue(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, settings().jwt_secret, algorithm='HS256')

def current_user(request: Request, db: Session = Depends(get_db)):
    try:
        claims = jwt.decode(request.cookies.get('session', ''), settings().jwt_secret, algorithms=['HS256'])
        user = db.get(User, int(claims['sub']))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Inicia sesión')
    if not user or not user.active:
        raise HTTPException(401, 'Sesión no válida')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if request.headers.get('origin') != settings().frontend_origin:
            raise HTTPException(403, 'Origen no permitido')
        if not secrets.compare_digest(request.headers.get('x-csrf-token', ''), request.cookies.get('csrf', '-')):
            raise HTTPException(403, 'CSRF no válido')
    return user

def editor(user=Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Requiere rol administrador')
    return user

def admin(user=Depends(current_user)):
    if user.role != 'admin':
        raise HTTPException(403, 'Requiere rol administrador')
    return user
