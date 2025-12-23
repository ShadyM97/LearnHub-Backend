import os

def read_var(path, var_name):
    try:
        with open(path, 'r') as f:
            for line in f:
                if line.startswith(var_name):
                    return line.split('=', 1)[1].strip()
    except FileNotFoundError:
        return "File Not Found"
    return "Var Not Found"

backend_url = read_var(r"c:\Users\Shady\Desktop\learnhub-backend\.env", "SUPABASE_URL")
frontend_url = read_var(r"c:\Users\Shady\Desktop\learnhub\.env.local", "NEXT_PUBLIC_SUPABASE_URL")

report = f"""
Backend SUPABASE_URL: {backend_url}
Frontend NEXT_PUBLIC_SUPABASE_URL: {frontend_url}
Match: {backend_url == frontend_url}
"""

with open("env_comparison.txt", "w") as f:
    f.write(report)
