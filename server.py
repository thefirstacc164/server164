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

# PVP CONFIG
ATTACK_COOLDOWN_SAME_TARGET = 3600  # 1 hour
ATTACK_COOLDOWN_GLOBAL = 30  # 30 sec between any attacks
SHIELD_DURATION_PER_LEVEL = 1800  # 30 min per shield level
BASE_STEAL_AMOUNT = 10000  # Base HC stolen per attack
STEAL_PER_LEVEL = 10000  # Extra HC per satellite_hack level
MAX_STEAL = 100000  # Hard cap
FIREWALL_REDUCTION = 0.20  # 20% reduction per firewall level


def get_db():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=15)
    except Exception as e:
        print(f"[get_db] Network error: {e}")
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}}, None
    
    if resp.status_code == 404:
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}}, None
    if resp.status_code != 200:
        print(f"[get_db] Status {resp.status_code}")
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}}, None
    
    try:
        gh_data = resp.json()
        sha = gh_data.get("sha")
        content_b64 = gh_data.get("content", "")
        if not content_b64:
            return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}}, sha
        decoded = base64.b64decode(content_b64).decode("utf-8").strip()
        if not decoded:
            return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}}, sha
        db = json.loads(decoded)
        if not isinstance(db, dict):
            db = {}
        db.setdefault("players", {})
        db.setdefault("accounts", {})
        db.setdefault("attacks", {})
        db.setdefault("shields", {})
        return db, sha
    except Exception as e:
        print(f"[get_db] Parse error: {e}")
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}}, None


