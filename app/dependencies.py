import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import HTTPException # Added this import for HTTPException

load_dotenv()

# Initialize Supabase client
# We initialize it once here to be reused
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
)

# Initialize Supabase Admin client (Service Role)
try:
    supabase_admin: Client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
except Exception as e:
    print(f"Warning: Could not initialize Supabase Admin client: {e}")
    supabase_admin = None
def get_supabase() -> Client:
    return supabase

def get_supabase_admin() -> Client:
    if not supabase_admin:
        raise HTTPException(
            status_code=500, 
            detail="Server configuration error: Service role key missing"
        )
    return supabase_admin
