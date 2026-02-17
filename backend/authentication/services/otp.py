import os
import secrets
import bcrypt
import logging
import json
import redis
from datetime import datetime, timedelta
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import ssl

try:
    # Fix for SSL: CERTIFICATE_VERIFY_FAILED on some local environments
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

logger = logging.getLogger(__name__)

# --- Redis Configuration ---
REDIS_HOST = getattr(settings, "REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
REDIS_PORT = int(getattr(settings, "REDIS_PORT", os.getenv("REDIS_PORT", 6379)))
REDIS_DB = int(getattr(settings, "REDIS_DB", os.getenv("REDIS_DB", 0)))

_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=1
        )
        client.ping()
        _redis_client = client
        logger.info("✅ Redis connection established for OTP service")
        return _redis_client
    except Exception as e:
        logger.warning(f"[!] Redis not available ({e}). Falling back to in-memory MOCK_REDIS.")
        return None

MOCK_REDIS = {}

def generate_otp():
    """Generate 6-digit secure OTP"""
    return str(secrets.randbelow(900000) + 100000)

def send_otp_email(email: str, otp: str):
    """Send OTP email via SendGrid"""
    sg_api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("FROM_EMAIL")
    
    logger.info(f"Attempting to send OTP email to {email}")
    print(f"\n[DEBUG] Attempting to send OTP email to: {email}")
    
    if not sg_api_key or "your_sendgrid_api_key" in sg_api_key:
        error_msg = f"[CONFIG ERROR] Missing SENDGRID_API_KEY. OTP for {email} is {otp}"
        logger.error(error_msg)
        print(f"\n❌ {error_msg}")
        return False
    
    if not from_email:
        logger.error(f"[CONFIG ERROR] Missing FROM_EMAIL. OTP for {email} is {otp}")
        return False

    message = Mail(
        from_email=from_email,
        to_emails=email,
        subject='Verify your email - MLR Validator',
        html_content=f'''
            <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
                <h2 style="color: #111827;">Verify Your Email</h2>
                <p>Your verification code is:</p>
                <div style="background: #f3f4f6; padding: 20px; text-align: center; border-radius: 8px; font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #2563eb;">
                    {otp}
                </div>
                <p>This code will expire in 5 minutes.</p>
                <p style="color: #6b7280; font-size: 14px;">If you didn't request this, please ignore this email.</p>
            </div>
        '''
    )
    
    try:
        sg = SendGridAPIClient(sg_api_key)
        response = sg.send(message)
        logger.info(f"SendGrid Status: {response.status_code}")
        print(f"✅ SendGrid SUCCESS - Status: {response.status_code}")
        logger.info(f"OTP email sent successfully to {email}")
        return True
    except Exception as e:
        logger.error(f"SendGrid error for {email}: {str(e)}")
        # If it's a 4xx error, it might be an unverified sender
        if hasattr(e, 'body'):
            logger.error(f"SendGrid Error Body: {e.body}")
        
        # We return True here so the UI doesn't crash, but we've logged the error
        logger.info(f"[EMERGENCY BACKUP] OTP for {email} is {otp}")
        return False

def store_otp(email: str, otp: str):
    """Store hashed OTP with 5-min expiry"""
    hashed = bcrypt.hashpw(otp.encode(), bcrypt.gensalt()).decode()
    now = datetime.now()
    
    client = get_redis_client()
    if client:
        otp_data = {
            "hash": hashed,
            "expiry": (now + timedelta(minutes=5)).isoformat(),
            "attempts": 0
        }
        client.setex(f"otp:{email}", 300, json.dumps(otp_data))
        client.setex(f"otp_resend:{email}", 60, "true")
        logger.info(f"OTP stored in Redis for {email}")
    else:
        MOCK_REDIS[f"otp:{email}"] = {
            "hash": hashed,
            "expiry": now + timedelta(minutes=5),
            "attempts": 0
        }
        MOCK_REDIS[f"otp_resend:{email}"] = {
            "expiry": now + timedelta(seconds=60)
        }
        logger.info(f"OTP stored in memory for {email}")

def verify_otp_hash(email: str, provided_otp: str):
    """Verify provided OTP against hashed version"""
    now = datetime.now()
    client = get_redis_client()
    
    if client:
        raw_data = client.get(f"otp:{email}")
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
        if client: client.delete(f"otp:{email}")
        else: MOCK_REDIS.pop(f"otp:{email}", None)
        return False, "OTP expired"
    
    if data["attempts"] >= 3:
        return False, "Too many failed attempts"
    
    if bcrypt.checkpw(provided_otp.encode(), data["hash"].encode()):
        if client:
            client.delete(f"otp:{email}")
            client.delete(f"otp_resend:{email}")
        else:
            MOCK_REDIS.pop(f"otp:{email}", None)
            MOCK_REDIS.pop(f"otp_resend:{email}", None)
        return True, "Verified"
    else:
        data["attempts"] += 1
        if client:
            ttl = client.ttl(f"otp:{email}")
            if ttl > 0:
                client.setex(f"otp:{email}", ttl, json.dumps(data))
        return False, "Invalid OTP"

def check_resend_cooldown(email: str):
    """Returns True if user is still in cooldown"""
    client = get_redis_client()
    if client:
        return client.exists(f"otp_resend:{email}") > 0
    
    now = datetime.now()
    cooldown = MOCK_REDIS.get(f"otp_resend:{email}")
    if cooldown and now < cooldown["expiry"]:
        return True
    return False
