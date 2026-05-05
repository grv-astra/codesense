import jwt
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import os

load_dotenv()

JWT_SECRET = os.getenv("JWT_TOKEN_SECRET", "nodeBetter+ImLe@theragicToThis")
JWT_ALGO = "HS256"
JWT_EXP_MINUTES = 60

def generate_token(payload):
    payload["iat"] =  datetime.now(timezone.utc)
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXP_MINUTES)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None