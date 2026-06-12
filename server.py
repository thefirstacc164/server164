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
FILE_PATH = "clicker_save_db.json"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"


def get_db():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    resp = requests.get(GITHUB_API_URL, headers=headers)
    if resp.status_code == 200:
        content_b64 = resp.json()["content"]
        decoded = base64.b64decode(content_b64).decode("utf-8")
        return json.loads(decoded), resp.json().get("sha")
    return {"players": {}, "accounts": {}}, None

def save_db(db_data, current_sha=None):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    if not current_sha:
        get_resp = requests.get(GITHUB_API_URL, headers=headers)
        if get_resp.status_code == 200:
            current_sha = get_resp.json().get("sha")
    json_string = json.dumps(db_data, indent=4)
    encoded = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    payload = {"message": "Hacker Master Sync", "content": encoded}
    if current_sha:
        payload["sha"] = current_sha
    put_resp = requests.put(GITHUB_API_URL, headers=headers, json=payload)
    return put_resp.status_code in [200, 201]

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
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
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
            self.end_headers()
            self.wfile.write(b"OK")

    def do_POST(self):
        try:
            length = int(self.headers['Content-Length'])
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except:
            return self.send_json({"success": False, "error": "Bad JSON"}, 400)

        if self.path == "/api/register":
            u = payload.get("username", "").strip().lower()
            p = payload.get("password", "").strip()
            if len(u) < 3 or len(p) < 4:
                return self.send_json({"success": False, "error": "User >=3 chars, password >=4."}, 400)
            db, sha = get_db()
            db.setdefault("accounts", {})
            db.setdefault("players", {})
            if u in db["accounts"]:
                return self.send_json({"success": False, "error": "Handle already taken."}, 400)
            db["accounts"][u] = {"password_hash": hash_pwd(p)}
            db["players"][u] = default_player()
            save_db(db, sha)
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
            # Fill in missing fields from default
            for k, v in default_player().items():
                if k not in pdata:
                    pdata[k] = v
            return self.send_json({"success": True, "player": pdata})

        elif self.path == "/api/save":
            u = payload.get("player", "").strip().lower()
            if not u:
                return self.send_json({"success": False, "error": "Missing player."}, 400)
            db, sha = get_db()
            db.setdefault("players", {})
            existing = db["players"].get(u, default_player())
            existing["money"] = int(payload.get("money", existing.get("money", 0)))
            existing["xp"] = int(payload.get("xp", existing.get("xp", 0)))
            existing["level"] = int(payload.get("level", existing.get("level", 1)))
            existing["gear_levels"] = payload.get("gear_levels", existing.get("gear_levels", {}))
            existing["intro_done"] = bool(payload.get("intro_done", existing.get("intro_done", False)))
            existing["best_difficulty"] = payload.get("best_difficulty", existing.get("best_difficulty", "easy"))
            db["players"][u] = existing
            save_db(db, sha)
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


def run():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Hacker Master backend live on :{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