def save_db(db_data, current_sha=None):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    if not current_sha:
        try:
            r = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
            if r.status_code == 200:
                current_sha = r.json().get("sha")
        except:
            pass
    json_string = json.dumps(db_data, indent=2)
    encoded = base64.b64encode(json_string.encode("utf-8")).decode("utf-8")
    payload = {"message": "Hacker Master save", "content": encoded}
    if current_sha:
        payload["sha"] = current_sha
    try:
        r = requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=15)
        return r.status_code in [200, 201]
    except Exception as e:
        print(f"[save_db] Error: {e}")
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
    .shield { color: #ff0; }
</style>
</head>
<body>
<div class="frame">
<h1>>> HACKER MASTER NETWORK <<</h1>
<table>
<thead><tr><th>Rank</th><th>Handle</th><th>Level</th><th>Bitcoins</th><th>Status</th></tr></thead>
<tbody id="board"><tr><td colspan="5" style="text-align:center;">Loading...</td></tr></tbody>
</table>
</div>
<script>
function refresh() {
    fetch('/api/scores').then(r=>r.json()).then(data => {
        const t = document.getElementById("board");
        t.innerHTML = "";
        let list = Object.keys(data.players).map(n => ({name:n, ...data.players[n]}));
        list.sort((a,b) => (b.level||1) - (a.level||1) || (b.money||0) - (a.money||0));
        if(list.length===0) { t.innerHTML = "<tr><td colspan='5' style='text-align:center;'>No hackers.</td></tr>"; return; }
        const now = Math.floor(Date.now()/1000);
        const shields = data.shields || {};
        list.forEach((p,i) => {
            let status = "Active";
            const shield = shields[p.name];
            if (shield && shield.expire > now) {
                const mins = Math.floor((shield.expire - now) / 60);
                status = `🛡 SHIELDED (${mins}m)`;
            }
            t.innerHTML += `<tr><td class="rank">#${i+1}</td><td><b>${p.name}</b></td><td class="lvl">LVL ${p.level||1}</td><td class="btc">${Number(p.money||0).toLocaleString()}</td><td class="shield">${status}</td></tr>`;
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
            print(f"[send_json] {e}")

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
            print(f"[do_GET] {e}")

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length).decode('utf-8') if length > 0 else "{}"
            payload = json.loads(raw)
        except Exception as e:
            return self.send_json({"success": False, "error": "Bad JSON"}, 400)

        try:
            # === REGISTER ===
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
                    return self.send_json({"success": False, "error": "DB save failed."}, 500)
                return self.send_json({"success": True, "msg": f"Hacker '{u}' registered."})

            # === LOGIN ===
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

            # === SAVE ===
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
                    return self.send_json({"success": False, "error": "Save failed."}, 500)
                return self.send_json({"success": True})

            # === LOAD ===
            elif self.path == "/api/load":
                u = payload.get("player", "").strip().lower()
                db, _ = get_db()
                pdata = db.get("players", {}).get(u, default_player())
                for k, v in default_player().items():
                    if k not in pdata:
                        pdata[k] = v
                return self.send_json({"success": True, "player": pdata})

            # === GET PVP TARGETS (list of attackable players) ===
            elif self.path == "/api/pvp_targets":
                u = payload.get("player", "").strip().lower()
                db, _ = get_db()
                now = int(time.time())
                shields = db.get("shields", {})
                
                targets = []
                for name, pdata in db.get("players", {}).items():
                    if name == u:  # Don't list yourself
                        continue
                    
                    # Check VPN cloak
                    gear = pdata.get("gear_levels", {})
                    has_vpn = int(gear.get("vpn_cloak", 0)) > 0
                    
                    # Check shield
                    shield_data = shields.get(name, {})
                    shielded = int(shield_data.get("expire", 0)) > now
                    
                    targets.append({
                        "name": name,
                        "level": pdata.get("level", 1),
                        "money": pdata.get("money", 0),
                        "shielded": shielded,
                        "cloaked": has_vpn
                    })
                
                # Sort by money descending
                targets.sort(key=lambda x: -x["money"])
                return self.send_json({"success": True, "targets": targets})

            # === ATTACK PLAYER ===
            elif self.path == "/api/attack":
                attacker = payload.get("attacker", "").strip().lower()
                target = payload.get("target", "").strip().lower()
                
                if not attacker or not target:
                    return self.send_json({"success": False, "error": "Missing player names."}, 400)
                if attacker == target:
                    return self.send_json({"success": False, "error": "You can't hack yourself!"}, 400)
                
                db, sha = get_db()
                now = int(time.time())
                
                # Check attacker exists and has satellite_hack
                attacker_data = db["players"].get(attacker)
                if not attacker_data:
                    return self.send_json({"success": False, "error": "Attacker not found."}, 400)
                
                attacker_gear = attacker_data.get("gear_levels", {})
                sat_level = int(attacker_gear.get("satellite_hack", 0))
                if sat_level == 0:
                    return self.send_json({"success": False, "error": "You need Satellite Hack from the shop!"}, 400)
                
                # Check target exists
                target_data = db["players"].get(target)
                if not target_data:
                    return self.send_json({"success": False, "error": "Target not found."}, 400)
                
                # Check global cooldown
                attacks = db.get("attacks", {})
                last_global = attacks.get(f"{attacker}__last", 0)
                if now - last_global < ATTACK_COOLDOWN_GLOBAL:
                    remaining = ATTACK_COOLDOWN_GLOBAL - (now - last_global)
                    return self.send_json({"success": False, "error": f"Wait {remaining}s before next attack."}, 400)
                
                # Check same-target cooldown
                last_attack = attacks.get(f"{attacker}->{target}", 0)
                if now - last_attack < ATTACK_COOLDOWN_SAME_TARGET:
                    remaining_min = (ATTACK_COOLDOWN_SAME_TARGET - (now - last_attack)) // 60
                    return self.send_json({"success": False, "error": f"This target on cooldown for {remaining_min}m."}, 400)
                
                # Check target's shield
                shields = db.get("shields", {})
                shield_data = shields.get(target, {})
                if int(shield_data.get("expire", 0)) > now:
                    mins = (int(shield_data.get("expire", 0)) - now) // 60
                    # Counter-hack check (target's counter)
                    target_counter = int(target_data.get("gear_levels", {}).get("counter_hack", 0))
                    if target_counter > 0:
                        # Counter-hack steals back!
                        counter_amount = min(5000 * target_counter, attacker_data.get("money", 0))
                        attacker_data["money"] = max(0, attacker_data.get("money", 0) - counter_amount)
                        target_data["money"] = target_data.get("money", 0) + counter_amount
                        db["players"][attacker] = attacker_data
                        db["players"][target] = target_data
                        save_db(db, sha)
                        return self.send_json({
                            "success": False,
                            "error": f"🛡 {target} is shielded! Their counter-hack stole {counter_amount} HC from you!",
                            "counter_loss": counter_amount
                        })
                    return self.send_json({"success": False, "error": f"🛡 Target shielded for {mins}m."}, 400)
                
                # Check target's VPN cloak (should have been filtered earlier but double-check)
                target_vpn = int(target_data.get("gear_levels", {}).get("vpn_cloak", 0))
                if target_vpn > 0 and randf_chance(target_vpn * 0.2):
                    return self.send_json({"success": False, "error": "🌫 Target's VPN Cloak hid them — attack failed!"}, 400)
                
                # CALCULATE STEAL AMOUNT
                # Base: 10K per satellite_hack level
                steal_amount = min(MAX_STEAL, BASE_STEAL_AMOUNT + (sat_level - 1) * STEAL_PER_LEVEL)
                
                # Apply firewall reduction
                target_firewall = int(target_data.get("gear_levels", {}).get("firewall", 0))
                reduction = min(0.95, FIREWALL_REDUCTION * target_firewall)
                steal_amount = int(steal_amount * (1.0 - reduction))
                
                # Cap to target's actual money
                steal_amount = min(steal_amount, target_data.get("money", 0))
                if steal_amount <= 0:
                    return self.send_json({"success": False, "error": "Target has no HackCoins to steal!"}, 400)
                
                # Apply theft
                target_data["money"] = max(0, target_data.get("money", 0) - steal_amount)
                attacker_data["money"] = attacker_data.get("money", 0) + steal_amount
                
                # Counter-hack check (target steals back partially)
                counter_amount = 0
                target_counter = int(target_data.get("gear_levels", {}).get("counter_hack", 0))
                if target_counter > 0:
                    counter_amount = min(2000 * target_counter, attacker_data.get("money", 0))
                    if counter_amount > 0:
                        attacker_data["money"] = max(0, attacker_data.get("money", 0) - counter_amount)
                        target_data["money"] = target_data.get("money", 0) + counter_amount
                
                # Save attacks
                attacks[f"{attacker}__last"] = now
                attacks[f"{attacker}->{target}"] = now
                db["attacks"] = attacks
                db["players"][attacker] = attacker_data
                db["players"][target] = target_data
                
                if not save_db(db, sha):
                    return self.send_json({"success": False, "error": "Save failed."}, 500)
                
                return self.send_json({
                    "success": True,
                    "stolen": steal_amount,
                    "counter_loss": counter_amount,
                    "new_money": attacker_data["money"],
                    "target_firewall": target_firewall,
                    "target_counter": target_counter > 0
                })

            # === ACTIVATE SHIELD ===
            elif self.path == "/api/shield":
                u = payload.get("player", "").strip().lower()
                db, sha = get_db()
                pdata = db["players"].get(u)
                if not pdata:
                    return self.send_json({"success": False, "error": "Player not found."}, 400)
                
                shield_level = int(pdata.get("gear_levels", {}).get("proxy_shield", 0))
                if shield_level == 0:
                    return self.send_json({"success": False, "error": "You don't have Proxy Shield!"}, 400)
                
                now = int(time.time())
                shields = db.get("shields", {})
                existing = shields.get(u, {})
                if int(existing.get("expire", 0)) > now:
                    mins = (int(existing.get("expire", 0)) - now) // 60
                    return self.send_json({"success": False, "error": f"Shield already active for {mins}m."}, 400)
                
                duration = SHIELD_DURATION_PER_LEVEL * shield_level
                shields[u] = {"expire": now + duration}
                db["shields"] = shields
                save_db(db, sha)
                return self.send_json({
                    "success": True,
                    "duration_minutes": duration // 60,
                    "msg": f"Shield active for {duration // 60} minutes!"
                })

            else:
                self.send_json({"success": False, "error": "Unknown endpoint."}, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[do_POST] {e}")
            self.send_json({"success": False, "error": f"Server error: {str(e)[:100]}"}, 500)


def randf_chance(probability):
    import random
    return random.random() < probability


def run():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Hacker Master backend live on :{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
