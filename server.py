import os
import json
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import requests

# --- DATABASE CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"
FILE_PATH = "clicker_save_db.json"

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

def get_db_from_github():
    """Retrieves the global player registry from GitHub."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    resp = requests.get(GITHUB_API_URL, headers=headers)
    if resp.status_code == 200:
        content_b64 = resp.json()["content"]
        decoded_json = base64.b64decode(content_b64).decode("utf-8")
        return json.loads(decoded_json), resp.json().get("sha")
    # Base template if the file doesn't exist
    return {"players": {}, "accounts": {}}, None

def save_db_to_github(db_data, current_sha=None):
    """Commits updated data back to GitHub."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    if not current_sha:
        get_resp = requests.get(GITHUB_API_URL, headers=headers)
        if get_resp.status_code == 200:
            current_sha = get_resp.json().get("sha")

    json_string = json.dumps(db_data, indent=4)
    encoded_content = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": "Cloud Save Engine Delta Sync",
        "content": encoded_content
    }
    if current_sha:
        payload["sha"] = current_sha

    put_resp = requests.put(GITHUB_API_URL, headers=headers, json=payload)
    return put_resp.status_code in [200, 201]

def hash_password(password):
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# --- LEADERBOARD HTML ---
DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>NetClicker // Hub Matrix</title>
    <style>
        body { background-color: #0d0e15; color: #00ffcc; font-family: 'Consolas', monospace; padding: 30px; }
        .main-frame { max-width: 700px; margin: 0 auto; background: #131520; border: 2px solid #00ffcc; border-radius: 8px; padding: 25px; box-shadow: 0 0 15px rgba(0,255,204,0.2); }
        h1 { text-align: center; color: #ffffff; text-shadow: 0 0 8px #00ffcc; margin-bottom: 25px; font-size: 1.6rem; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #22263a; }
        th { color: #ff007f; font-size: 0.9rem; text-transform: uppercase; }
        td { color: #ffffff; }
        .cash-amount { color: #00ffcc; font-weight: bold; }
        .rank { color: #ff007f; font-weight: bold; }
    </style>
</head>
<body>
    <div class="main-frame">
        <h1>NETCLICKER CENTRAL LEADERBOARD</h1>
        <table>
            <thead>
                <tr>
                    <th style="width: 15%">Rank</th>
                    <th style="width: 50%">Player Handle</th>
                    <th style="width: 35%">Total Cash Balance</th>
                </tr>
            </thead>
            <tbody id="leaderboard-body">
                <tr><td colspan="3" style="text-align:center; color:#888;">Synchronizing game matrix telemetry...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        function refreshLeaderboard() {
            fetch('/api/scores')
            .then(res => res.json())
            .then(data => {
                const tbody = document.getElementById("leaderboard-body");
                tbody.innerHTML = "";
                let playerList = Object.keys(data.players).map(name => ({name: name, ...data.players[name]}));
                playerList.sort((a, b) => (b.money || 0) - (a.money || 0));
                if(playerList.length === 0) {
                    tbody.innerHTML = "<tr><td colspan='3' style='text-align:center; color:#888;'>No active user nodes registered.</td></tr>";
                    return;
                }
                playerList.forEach((player, index) => {
                    tbody.innerHTML += `
                        <tr>
                            <td class="rank">#${index + 1}</td>
                            <td><b>${player.name}</b></td>
                            <td class="cash-amount">$${Number(player.money).toLocaleString()}</td>
                        </tr>
                    `;
                });
            });
        }
        refreshLeaderboard();
        setInterval(refreshLeaderboard, 4000);
    </script>
</body>
</html>"""

# --- HTTP HANDLER ---
class GodotBackendHandler(BaseHTTPRequestHandler):

    def send_json(self, data_dict, status=200):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data_dict).encode("utf-8"))

    def do_OPTIONS(self):
        """Handles browser CORS preflight."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))

        elif self.path == "/api/scores":
            db, _ = get_db_from_github()
            self.send_json(db)

        elif self.path == "/ping":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Backend Ready")

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            payload = json.loads(post_data)
        except:
            return self.send_json({"success": False, "error": "Invalid JSON"}, 400)

        # --- ACCOUNT CREATION ---
        if self.path == "/api/register":
            username = payload.get("username", "").strip().lower()
            password = payload.get("password", "").strip()
            
            if not username or not password:
                return self.send_json({"success": False, "error": "Username and password required."}, 400)
            if len(username) < 3:
                return self.send_json({"success": False, "error": "Username must be at least 3 characters."}, 400)
            if len(password) < 4:
                return self.send_json({"success": False, "error": "Password must be at least 4 characters."}, 400)
            
            db, sha = get_db_from_github()
            
            if "accounts" not in db:
                db["accounts"] = {}
            if "players" not in db:
                db["players"] = {}
            
            if username in db["accounts"]:
                return self.send_json({"success": False, "error": "Username already exists!"}, 400)
            
            db["accounts"][username] = {"password_hash": hash_password(password)}
            db["players"][username] = {"money": 0, "upgrade_levels": {}}
            save_db_to_github(db, sha)
            return self.send_json({"success": True, "msg": f"Account '{username}' created!"})

        # --- LOGIN ---
        elif self.path == "/api/login":
            username = payload.get("username", "").strip().lower()
            password = payload.get("password", "").strip()
            
            if not username or not password:
                return self.send_json({"success": False, "error": "Username and password required."}, 400)
            
            db, sha = get_db_from_github()
            
            if "accounts" not in db:
                db["accounts"] = {}
            
            account = db["accounts"].get(username)
            if not account:
                return self.send_json({"success": False, "error": "Account not found."}, 400)
            
            if account["password_hash"] != hash_password(password):
                return self.send_json({"success": False, "error": "Wrong password."}, 400)
            
            player_data = db["players"].get(username, {"money": 0, "upgrade_levels": {}})
            return self.send_json({
                "success": True,
                "msg": "Login successful!",
                "money": player_data.get("money", 0),
                "upgrade_levels": player_data.get("upgrade_levels", {})
            })

        # --- SAVE ---
        elif self.path == "/api/save":
            player = payload.get("player", "").strip().lower()
            if not player:
                return self.send_json({"success": False, "error": "Missing player profile identifier."}, 400)
            
            db, sha = get_db_from_github()
            if "players" not in db:
                db["players"] = {}
            
            incoming_money = int(payload.get("money", 0))
            incoming_upgrades = payload.get("upgrade_levels", {})
            
            db["players"][player] = {
                "money": incoming_money,
                "upgrade_levels": incoming_upgrades
            }
            save_db_to_github(db, sha)
            return self.send_json({"success": True, "msg": f"Progress compiled for {player}."})

        # --- LOAD ---
        elif self.path == "/api/load":
            player = payload.get("player", "").strip().lower()
            if not player:
                return self.send_json({"success": False, "error": "Missing player profile identifier."}, 400)
            
            db, sha = get_db_from_github()
            player_data = db["players"].get(player, {"money": 0, "upgrade_levels": {}})
            return self.send_json({
                "success": True,
                "money": player_data.get("money", 0),
                "upgrade_levels": player_data.get("upgrade_levels", {})
            })

        else:
            self.send_json({"success": False, "error": "Unknown endpoint."}, 404)

def run():
    port = int(os.environ.get("PORT", 10000))
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, GodotBackendHandler)
    print(f"Godot Cloud Core active on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
