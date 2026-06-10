import os
import json
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import requests

# --- DATABASE CONFIGULATION ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"
FILE_PATH = "clicker_save_db.json"

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

def get_db_from_github():
    """Retrieves the global player registry from your GitHub repository."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    resp = requests.get(GITHUB_API_URL, headers=headers)
    if resp.status_code == 200:
        content_b64 = resp.json()["content"]
        decoded_json = base64.b64decode(content_b64).decode("utf-8")
        return json.loads(decoded_json), resp.json().get("sha")
    # Base template if the file doesn't exist yet
    return {"players": {}}, None

def save_db_to_github(db_data, current_sha=None):
    """Commits updated player save data directly back to GitHub."""
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

# --- LEADERBOARD & STATUS MONITOR ---
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
        <h1>📊 NETCLICKER CENTRAL LEADERBOARD</h1>
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
                
                // Sort players by cash descending
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
        setInterval(refreshLeaderboard, 4000); // Live poll updates every 4 seconds
    </script>
</body>
</html>
"""

# --- HTTP TRANSLATION CORE ---
class GodotBackendHandler(BaseHTTPRequestHandler):

    def send_json(self, data_dict, status=200):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        # CORS headers allow your Godot game to talk to this server even if run as an HTML5 web game
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data_dict).encode("utf-8"))

    def do_OPTIONS(self):
        """Handles browser security handshakes for web-based games."""
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
        
        # --- API ENDPOINT: GODOT CLIENT SAVE / LOAD ---
        if self.path == "/api/save" or self.path == "/api/load":
            try:
                payload = json.loads(post_data)
                player = payload.get("player", "").strip().lower()
                
                if not player:
                    return self.send_json({"success": False, "error": "Missing player profile identifier."}, 400)
                
                db, sha = get_db_from_github()
                
                # HANDLER 1: FETCH SAVED DATA VALUE
                if self.path == "/api/load":
                    player_data = db["players"].get(player, {"money": 0})
                    return self.send_json({"success": True, "money": player_data.get("money", 0)})
                
                # HANDLER 2: SAVE DATA VALUE FROM GAME CLICKER
                elif self.path == "/api/save":
                    incoming_money = int(payload.get("money", 0))
                    
                    # Store data structure
                    db["players"][player] = {"money": incoming_money}
                    save_db_to_github(db, sha)
                    
                    return self.send_json({"success": True, "msg": f"Progress compiled for {player}."})
                    
            except Exception as e:
                self.send_json({"success": False, "error": f"Internal matrix disruption: {str(e)}"}, 400)

def run():
    port = int(os.environ.get("PORT", 10000))
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, GodotBackendHandler)
    print(f"Godot Cloud Core active on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
