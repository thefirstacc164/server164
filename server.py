import os
import json
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import requests

# --- SYSTEM CONFIGURATION ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"
FILE_PATH = "email_system_db.json"  # This file will act as our permanent database on GitHub

GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

def get_db_from_github():
    """Fetches the latest email data file from the GitHub repository."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    resp = requests.get(GITHUB_API_URL, headers=headers)
    if resp.status_code == 200:
        content_b64 = resp.json()["content"]
        decoded_json = base64.b64decode(content_b64).decode("utf-8")
        return json.loads(decoded_json), resp.json().get("sha")
    # If the file doesn't exist yet, return a clean blueprint structure
    return {"users": {}, "messages": []}, None

def save_db_to_github(db_data, current_sha=None):
    """Commits the modified database state back into the GitHub repository."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    
    # If SHA wasn't passed, try to fetch it instantly to prevent conflict errors
    if not current_sha:
        get_resp = requests.get(GITHUB_API_URL, headers=headers)
        if get_resp.status_code == 200:
            current_sha = get_resp.json().get("sha")

    json_string = json.dumps(db_data, indent=4)
    encoded_content = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    
    payload = {
        "message": "System Database Sync Update",
        "content": encoded_content
    }
    if current_sha:
        payload["sha"] = current_sha

    put_resp = requests.put(GITHUB_API_URL, headers=headers, json=payload)
    return put_resp.status_code in [200, 201]

