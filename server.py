import os
import json
import base64
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

# --- CONFIGURATION FROM ENVIRONMENT VARIABLES ---
# We fetch these securely from Render's panel so your token is never leaked in public code
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"  # You can change this to a private repo name later for security
FILE_PATH = "player_saves.json"

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

def save_to_github(data_dict):
    """Sends an API request to GitHub to commit the updated save file."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    
    # Check if the file already exists to get its unique SHA identifier
    get_resp = requests.get(GITHUB_API_URL, headers=headers)
    sha = None
    if get_resp.status_code == 200:
        sha = get_resp.json().get("sha")
        
    # Format and Base64 encode the string data for the GitHub API
    json_string = json.dumps(data_dict, indent=4)
    encoded_content = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": "Server Auto-Save Update",
        "content": encoded_content
    }
    if sha:
        payload["sha"] = sha

    put_resp = requests.put(GITHUB_API_URL, headers=headers, json=payload)
    return put_resp.status_code in [200, 201]

def load_from_github():
    """Fetches the current save file from GitHub."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    resp = requests.get(GITHUB_API_URL, headers=headers)
    if resp.status_code == 200:
        file_content_b64 = resp.json()["content"]
        decoded_json = base64.b64decode(file_content_b64).decode("utf-8")
        return json.loads(decoded_json)
    return {}

class GameServerHandler(BaseHTTPRequestHandler):
    """Handles incoming network traffic from your game clients or ping bots."""
    
    def do_GET(self):
        """Handles reading data or keeping the server awake."""
        if self.path == "/ping":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Server is awake and active!")
            
        elif self.path == "/load":
            # Endpoint for your game to request player data
            data = load_from_github()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode("utf-8"))
            
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        """Handles incoming player saves."""
        if self.path == "/save":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                incoming_data = json.loads(post_data.decode("utf-8"))
                # Merge incoming data with the existing save file
                current_data = load_from_github()
                current_data.update(incoming_data)
                
                success = save_to_github(current_data)
                if success:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Data successfully backed up to GitHub!")
                else:
                    self.send_response(500)
                    self.end_headers()
            except Exception as e:
                self.send_response(400)
                self.end_headers()

def run():
    # Render automatically sets the PORT environment variable to 10000
    port = int(os.environ.get("PORT", 10000))
    # Binding to 0.0.0.0 makes the server accessible to the public internet
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, GameServerHandler)
    print(f"Game server seamlessly running 24/7 on port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
