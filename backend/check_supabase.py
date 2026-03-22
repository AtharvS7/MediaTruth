import os
import requests
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}"
}
print(f"Checking Supabase OpenAPI Schema at: {url}/rest/v1/")
try:
    resp = requests.get(f"{url}/rest/v1/", headers=headers, timeout=10)
    if resp.status_code == 200:
        schema = resp.json()
        tables = [path.strip("/") for path in schema.get("paths", {}).keys() if path.startswith("/")]
        print("[+] Successfully connected to Supabase!")
        print("[+] Available tables in schema:")
        for t in tables:
            if t != "":
                print(f"  - {t}")
    else:
        print("[-] Failed to fetch schema:", resp.status_code, resp.text)
except Exception as e:
    print("[-] Error connecting:", e)