def hash_password(password):
    """Simple helper to securely hash user credentials instead of storing plain text."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# --- HTML TEMPLATE UI LAYOUTS ---
BASE_CSS = """
<style>
    body { font-family: monospace; background-color: #121212; color: #00ff00; padding: 20px; max-width: 600px; margin: auto; }
    h1, h2 { color: #ffffff; border-bottom: 1px solid #00ff00; padding-bottom: 5px; }
    input, textarea, button { background-color: #222; color: #00ff00; border: 1px solid #00ff00; padding: 8px; width: 100%; margin-bottom: 15px; font-family: monospace; }
    button:hover { background-color: #00ff00; color: #000; cursor: pointer; font-weight: bold; }
    .msg-box { border: 1px dashed #00ff00; padding: 10px; margin-bottom: 10px; background-color: #1a1a1a; }
    .error { color: #ff0000; font-weight: bold; }
    .success { color: #00ff00; font-weight: bold; }
    .nav { margin-bottom: 20px; }
    .nav a { color: #ffffff; text-decoration: none; border: 1px solid #ffffff; padding: 4px 8px; margin-right: 5px; }
    .nav a:hover { background-color: #ffffff; color: #000; }
</style>
"""

INDEX_HTML = f"""<!DOCTYPE html><html><head>{BASE_CSS}<title>NetMail 164</title></head>
<body>
    <h1>📟 NetMail 164 Server Node</h1>
    <p>Welcome to the custom, decentralized network email portal.</p>
    <div style="margin-top: 30px;">
        <a href="/login-page"><button>Log Into System Inbox</button></a>
        <a href="/register-page"><button style="background-color: #333;">Create New Network Address</button></a>
    </div>
</body></html>"""

REGISTER_HTML = f"""<!DOCTYPE html><html><head>{BASE_CSS}<title>Register - NetMail 164</title></head>
<body>
    <h1>Create Network Address</h1>
    <form action="/register" method="POST">
        <label>Choose Email Address Prefix (e.g., alex):</label>
        <input type="text" name="username" placeholder="username" required>
        <label>Create Secure Access Token Password:</label>
        <input type="password" name="password" placeholder="password" required>
        <button type="submit">Initialize Address Node</button>
    </form>
    <p><a href="/" style="color:#fff;">Back to Home</a></p>
</body></html>"""

LOGIN_HTML = f"""<!DOCTYPE html><html><head>{BASE_CSS}<title>Login - NetMail 164</title></head>
<body>
    <h1>System Access Authentication</h1>
    <form action="/login" method="POST">
        <label>Network Email Address Prefix:</label>
        <input type="text" name="username" placeholder="username" required>
        <label>Secure Access Token Password:</label>
        <input type="password" name="password" placeholder="password" required>
        <button type="submit">Decrypt & Open Inbox</button>
    </form>
    <p><a href="/" style="color:#fff;">Back to Home</a></p>
</body></html>"""

# --- SERVER NETWORKING CORE ---
class EmailSystemHandler(BaseHTTPRequestHandler):

    def send_html(self, html_content, status_code=200):
        self.send_response(status_code)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def do_GET(self):
        # Clean paths to match simply
        path = self.path.split('?')[0]
        
        if path == "/" or path == "":
            self.send_html(INDEX_HTML)
        elif path == "/register-page":
            self.send_html(REGISTER_HTML)
        elif path == "/login-page":
            self.send_html(LOGIN_HTML)
        elif path == "/ping":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"KeepAlive Active")
        else:
            self.send_html(f"<!DOCTYPE html><html><body><h1>404 File Not Found</h1></body></html>", 404)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        parsed_fields = urllib.parse.parse_qs(post_data)

        # Helper to extract clean form strings safely
        def get_field(field_name):
            return parsed_fields.get(field_name, [""])[0].strip().lower()

        path = self.path

        if path == "/register":
            username = get_field("username")
            password = get_field("password")

            if not username or not password:
                self.send_html(f"<html><head>{BASE_CSS}</head><body><p class='error'>Error: Invalid Fields.</p><a href='/register-page'>Try again</a></body></html>")
                return

            db, sha = get_db_from_github()
            
            if username in db["users"]:
                self.send_html(f"<html><head>{BASE_CSS}</head><body><p class='error'>Error: Username Address already taken.</p><a href='/register-page'>Try again</a></body></html>")
            else:
                # Add user to structural store with hashed password authentication
                db["users"][username] = hash_password(password)
                save_db_to_github(db, sha)
                self.send_html(f"<html><head>{BASE_CSS}</head><body><p class='success'>Success! Account initialized.</p><a href='/login-page'>Log in here</a></body></html>")

        elif path == "/login" or path == "/dashboard":
            username = get_field("username")
            password = get_field("password")

            db, _ = get_db_from_github()
            
            # Authenticate credentials
            if username in db["users"] and db["users"][username] == hash_password(password):
                # Build custom dynamic account profile page showing user's specific mailboxes
                user_mail_view = f"<!DOCTYPE html><html><head>{BASE_CSS}<title>Dashboard</title></head><body>"
                user_mail_view += f"<div class='nav'><span>Logged in as: <b>{username}@netmail164</b></span> | <a href='/'>Log Out</a></div>"
                user_mail_view += "<h2>📥 Incoming Secure Messages</h2>"
                
                user_messages = [m for m in db["messages"] if m["to"] == username]
                
                if not user_messages:
                    user_mail_view += "<p>No packets found inside mailbox directory.</p>"
                else:
                    for msg in reversed(user_messages):
                        user_mail_view += f"""
                        <div class='msg-box'>
                            <b>From:</b> {msg['from']}@netmail164<br>
                            <b>Content:</b><br><p style='color:#ffffff;'>{msg['body']}</p>
                        </div>"""
                
                user_mail_view += f"""
                <h2 style='margin-top:40px;'>📤 Transmit New Data Packet</h2>
                <form action="/send-message" method="POST">
                    <input type="hidden" name="username" value="{username}">
                    <input type="hidden" name="password" value="{password}">
                    <label>Destination Address Prefix (e.g., bob):</label>
                    <input type="text" name="recipient" required>
                    <label>Encrypted Payload Data:</label>
                    <textarea name="message_body" rows="4" required></textarea>
                    <button type="submit">Broadcast Transmission</button>
                </form>
                </body></html>"""
                
                self.send_html(user_mail_view)
            else:
                self.send_html(f"<html><head>{BASE_CSS}</head><body><p class='error'>Access Denied: Bad authentication keys.</p><a href='/login-page'>Back to login</a></body></html>")

        elif path == "/send-message":
            username = get_field("username")
            password = get_field("password")
            recipient = get_field("recipient")
            message_body = parsed_fields.get("message_body", [""])[0].strip() # Keep case sensitivity for content texts

            db, sha = get_db_from_github()

            # Re-authenticate to ensure form isn't hijacked
            if username in db["users"] and db["users"][username] == hash_password(password):
                if recipient not in db["users"]:
                    self.send_html(f"<html><head>{BASE_CSS}</head><body><p class='error'>Transmission Error: Destination address node does not exist.</p><form action='/login' method='POST'><input type='hidden' name='username' value='{username}'><input type='hidden' name='password' value='{password}'><button type='submit'>Return to Panel</button></form></body></html>")
                else:
                    # Append message structure to tracking array block
                    new_msg_packet = {
                        "from": username,
                        "to": recipient,
                        "body": message_body
                    }
                    db["messages"].append(new_msg_packet)
                    save_db_to_github(db, sha)
                    
                    # Direct user straight back into panel dashboard cleanly
                    self.send_html(f"<html><head>{BASE_CSS}</head><body><p class='success'>Transmission Complete!</p><form action='/login' method='POST'><input type='hidden' name='username' value='{username}'><input type='hidden' name='password' value='{password}'><button type='submit'>Back to Inbox</button></form></body></html>")
            else:
                self.send_html("Unauthorized Post Action", 401)

def run():
    port = int(os.environ.get("PORT", 10000))
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, EmailSystemHandler)
    print(f"Email system engine online on target port {port}...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
