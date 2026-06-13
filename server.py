import os
import json
import base64
import hashlib
import time
import math
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = "thefirstacc164"
REPO_NAME = "server164"
FILE_PATH = "hacker_master_db.json"
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{FILE_PATH}"

# PVP CONFIG
ATTACK_COOLDOWN_SAME_TARGET = 3600
ATTACK_COOLDOWN_GLOBAL = 30
SHIELD_DURATION_PER_LEVEL = 1800
BASE_STEAL_AMOUNT = 10000
STEAL_PER_LEVEL = 10000
MAX_STEAL = 100000
FIREWALL_REDUCTION = 0.20

# ANTI-CHEAT CONFIG
MAX_MONEY_GAIN_PER_SAVE = 10000000  # 10M
MAX_LEVEL_GAIN_PER_SAVE = 10
MAX_MONEY_CAP = 9000000000000000  # 9 quadrillion
MONEY_CORRECTION = 1000000  # Cap cheat gain to 1M
LEVEL_CORRECTION = 2  # Cap cheat level gain to 2


def get_db():
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=15)
    except Exception as e:
        print(f"[get_db] Network error: {e}")
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}, "cheaters": {}}, None
    
    if resp.status_code == 404:
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}, "cheaters": {}}, None
    if resp.status_code != 200:
        print(f"[get_db] Status {resp.status_code}")
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}, "cheaters": {}}, None
    
    try:
        gh_data = resp.json()
        sha = gh_data.get("sha")
        content_b64 = gh_data.get("content", "")
        if not content_b64:
            return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}, "cheaters": {}}, sha
        decoded = base64.b64decode(content_b64).decode("utf-8").strip()
        if not decoded:
            return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}, "cheaters": {}}, sha
        db = json.loads(decoded)
        if not isinstance(db, dict):
            db = {}
        db.setdefault("players", {})
        db.setdefault("accounts", {})
        db.setdefault("attacks", {})
        db.setdefault("shields", {})
        db.setdefault("cheaters", {})
        return db, sha
    except Exception as e:
        print(f"[get_db] Parse error: {e}")
        return {"players": {}, "accounts": {}, "attacks": {}, "shields": {}, "cheaters": {}}, None


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
        "usd": 0,
        "xp": 0,
        "level": 1,
        "gear_levels": {},
        "intro_done": False,
        "best_difficulty": "easy"
    }


