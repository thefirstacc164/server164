import os
import json
import base64
import hashlib
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"
FILE_PATH = "hacker_master_db.json"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"


def get_db():
    """Fetches the database from GitHub. Handles missing/empty/corrupt files gracefully."""
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=15)
    except Exception as e:
        print(f"[get_db] Network error: {e}")
        return {"players": {}, "accounts": {}}, None
    
    # File doesn't exist on GitHub yet
    if resp.status_code == 404:
        print("[get_db] File not found on GitHub, returning empty DB.")
        return {"players": {}, "accounts": {}}, None
    
    # Any other non-200 status
    if resp.status_code != 200:
        print(f"[get_db] GitHub returned status {resp.status_code}: {resp.text[:200]}")
        return {"players": {}, "accounts": {}}, None
    
    # Try to parse the response
    try:
        gh_data = resp.json()
        sha = gh_data.get("sha")
        content_b64 = gh_data.get("content", "")
        
        if not content_b64:
            print("[get_db] File is empty.")
            return {"players": {}, "accounts": {}}, sha
        
        decoded = base64.b64decode(content_b64).decode("utf-8").strip()
        
        if not decoded:
            print("[get_db] Decoded content is empty.")
            return {"players": {}, "accounts": {}}, sha
        
        # Parse the actual JSON
        try:
            db = json.loads(decoded)
            # Ensure structure
            if not isinstance(db, dict):
                db = {"players": {}, "accounts": {}}
            db.setdefault("players", {})
            db.setdefault("accounts", {})
            return db, sha
        except json.JSONDecodeError as e:
            print(f"[get_db] Corrupted JSON in DB file: {e}. Resetting.")
            return {"players": {}, "accounts": {}}, sha
            
    except Exception as e:
        print(f"[get_db] Unexpected error: {e}")
        return {"players": {}, "accounts": {}}, None


def save_db(db_data, current_sha=None):
    """Saves the database to GitHub. Returns True on success, False on failure."""
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    
    # Re-fetch sha if missing (file might have been created since)
    if not current_sha:
        try:
            get_resp = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            if get_resp.status_code == 200:
                current_sha = get_resp.json().get("sha")
        except Exception as e:
            print(f"[save_db] Sha fetch error: {e}")
    
    json_string = json.dumps(db_data, indent=2)
    encoded = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    payload = {"message": "Hacker Master save", "content": encoded}
    if current_sha:
        payload["sha"] = current_sha
    
    try:
        put_resp = requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=15)
        if put_resp.status_code not in [200, 201]:
            print(f"[save_db] GitHub PUT failed: {put_resp.status_code} - {put_resp.text[:200]}")
            return False
        print("[save_db] Save successful.")
        return True
    except Exception as e:
        print(f"[save_db] Network error: {e}")
        return False


def hash_pwd(p):
    return hashlib.sha256(p.encode("utf-8")).hexdigest()


def default_player():
    return {
        "money": 0,
        "xp": 0,
        "level": 1,
        "gear_levels": {},
        "intro_done": False,
        "best_difficulty": "easy"
    }


DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<title>HACKER MASTER // Live Network</title>
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 30px; }
    .frame { max-width: 800px; margin: auto; border: 2px solid #0f0; padding: 25px; box-shadow: 0 0 20px #0f04; }
    h1 { text-align: center; text-shadow: 0 0 10px #0f0; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { padding: 10px; border-bottom: 1px solid #030; text-align: left; }
    th { color: #f0f; }
    .btc { color: #0ff; font-weight: bold; }
    .lvl { color: #ff0; }
    .rank { color: #f55; }
</style>
</head>
<body>
<div class="frame">
<h1>>> HACKER MASTER NETWORK <<</h1>
<table>
<thead><tr><th>Rank</th><th>Handle</th><th>Level</th><th>Bitcoins</th></tr></thead>
<tbody id="board"><tr><td colspan="4" style="text-align:center;">Loading...</td></tr></tbody>
</table>
</div>
<script>
function refresh() {
    fetch('/api/scores').then(r=>r.json()).then(data => {
        const t = document.getElementById("board");
        t.innerHTML = "";
        let list = Object.keys(data.players).map(n => ({name:n, ...data.players[n]}));
        list.sort((a,b) => (b.level||1) - (a.level||1) || (b.money||0) - (a.money||0));
        if(list.length===0) { t.innerHTML = "<tr><td colspan='4' style='text-align:center;'>No hackers.</td></tr>"; return; }
        list.forEach((p,i) => {
            t.innerHTML += `<tr><td class="rank">#${i+1}</td><td><b>${p.name}</b></td><td class="lvl">LVL ${p.level||1}</td><td class="btc">${Number(p.money||0).toLocaleString()}</td></tr>`;
        });
    });
}
refresh();
setInterval(refresh, 4000);
</script>
</body>
</html>"""


class GameHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
        except Exception as e:
            print(f"[send_json] Error: {e}")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_GET(self):
        try:
            if self.path in ("/", ""):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            elif self.path == "/api/scores":
                db, _ = get_db()
                self.send_json(db)
            elif self.path == "/ping":
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_json({"error": "Unknown endpoint"}, 404)
        except Exception as e:
            print(f"[do_GET] Error: {e}")
            try:
                self.send_json({"success": False, "error": "Server error"}, 500)
            except:
                pass

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length).decode('utf-8') if length > 0 else "{}"
            payload = json.loads(raw)
        except Exception as e:
            print(f"[do_POST] Bad JSON: {e}")
            return self.send_json({"success": False, "error": "Bad JSON in request"}, 400)

        try:
            if self.path == "/api/register":
                u = payload.get("username", "").strip().lower()
                p = payload.get("password", "").strip()
                if len(u) < 3 or len(p) < 4:
                    return self.send_json({"success": False, "error": "User >=3 chars, password >=4."}, 400)
                db, sha = get_db()
                if u in db["accounts"]:
                    return self.send_json({"success": False, "error": "Handle already taken."}, 400)
                db["accounts"][u] = {"password_hash": hash_pwd(p)}
                db["players"][u] = default_player()
                if not save_db(db, sha):
                    return self.send_json({"success": False, "error": "DB save failed (check server logs)."}, 500)
                return self.send_json({"success": True, "msg": f"Hacker '{u}' registered."})

            elif self.path == "/api/login":
                u = payload.get("username", "").strip().lower()
                p = payload.get("password", "").strip()
                db, _ = get_db()
                acc = db.get("accounts", {}).get(u)
                if not acc:
                    return self.send_json({"success": False, "error": "Account not found."}, 400)
                if acc["password_hash"] != hash_pwd(p):
                    return self.send_json({"success": False, "error": "Wrong password."}, 400)
                pdata = db.get("players", {}).get(u, default_player())
                for k, v in default_player().items():
                    if k not in pdata:
                        pdata[k] = v
                return self.send_json({"success": True, "player": pdata})

            elif self.path == "/api/save":
                u = payload.get("player", "").strip().lower()
                if not u:
                    return self.send_json({"success": False, "error": "Missing player."}, 400)
                db, sha = get_db()
                existing = db["players"].get(u, default_player())
                existing["money"] = int(payload.get("money", existing.get("money", 0)))
                existing["xp"] = int(payload.get("xp", existing.get("xp", 0)))
                existing["level"] = int(payload.get("level", existing.get("level", 1)))
                existing["gear_levels"] = payload.get("gear_levels", existing.get("gear_levels", {}))
                existing["intro_done"] = bool(payload.get("intro_done", existing.get("intro_done", False)))
                existing["best_difficulty"] = payload.get("best_difficulty", existing.get("best_difficulty", "easy"))
                db["players"][u] = existing
                if not save_db(db, sha):
                    return self.send_json({"success": False, "error": "DB save failed."}, 500)
                return self.send_json({"success": True})

            elif self.path == "/api/load":
                u = payload.get("player", "").strip().lower()
                db, _ = get_db()
                pdata = db.get("players", {}).get(u, default_player())
                for k, v in default_player().items():
                    if k not in pdata:
                        pdata[k] = v
                return self.send_json({"success": True, "player": pdata})

            else:
                self.send_json({"success": False, "error": "Unknown endpoint."}, 404)
        except Exception as e:
            print(f"[do_POST] Unhandled error: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.send_json({"success": False, "error": f"Server crashed: {str(e)[:100]}"}, 500)
            except:
                pass


def run():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Hacker Master backend live on :{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
