import os
import secrets
import bcrypt
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from dotenv import load_dotenv
import logging
import ssl
import certifi

import redis
import json

load_dotenv()
logger = logging.getLogger(__name__)

# Fix SSL certificate verification for Windows
os.environ['SSL_CERT_FILE'] = certifi.where()

# --- Redis Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Initialize Redis client
try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=2
    )
    # Test connection
    redis_client.ping()
    logger.info("✅ Redis connection established for OTP service")
    USE_REDIS = True
except Exception as e:
    logger.warning(f"[!] Redis not available ({e}). Falling back to in-memory MOCK_REDIS.")
    USE_REDIS = False
    MOCK_REDIS = {}

def generate_otp():
    """Step 5: Generate 6-digit secure OTP"""
    return str(secrets.randbelow(900000) + 100000)

def store_otp(email: str, otp: str):
    """Step 6: Store hashed OTP with 5-min expiry"""
    hashed = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    now = datetime.now()
    
    if USE_REDIS:
        # Use Redis for storage
        otp_data = {
            "hash": hashed,
            "expiry": (now + timedelta(minutes=5)).isoformat(),
            "attempts": 0
        }
        redis_client.setex(f"otp:{email}", 300, json.dumps(otp_data))
        redis_client.setex(f"otp_resend:{email}", 60, "true")
        logger.info(f"OTP stored in Redis for {email}")
    else:
        # Fallback to Mock Redis
        MOCK_REDIS[f"otp:{email}"] = {
            "hash": hashed,
            "expiry": now + timedelta(minutes=5),
            "attempts": 0
        }
        MOCK_REDIS[f"otp_resend:{email}"] = {
            "expiry": now + timedelta(seconds=60)
        }
        logger.info(f"OTP stored in memory for {email}")

def send_otp_email(email: str, otp: str):
    """Step 7: Send OTP email via SendGrid"""
    sg_api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL")
    
    if not sg_api_key or sg_api_key == "your_sendgrid_api_key_here":
        logger.error("[X] SendGrid API key not configured in .env file")
        logger.info(f"[TEST] TESTING MODE: OTP for {email} is {otp}")
        return True  # Allow testing without SendGrid
    
    if not from_email or from_email == "no-reply@yourdomain.com":
        logger.error("[X] FROM_EMAIL not configured in .env file")
        logger.info(f"[TEST] TESTING MODE: OTP for {email} is {otp}")
        return True

    message = Mail(
        from_email=from_email,
        to_emails=email,
        subject='Verify your email - MLR Validator',
        html_content=f'''
            <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px; background: #f9fafb;">
                <div style="background: white; border-radius: 16px; padding: 40px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #111827; margin: 0; font-size: 28px; font-weight: 700;">Verify Your Email</h1>
                        <p style="color: #6b7280; margin: 10px 0 0 0; font-size: 15px;">MLR Validator Account Verification</p>
                    </div>
                    
                    <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 20px 0;">Hello,</p>
                    <p style="color: #374151; font-size: 16px; line-height: 1.6; margin: 0 0 30px 0;">
                        Use the following verification code to complete your account setup. This code will expire in <strong>5 minutes</strong>.
                    </p>
                    
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 12px; margin: 30px 0;">
                        <div style="background: white; display: inline-block; padding: 20px 40px; border-radius: 8px;">
                            <span style="font-size: 36px; font-weight: 700; letter-spacing: 0.3em; color: #2563eb; font-family: 'Courier New', monospace;">{otp}</span>
                        </div>
                    </div>
                    
                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 8px; margin: 30px 0;">
                        <p style="color: #92400e; margin: 0; font-size: 14px;">
                            <strong>Security Notice:</strong> Never share this code with anyone. Our team will never ask for your verification code.
                        </p>
                    </div>
                    
                    <p style="color: #9ca3af; font-size: 13px; text-align: center; margin: 30px 0 0 0; line-height: 1.6;">
                        If you didn't request this code, please ignore this email or contact support if you have concerns.
                    </p>
                </div>
                
                <p style="color: #9ca3af; font-size: 12px; text-align: center; margin: 20px 0 0 0;">
                    © 2026 MLR Validator. All rights reserved.
                </p>
            </div>
        '''
    )
    
    try:
        sg = SendGridAPIClient(sg_api_key)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            logger.info(f"[OK] OTP email sent successfully to {email}")
            return True
        else:
            logger.error(f"[X] SendGrid returned status {response.status_code}")
            logger.info(f"[FALLBACK] OTP for {email} is {otp}")
            return True
            
    except Exception as e:
        logger.error(f"[X] SendGrid error: {str(e)}")
        logger.info(f"[FALLBACK] OTP for {email} is {otp}")
        return True

def verify_otp_hash(email: str, provided_otp: str):
    """Verify provided OTP against hashed version"""
    now = datetime.now()
    
    if USE_REDIS:
        raw_data = redis_client.get(f"otp:{email}")
        if not raw_data:
            return False, "OTP not found or expired"
        data = json.loads(raw_data)
        expiry = datetime.fromisoformat(data["expiry"])
    else:
        data = MOCK_REDIS.get(f"otp:{email}")
        if not data:
            return False, "OTP not found"
        expiry = data["expiry"]
    
    if now > expiry:
        if not USE_REDIS: del MOCK_REDIS[f"otp:{email}"]
        else: redis_client.delete(f"otp:{email}")
        return False, "OTP expired"
    
    if data["attempts"] >= 3:
        return False, "Too many failed attempts"
    
    if bcrypt.checkpw(provided_otp.encode(), data["hash"].encode()):
        # Cleanup on success
        if USE_REDIS:
            redis_client.delete(f"otp:{email}")
            redis_client.delete(f"otp_resend:{email}")
        else:
            if f"otp:{email}" in MOCK_REDIS: del MOCK_REDIS[f"otp:{email}"]
            if f"otp_resend:{email}" in MOCK_REDIS: del MOCK_REDIS[f"otp_resend:{email}"]
        return True, "Verified"
    else:
        # Increment attempts
        data["attempts"] += 1
        if USE_REDIS:
            ttl = redis_client.ttl(f"otp:{email}")
            if ttl > 0:
                redis_client.setex(f"otp:{email}", ttl, json.dumps(data))
        return False, "Invalid OTP"

def check_resend_cooldown(email: str):
    """Returns True if user is still in cooldown"""
    if USE_REDIS:
        return redis_client.exists(f"otp_resend:{email}") > 0
    
    now = datetime.now()
    cooldown = MOCK_REDIS.get(f"otp_resend:{email}")
    if cooldown and now < cooldown["expiry"]:
        return True
    return False
