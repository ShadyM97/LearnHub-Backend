import os
import requests
import json

def read_env(path):
    d = {}
    try:
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    d[k] = v
    except FileNotFoundError:
        return None
    return d

backend = read_env(r"c:\Users\Shady\Desktop\learnhub-backend\.env")
url = backend.get("SUPABASE_URL") if backend else None

output = []

if url:
    jwks_url = f"{url}/auth/v1/.well-known/jwks.json"
    output.append(f"Fetching from: {jwks_url}")
    try:
        res = requests.get(jwks_url)
        if res.status_code == 200:
            keys = res.json().get("keys", [])
            kids = [k.get("kid") for k in keys]
            output.append(f"Found {len(keys)} keys.")
            output.append(f"KIDs: {', '.join(kids)}")
            
            target_kid = "R1dWxhG0rDzYWclk"
            if target_kid in kids:
                output.append(f"SUCCESS: Target KID {target_kid} FOUND in JWKS.")
            else:
                output.append(f"FAILURE: Target KID {target_kid} NOT FOUND in JWKS.")
        else:
            output.append(f"Error fetching JWKS: {res.status_code}")
    except Exception as e:
        output.append(f"Exception fetching JWKS: {e}")
else:
    output.append("No SUPABASE_URL found in backend .env")

with open("jwks_debug.txt", "w") as f:
    f.write("\n".join(output))
