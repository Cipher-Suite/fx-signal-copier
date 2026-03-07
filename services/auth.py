# fx/services/auth.py
"""
Authentication and encryption services
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64
import os
import logging
from sqlalchemy.orm import Session

from database.repositories import UserRepository
from config.settings import settings

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Handles encryption/decryption of sensitive data
    Uses Fernet (symmetric encryption) for MT5 passwords
    """
    
    def __init__(self):
        # Get encryption key from environment
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            # Generate a key if not provided (for development)
            # In production, this MUST be set in environment
            key = base64.urlsafe_b64encode(os.urandom(32))
            logger.warning("ENCRYPTION_KEY not set, using generated key. "
                          "This will cause issues in production!")
        else:
            key = key.encode()
        
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt sensitive data"""
        if not data:
            return ""
        encrypted = self.cipher.encrypt(data.encode())
        return encrypted.decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        if not encrypted_data:
            return ""
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return decrypted.decode()
    
    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Hash a password using PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        return key, salt
    
    @staticmethod
    def verify_password(password: str, key: bytes, salt: bytes) -> bool:
        """Verify a password against a hash"""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        try:
            kdf.verify(password.encode(), key)
            return True
        except Exception:
            return False


class AuthService:
    """
    Handles user authentication, API keys, and JWT tokens
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.user_repo = UserRepository(db_session)
        self.encryption = EncryptionService()
        self.jwt_secret = os.getenv("JWT_SECRET", secrets.token_hex(32))
        self.jwt_algorithm = "HS256"
    
    def verify_telegram_user(self, telegram_id: int, username: str) -> bool:
        """
        Verify if a Telegram user is authorized
        Returns True if user exists and is active
        """
        user = self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            logger.info(f"Unknown Telegram user attempted access: {telegram_id}")
            return False
        
        if not user.is_active or user.is_banned:
            logger.warning(f"Inactive/banned user attempted access: {telegram_id}")
            return False
        
        return True
    
    def create_api_key(self, user_id: int) -> Optional[str]:
        """
        Generate a new API key for a user
        """
        from database.repositories import SettingsRepository
        settings_repo = SettingsRepository(self.db)
        return settings_repo.generate_api_key(user_id)
    
    def validate_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """
        Validate an API key and return user info
        """
        from database.models import UserSettings, User
        
        settings = self.db.query(UserSettings).filter(
            UserSettings.api_key == api_key,
            UserSettings.api_enabled == True
        ).first()
        
        if not settings:
            return None
        
        user = self.db.query(User).filter(User.id == settings.user_id).first()
        if not user or not user.is_active or user.is_banned:
            return None
        
        return {
            'user_id': user.id,
            'telegram_id': user.telegram_id,
            'subscription_tier': user.subscription_tier
        }
    
    def generate_jwt(self, user_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """
        Generate a JWT token for a user
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        
        to_encode = {
            "user_id": user_id,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        return jwt.encode(to_encode, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a JWT token and return the payload
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
    
    def validate_mt5_credentials(self, account: str, password: str, server: str) -> Tuple[bool, str]:
        """
        Validate MT5 credentials by attempting connection
        This is a stub - actual validation happens in mt5_manager
        """
        # This will be called by MT5ConnectionManager
        # Returning True/False with message
        pass
    
    def encrypt_mt5_password(self, password: str) -> str:
        """Encrypt MT5 password for storage"""
        return self.encryption.encrypt(password)
    
    def decrypt_mt5_password(self, encrypted: str) -> str:
        """Decrypt MT5 password for use"""
        return self.encryption.decrypt(encrypted)
    
    def generate_csrf_token(self) -> str:
        """Generate a CSRF token for web forms"""
        return secrets.token_urlsafe(32)
    
    def verify_hmac(self, secret: str, data: str, signature: str) -> bool:
        """Verify HMAC signature for webhooks"""
        expected = hmac.new(
            secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)