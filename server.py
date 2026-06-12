import os
import json
import base64
import hashlib
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# --- CONFIG ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"
FILE_PATH = "clicker_save_db.json"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

ATTACK_COOLDOWN_SEC = 3600   # 1 hour between attacks on same target
ATTACK_STEAL_PERCENT = 0.10  # 10% of victim's bitcoins
BASE_FIREWALL_REDUCTION = 0.05  # Each firewall level reduces theft by 5%

# --- DB FUNCTIONS ---
def get_db():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    resp = requests.get(GITHUB_API_URL, headers=headers)
    if resp.status_code == 200:
        content_b64 = resp.json()["content"]
        decoded = base64.b64decode(content_b64).decode("utf-8")
        return json.loads(decoded), resp.json().get("sha")
    return {"players": {}, "accounts": {}, "attacks": {}}, None

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


# --- DASHBOARD HTML ---
DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<title>HACKER MASTER // Live Network</title>
<style>
    body { background: #000; color: #0f0; font-family: 'Courier New', monospace; padding: 30px; }
    .frame { max-width: 750px; margin: auto; border: 2px solid #0f0; padding: 25px; box-shadow: 0 0 20px #0f04; }
    h1 { text-align: center; text-shadow: 0 0 10px #0f0; }
    table { width: 100%; border-collapse: collapse; margin-top: 15px; }
    th, td { padding: 10px; border-bottom: 1px solid #030; text-align: left; }
    th { color: #f0f; }
    .btc { color: #0ff; font-weight: bold; }
    .rank { color: #ff0; }
</style>
</head>
<body>
<div class="frame">
<h1>>> HACKER MASTER NETWORK <<</h1>
<table>
<thead><tr><th>Rank</th><th>Hacker</th><th>Bitcoins ₿</th><th>Firewall</th></tr></thead>
<tbody id="board"><tr><td colspan="4" style="text-align:center;">Loading network...</td></tr></tbody>
</table>
</div>
<script>
function refresh() {
    fetch('/api/scores').then(r=>r.json()).then(data => {
        const t = document.getElementById("board");
        t.innerHTML = "";
        let list = Object.keys(data.players).map(n => ({name:n, ...data.players[n]}));
        list.sort((a,b) => (b.money||0) - (a.money||0));
        if(list.length===0) {
            t.innerHTML = "<tr><td colspan='4' style='text-align:center;'>No hackers detected.</td></tr>";
            return;
        }
        list.forEach((p,i) => {
            const fw = (p.upgrade_levels && p.upgrade_levels.firewall) || 0;
            t.innerHTML += `<tr><td class="rank">#${i+1}</td><td><b>${p.name}</b></td><td class="btc">₿ ${Number(p.money).toLocaleString()}</td><td>LVL ${fw}</td></tr>`;
        });
    });
}
refresh();
setInterval(refresh, 4000);
</script>
</body>
</html>"""


# --- HTTP HANDLER ---
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

        # --- REGISTER ---
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
            db["players"][u] = {"money": 0, "upgrade_levels": {}}
            save_db(db, sha)
            return self.send_json({"success": True, "msg": f"Hacker '{u}' deployed."})

        # --- LOGIN ---
        elif self.path == "/api/login":
            u = payload.get("username", "").strip().lower()
            p = payload.get("password", "").strip()
            db, _ = get_db()
            acc = db.get("accounts", {}).get(u)
            if not acc:
                return self.send_json({"success": False, "error": "No such hacker."}, 400)
            if acc["password_hash"] != hash_pwd(p):
                return self.send_json({"success": False, "error": "Access denied."}, 400)
            pdata = db.get("players", {}).get(u, {"money": 0, "upgrade_levels": {}})
            return self.send_json({
                "success": True,
                "money": pdata.get("money", 0),
                "upgrade_levels": pdata.get("upgrade_levels", {})
            })

        # --- SAVE ---
        elif self.path == "/api/save":
            u = payload.get("player", "").strip().lower()
            if not u:
                return self.send_json({"success": False, "error": "Missing handle."}, 400)
            db, sha = get_db()
            db.setdefault("players", {})
            db["players"][u] = {
                "money": int(payload.get("money", 0)),
                "upgrade_levels": payload.get("upgrade_levels", {})
            }
            save_db(db, sha)
            return self.send_json({"success": True})

        # --- LOAD ---
        elif self.path == "/api/load":
            u = payload.get("player", "").strip().lower()
            db, _ = get_db()
            pdata = db.get("players", {}).get(u, {"money": 0, "upgrade_levels": {}})
            return self.send_json({
                "success": True,
                "money": pdata.get("money", 0),
                "upgrade_levels": pdata.get("upgrade_levels", {})
            })

        # --- ATTACK ANOTHER PLAYER ---
        elif self.path == "/api/attack":
            attacker = payload.get("attacker", "").strip().lower()
            target = payload.get("target", "").strip().lower()
            if not attacker or not target:
                return self.send_json({"success": False, "error": "Missing attacker/target."}, 400)
            if attacker == target:
                return self.send_json({"success": False, "error": "You can't hack yourself."}, 400)
            
            db, sha = get_db()
            db.setdefault("attacks", {})
            db.setdefault("players", {})
            
            if target not in db["players"]:
                return self.send_json({"success": False, "error": "Target not found."}, 400)
            
            # Cooldown check
            attack_key = f"{attacker}->{target}"
            now = int(time.time())
            last_attack = db["attacks"].get(attack_key, 0)
            elapsed = now - last_attack
            if elapsed < ATTACK_COOLDOWN_SEC:
                remaining = ATTACK_COOLDOWN_SEC - elapsed
                mins = remaining // 60
                return self.send_json({
                    "success": False,
                    "error": f"Target on cooldown. Try again in {mins} min."
                }, 400)
            
            # Calculate stolen amount
            victim_data = db["players"][target]
            victim_money = victim_data.get("money", 0)
            victim_fw = victim_data.get("upgrade_levels", {}).get("firewall", 0)
            
            steal_rate = max(0.01, ATTACK_STEAL_PERCENT - (victim_fw * BASE_FIREWALL_REDUCTION))
            stolen = int(victim_money * steal_rate)
            
            if stolen <= 0:
                stolen = 1 if victim_money > 0 else 0
            
            # Apply
            db["players"][target]["money"] = max(0, victim_money - stolen)
            attacker_data = db["players"].setdefault(attacker, {"money": 0, "upgrade_levels": {}})
            attacker_data["money"] = attacker_data.get("money", 0) + stolen
            
            db["attacks"][attack_key] = now
            save_db(db, sha)
            
            return self.send_json({
                "success": True,
                "stolen": stolen,
                "new_money": attacker_data["money"],
                "steal_rate": steal_rate
            })

        else:
            self.send_json({"success": False, "error": "Unknown endpoint."}, 404)


def run():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Hacker Master backend live on :{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