def log_cheater(db, username, reason, original_money, attempted_money, corrected_money):
    db.setdefault("cheaters", {})
    if username not in db["cheaters"]:
        db["cheaters"][username] = []
    if not isinstance(db["cheaters"][username], list):
        db["cheaters"][username] = []
    db["cheaters"][username].append({
        "time": int(time.time()),
        "reason": reason,
        "original_money": original_money,
        "attempted_money": attempted_money,
        "corrected_money": corrected_money
    })
    # Keep only last 50 entries per cheater
    if len(db["cheaters"][username]) > 50:
        db["cheaters"][username] = db["cheaters"][username][-50:]
    print(f"[ANTICHEAT] {username}: {reason}")


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
    .cheater { color: #f55; font-weight: bold; }
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
        const cheaters = data.cheaters || {};
        list.forEach((p,i) => {
            let status = "Active";
            const shield = shields[p.name];
            if (shield && shield.expire > now) {
                const mins = Math.floor((shield.expire - now) / 60);
                status = `🛡 SHIELDED (${mins}m)`;
            }
            if (cheaters[p.name]) {
                status = `<span class="cheater">⚠ FLAGGED</span>`;
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
            elif self.path == "/api/crypto_prices":
                # Server-side price generation - deterministic per time window
                now = int(time.time())
                cryptos = {
                    "bytcoin": {"base": 100, "vol": 0.15},
                    "atharnium": {"base": 250, "vol": 0.25},
                    "tethar": {"base": 50, "vol": 0.08},
                    "dnb": {"base": 500, "vol": 0.35},
                    "solina": {"base": 175, "vol": 0.20}
                }
                prices = {}
                time_window = now // 15  # Changes every 15 seconds (all clients get same value)
                for cid, cfg in cryptos.items():
                    base = cfg["base"]
                    vol = cfg["vol"]
                    # Deterministic wave + noise based on time window + crypto name hash
                    wave = math.sin(time_window * 0.1 + (hash(cid) % 1000) * 0.01) * base * vol
                    noise_seed = (time_window * 7 + hash(cid)) % 10000
                    noise = ((noise_seed % 100) / 100.0 - 0.5) * base * vol * 0.5
                    price = max(1, int(base + wave + noise))
                    prices[cid] = price
                self.send_json({"prices": prices, "timestamp": now, "window": time_window})
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
        except Exception:
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

            # === SAVE (with anti-cheat) ===
            elif self.path == "/api/save":
                u = payload.get("player", "").strip().lower()
                if not u:
                    return self.send_json({"success": False, "error": "Missing player."}, 400)
                db, sha = get_db()
                existing = db["players"].get(u, default_player())
                
                incoming_money = int(payload.get("money", existing.get("money", 0)))
                incoming_level = int(payload.get("level", existing.get("level", 1)))
                
                # === ANTI-CHEAT ===
                old_money = existing.get("money", 0)
                old_level = existing.get("level", 1)
                
                money_diff = incoming_money - old_money
                level_diff = incoming_level - old_level
                
                cheater_flagged = False
                cheat_reasons = []
                attempted_money = incoming_money
                
                # Money jumped too much
                if money_diff > MAX_MONEY_GAIN_PER_SAVE and old_money > 0:
                    cheater_flagged = True
                    cheat_reasons.append(f"Money +{money_diff:,} (max {MAX_MONEY_GAIN_PER_SAVE:,})")
                    incoming_money = old_money + MONEY_CORRECTION
                
                # Level jumped too much
                if level_diff > MAX_LEVEL_GAIN_PER_SAVE and old_level > 1:
                    cheater_flagged = True
                    cheat_reasons.append(f"Level +{level_diff} (max {MAX_LEVEL_GAIN_PER_SAVE})")
                    incoming_level = old_level + LEVEL_CORRECTION
                
                # Money overflow
                if incoming_money > MAX_MONEY_CAP:
                    cheater_flagged = True
                    cheat_reasons.append(f"Money overflow ({incoming_money:,} > cap)")
                    incoming_money = MAX_MONEY_CAP
                
                # Negative money
                if incoming_money < 0:
                    cheater_flagged = True
                    cheat_reasons.append(f"Negative money ({incoming_money})")
                    incoming_money = 0
                
                if incoming_level < 1:
                    incoming_level = 1
                
                if cheater_flagged:
                    log_cheater(db, u, " | ".join(cheat_reasons), old_money, attempted_money, incoming_money)
                
                existing["money"] = incoming_money
                existing["xp"] = int(payload.get("xp", existing.get("xp", 0)))
                existing["level"] = incoming_level
                existing["gear_levels"] = payload.get("gear_levels", existing.get("gear_levels", {}))
                existing["usd"] = int(payload.get("usd", existing.get("usd", 0)))
                existing["intro_done"] = bool(payload.get("intro_done", existing.get("intro_done", False)))
                existing["best_difficulty"] = payload.get("best_difficulty", existing.get("best_difficulty", "easy"))
                db["players"][u] = existing
                if not save_db(db, sha):
                    return self.send_json({"success": False, "error": "Save failed."}, 500)
                return self.send_json({"success": True, "flagged": cheater_flagged, "corrected_money": incoming_money})

            # === LOAD ===
            elif self.path == "/api/load":
                u = payload.get("player", "").strip().lower()
                db, _ = get_db()
                pdata = db.get("players", {}).get(u, default_player())
                for k, v in default_player().items():
                    if k not in pdata:
                        pdata[k] = v
                return self.send_json({"success": True, "player": pdata})

            # === GET CHEATERS (admin) ===
            elif self.path == "/api/cheaters":
                db, _ = get_db()
                return self.send_json({"success": True, "cheaters": db.get("cheaters", {})})

            # === CLEAR CHEATER (admin) ===
            elif self.path == "/api/clear_cheater":
                target = payload.get("target", "").strip().lower()
                if not target:
                    return self.send_json({"success": False, "error": "No target."}, 400)
                db, sha = get_db()
                if target in db.get("cheaters", {}):
                    db["cheaters"].pop(target)
                    save_db(db, sha)
                return self.send_json({"success": True})

            # === BAN PLAYER (admin) ===
            elif self.path == "/api/ban_player":
                target = payload.get("target", "").strip().lower()
                if not target:
                    return self.send_json({"success": False, "error": "No target."}, 400)
                db, sha = get_db()
                if target in db.get("players", {}):
                    db["players"].pop(target)
                if target in db.get("accounts", {}):
                    db["accounts"].pop(target)
                save_db(db, sha)
                return self.send_json({"success": True, "msg": f"Banned {target}"})

            # === SET PLAYER MONEY (admin) ===
            elif self.path == "/api/admin_set_money":
                target = payload.get("target", "").strip().lower()
                amount = int(payload.get("amount", 0))
                if not target:
                    return self.send_json({"success": False, "error": "No target."}, 400)
                db, sha = get_db()
                if target not in db.get("players", {}):
                    return self.send_json({"success": False, "error": "Player not found."}, 400)
                if amount < 0: amount = 0
                if amount > MAX_MONEY_CAP: amount = MAX_MONEY_CAP
                db["players"][target]["money"] = amount
                save_db(db, sha)
                return self.send_json({"success": True})

            # === GET PVP TARGETS ===
            elif self.path == "/api/pvp_targets":
                u = payload.get("player", "").strip().lower()
                db, _ = get_db()
                now = int(time.time())
                shields = db.get("shields", {})
                
                targets = []
                for name, pdata in db.get("players", {}).items():
                    if name == u:
                        continue
                    gear = pdata.get("gear_levels", {})
                    has_vpn = int(gear.get("vpn_cloak", 0)) > 0
                    shield_data = shields.get(name, {})
                    shielded = int(shield_data.get("expire", 0)) > now
                    targets.append({
                        "name": name,
                        "level": pdata.get("level", 1),
                        "money": pdata.get("money", 0),
                        "shielded": shielded,
                        "cloaked": has_vpn
                    })
                targets.sort(key=lambda x: -x["money"])
                return self.send_json({"success": True, "targets": targets})

            # === ATTACK PLAYER ===
            elif self.path == "/api/attack":
                attacker = payload.get("attacker", "").strip().lower()
                target = payload.get("target", "").strip().lower()
                
                if not attacker or not target:
                    return self.send_json({"success": False, "error": "Missing names."}, 400)
                if attacker == target:
                    return self.send_json({"success": False, "error": "Can't hack yourself."}, 400)
                
                db, sha = get_db()
                now = int(time.time())
                
                attacker_data = db["players"].get(attacker)
                if not attacker_data:
                    return self.send_json({"success": False, "error": "Attacker not found."}, 400)
                
                attacker_gear = attacker_data.get("gear_levels", {})
                sat_level = int(attacker_gear.get("satellite_hack", 0))
                if sat_level == 0:
                    return self.send_json({"success": False, "error": "Need Satellite Hack!"}, 400)
                
                target_data = db["players"].get(target)
                if not target_data:
                    return self.send_json({"success": False, "error": "Target not found."}, 400)
                
                attacks = db.get("attacks", {})
                last_global = attacks.get(f"{attacker}__last", 0)
                if now - last_global < ATTACK_COOLDOWN_GLOBAL:
                    remaining = ATTACK_COOLDOWN_GLOBAL - (now - last_global)
                    return self.send_json({"success": False, "error": f"Wait {remaining}s."}, 400)
                
                last_attack = attacks.get(f"{attacker}->{target}", 0)
                if now - last_attack < ATTACK_COOLDOWN_SAME_TARGET:
                    remaining_min = (ATTACK_COOLDOWN_SAME_TARGET - (now - last_attack)) // 60
                    return self.send_json({"success": False, "error": f"Target on cooldown {remaining_min}m."}, 400)
                
                shields = db.get("shields", {})
                shield_data = shields.get(target, {})
                if int(shield_data.get("expire", 0)) > now:
                    mins = (int(shield_data.get("expire", 0)) - now) // 60
                    target_counter = int(target_data.get("gear_levels", {}).get("counter_hack", 0))
                    if target_counter > 0:
                        counter_amount = min(5000 * target_counter, attacker_data.get("money", 0))
                        attacker_data["money"] = max(0, attacker_data.get("money", 0) - counter_amount)
                        target_data["money"] = target_data.get("money", 0) + counter_amount
                        db["players"][attacker] = attacker_data
                        db["players"][target] = target_data
                        save_db(db, sha)
                        return self.send_json({"success": False, "error": f"🛡 Shielded! Counter stole {counter_amount}.", "counter_loss": counter_amount})
                    return self.send_json({"success": False, "error": f"🛡 Shielded {mins}m."}, 400)
                
                target_vpn = int(target_data.get("gear_levels", {}).get("vpn_cloak", 0))
                if target_vpn > 0 and random.random() < (target_vpn * 0.2):
                    return self.send_json({"success": False, "error": "🌫 VPN Cloak hid them!"}, 400)
                
                steal_amount = min(MAX_STEAL, BASE_STEAL_AMOUNT + (sat_level - 1) * STEAL_PER_LEVEL)
                target_firewall = int(target_data.get("gear_levels", {}).get("firewall", 0))
                reduction = min(0.95, FIREWALL_REDUCTION * target_firewall)
                steal_amount = int(steal_amount * (1.0 - reduction))
                steal_amount = min(steal_amount, target_data.get("money", 0))
                if steal_amount <= 0:
                    return self.send_json({"success": False, "error": "Target has no HC!"}, 400)
                
                target_data["money"] = max(0, target_data.get("money", 0) - steal_amount)
                attacker_data["money"] = attacker_data.get("money", 0) + steal_amount
                
                counter_amount = 0
                target_counter = int(target_data.get("gear_levels", {}).get("counter_hack", 0))
                if target_counter > 0:
                    counter_amount = min(2000 * target_counter, attacker_data.get("money", 0))
                    if counter_amount > 0:
                        attacker_data["money"] = max(0, attacker_data.get("money", 0) - counter_amount)
                        target_data["money"] = target_data.get("money", 0) + counter_amount
                
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

            # === SHIELD ===
            elif self.path == "/api/shield":
                u = payload.get("player", "").strip().lower()
                db, sha = get_db()
                pdata = db["players"].get(u)
                if not pdata:
                    return self.send_json({"success": False, "error": "Player not found."}, 400)
                shield_level = int(pdata.get("gear_levels", {}).get("proxy_shield", 0))
                if shield_level == 0:
                    return self.send_json({"success": False, "error": "Need Proxy Shield!"}, 400)
                now = int(time.time())
                shields = db.get("shields", {})
                existing = shields.get(u, {})
                if int(existing.get("expire", 0)) > now:
                    mins = (int(existing.get("expire", 0)) - now) // 60
                    return self.send_json({"success": False, "error": f"Shield active {mins}m."}, 400)
                duration = SHIELD_DURATION_PER_LEVEL * shield_level
                shields[u] = {"expire": now + duration}
                db["shields"] = shields
                save_db(db, sha)
                return self.send_json({"success": True, "duration_minutes": duration // 60})

            else:
                self.send_json({"success": False, "error": "Unknown endpoint."}, 404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[do_POST] {e}")
            self.send_json({"success": False, "error": f"Server error: {str(e)[:100]}"}, 500)


def run():
    port = int(os.environ.get("PORT", 10000))
    httpd = HTTPServer(("0.0.0.0", port), GameHandler)
    print(f"Hacker Master backend live on :{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
