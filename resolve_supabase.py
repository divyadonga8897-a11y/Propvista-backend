import urllib.request
import json

def resolve(hostname, record_type):
    url = f"https://dns.google/resolve?name={hostname}&type={record_type}"
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if "Answer" in data:
                return [ans["data"] for ans in data["Answer"]]
    except Exception as e:
        print(f"Error resolving {hostname} ({record_type}): {e}")
    return []

print("Resolving db.svdcrgmpqoicxlfqmxxc.supabase.co...")
print("AAAA records:", resolve("db.svdcrgmpqoicxlfqmxxc.supabase.co", "AAAA"))
print("A records:", resolve("db.svdcrgmpqoicxlfqmxxc.supabase.co", "A"))
