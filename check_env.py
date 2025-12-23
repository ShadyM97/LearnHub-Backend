import os

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
frontend = read_env(r"c:\Users\Shady\Desktop\learnhub\.env.local")

print("Backend URL:", backend.get("SUPABASE_URL") if backend else "Not found")
print("Frontend URL:", frontend.get("NEXT_PUBLIC_SUPABASE_URL") if frontend else "Not found")

if backend and frontend:
    b_url = backend.get("SUPABASE_URL", "").strip()
    f_url = frontend.get("NEXT_PUBLIC_SUPABASE_URL", "").strip()
    if b_url == f_url:
        print("MATCH: URLs are identical.")
    else:
        print("MISMATCH: URLs are different!")
