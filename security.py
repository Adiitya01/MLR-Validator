from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import os

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
# from passlib.context import CryptContext
# from datetime import datetime, timedelta
# from typing import Optional
# import jwt
# import os

# # Configure bcrypt with proper settings to handle passwords safely
# pwd_context = CryptContext(
#     schemes=["bcrypt"],
#     deprecated="auto",
#     bcrypt__rounds=12,  # Default bcrypt rounds
#     bcrypt__ident="2b"  # Use 2b variant for better compatibility
# )

# SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours

# def hash_password(password: str) -> str:
#     """Hash a password using bcrypt"""
#     # Bcrypt has a 72-byte limit, truncate if necessary
#     if len(password.encode('utf-8')) > 72:
#         password = password[:72]
#     return pwd_context.hash(password)

# def verify_password(password: str, hashed: str) -> bool:
#     """Verify a password against its hash"""
#     # Apply same truncation for consistency
#     if len(password.encode('utf-8')) > 72:
#         password = password[:72]
#     return pwd_context.verify(password, hashed)

# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
#     """Create JWT access token"""
#     to_encode = data.copy()
    
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# def decode_token(token: str) -> dict:
#     """Decode JWT token"""
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except jwt.ExpiredSignatureError:
#         return None
#     except jwt.InvalidTokenError:
#         return None



import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import Optional
import jwt
import os

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60  # 24 hours
BCRYPT_ROUNDS = 12


def _prehash_password(password: str) -> str:
    """
    Pre-hash password using SHA-256 to avoid bcrypt 72-byte limit.
    
    This is the production-safe solution:
    - SHA-256 produces fixed 64-char output (always < 72 bytes)
    - No data loss from truncation
    - Prevents password collision attacks
    - Industry standard approach
    
    Flow: User Password → SHA-256 → bcrypt (safe)
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    """
    Hash password securely using SHA-256 + bcrypt.
    
    Args:
        password: Plain text password from user
        
    Returns:
        Bcrypt hash (safe to store in database)
    """
    prehashed = _prehash_password(password)
    # Use bcrypt directly to avoid passlib's password length validation
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(prehashed.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:

    """
    Verify password against stored hash.
    
    Args:
        password: Plain text password to verify
        hashed: Stored bcrypt hash from database
        
    Returns:
        True if password matches, False otherwise
    """
    prehashed = _prehash_password(password)
    # Use bcrypt directly to avoid passlib's validation
    return bcrypt.checkpw(prehashed.encode('utf-8'), hashed.encode('utf-8'))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

