from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
import httpx
import os
from typing import Dict, Any, Optional

security = HTTPBearer(auto_error=False)


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_AUDIENCE = "authenticated"
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

_jwks_cache = None


class AuthError(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


async def _get_jwks():
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache

    async with httpx.AsyncClient() as client:
        res = await client.get(JWKS_URL)
        res.raise_for_status()
        _jwks_cache = res.json()["keys"]
        return _jwks_cache



async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    token = credentials.credentials
    
    # DEBUG: Inspect the token format
    print(f"DEBUG: Received token length: {len(token)}")
    print(f"DEBUG: Token start: '{token[:10]}...'")
    print(f"DEBUG: Token end: '...{token[-10:]}'")
    
    # Check for JWT Secret for HS256 verification (common in self-hosted or older Supabase)
    jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

    try:
        # Strategy 1: Try HS256 if secret is available
        if jwt_secret:
            try:
                # Supabase secrets might be base64 encoded sometimes, but usually raw string in .env
                # If your secret is failing, check if it needs to be bytes.
                payload = jwt.decode(
                    token,
                    jwt_secret,
                    algorithms=["HS256"],
                    audience=SUPABASE_AUDIENCE,
                    options={"verify_exp": True},
                )
                if "sub" in payload:
                    return payload
            except JWTError as e:
                # If HS256 fails, we might fall through or just log it. 
                # If the project is configured for HS256, strictly only HS256 should work.
                print(f"DEBUG: HS256 verification failed: {e}")
                pass

        # Strategy 2: Try RS256 via JWKS (Default for new Supabase projects)
        unverified_header = jwt.get_unverified_header(token)
        jwks = await _get_jwks()

        key = next(
            (k for k in jwks if k["kid"] == unverified_header["kid"]), None
        )
        
        if not key:
             # Only a hard error if we also didn't have a secret to try, OR if we really expect RSA
             if not jwt_secret:
                print(f"DEBUG: Key not found in JWKS. Header kid: {unverified_header.get('kid')}")
                raise AuthError("Public key not found and no symmetric secret configured")
             else:
                # We already tried HS256 and failed, and now RS256 key is missing.
                raise AuthError("Authentication failed: No valid verification method found")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=SUPABASE_AUDIENCE,
            options={"verify_exp": True},
        )

    except (JWTError, StopIteration) as e:
        print(f"DEBUG: Auth Error: {str(e)}")
        raise AuthError(f"Invalid or expired authentication token: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Unexpected Auth Error: {str(e)}")
        raise AuthError(f"Authentication failed: {str(e)}")

    # Required claim
    if "sub" not in payload:
        print("DEBUG: 'sub' claim missing")
        raise AuthError("Invalid token payload")

    return payload

def require_role(role: str):
    async def dependency(user=Security(get_current_user)):
        from .dependencies import get_supabase_admin
        
        # Get user role from database since JWT doesn't include it
        # We need admin client to bypass RLS on users table
        user_id = user.get("sub")
        print(f"DEBUG: Checking role for user_id: {user_id}")
        
        try:
            db = get_supabase_admin()
        except HTTPException as e:
            print(f"DEBUG: Could not get admin client: {e.detail}")
            raise
        
        try:
            # Use execute() instead of single() to avoid exceptions when user doesn't exist
            user_res = db.from_("users").select("role").eq("id", user_id).execute()
            print(f"DEBUG: User query response: {user_res.data}")
            
            # Check if user exists in the database
            if not user_res.data:
                raise HTTPException(
                    status_code=403,
                    detail=f"User profile not found in database. Please complete your profile setup first."
                )
            
            user_role = user_res.data[0].get("role")
            print(f"DEBUG: User role: {user_role}, Required role: {role}")
            
            if user_role != role:
                raise HTTPException(
                    status_code=403, 
                    detail=f"Access denied. Required role: {role}, your role: {user_role}"
                )
            
            # Add role to user dict for convenience
            user["role"] = user_role
            return user
        except HTTPException:
            # Re-raise HTTP exceptions (like role mismatch)
            raise
        except Exception as e:
            print(f"DEBUG: Error fetching user role: {str(e)}")
            print(f"DEBUG: Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            # Provide more detailed error message
            error_detail = f"Could not verify user role. Error: {type(e).__name__}: {str(e)}"
            raise HTTPException(status_code=403, detail=error_detail)
    
    return dependency

async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[Dict[str, Any]]:
    if not credentials or not credentials.credentials:
        return None
    try:
        return await get_current_user(credentials)
    except Exception:
        return None

