from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict
import requests
import time
import logging
from app.core.config import settings
from fastapi import WebSocket
from starlette.status import WS_1008_POLICY_VIOLATION
logger = logging.getLogger(__name__)

# Azure AD Settings
TENANT_ID = settings.AZURE_TENANT_ID
CLIENT_ID = settings.AZURE_CLIENT_ID

# Fixed based on token you shared
ISSUER = f"https://sts.windows.net/{TENANT_ID}/"
JWKS_URL = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
AUDIENCE = f"api://{CLIENT_ID}"

http_bearer = HTTPBearer()

# JWKS caching
JWKS_CACHE = None
LAST_FETCH_TIME = 0
CACHE_DURATION = 3600  # 1 hour

def get_openid_keys():
    global JWKS_CACHE, LAST_FETCH_TIME
    if JWKS_CACHE and time.time() - LAST_FETCH_TIME < CACHE_DURATION:
        return JWKS_CACHE
    try:
        logger.info(f"Fetching JWKS from: {JWKS_URL}")
        response = requests.get(JWKS_URL, timeout=10)
        response.raise_for_status()
        JWKS_CACHE = response.json()
        LAST_FETCH_TIME = time.time()
        return JWKS_CACHE
    except Exception as e:
        logger.error(f"JWKS fetch failed: {str(e)}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch JWKS keys: {str(e)}"
        )

def verify_token(token: str):
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=403, detail="Missing key ID in token header")
        
        jwks = get_openid_keys()
        
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER
        )
        # Extract only the required fields
        user_info = {
            "UserEmail": payload.get("email"),
            "UserName": payload.get("name"),
            "ObjectId": payload.get("oid"),
            "UserType": payload.get("user_type") or "User"
        }

        return user_info

    except JWTError as e:
        logger.error(f"JWT validation failed: {str(e)}")
        if "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="Token has expired")
        elif "audience" in str(e).lower() or "issuer" in str(e).lower():
            raise HTTPException(status_code=401, detail=f"Invalid claims: {str(e)}")
        else:
            raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")

def azure_ad_dependency(credentials: HTTPAuthorizationCredentials = Depends(http_bearer)):
    return verify_token(credentials.credentials)

async def websocket_auth(websocket: WebSocket):
    # Get token from query parameter instead of header
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=WS_1008_POLICY_VIOLATION)
        return None
    
    try:
        return verify_token(token)
    except HTTPException:
        await websocket.close(code=WS_1008_POLICY_VIOLATION)
        return None