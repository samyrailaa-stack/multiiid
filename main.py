from flask import Flask, render_template, request, jsonify
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, FeedbackRequired, PleaseWaitFewMinutes, LoginRequired
import threading
import time
import random
import os
import gc

app = Flask(__name__)
app.secret_key = "sujal_hawk_spam_only_2025"

state = {"running": False, "sent": 0, "logs": ["PANEL READY - START DABAO"], "start_time": None, "current_acc_index": 0, "account_stats": []}
cfg = {
    "accounts": [],  # max 4
    "messages": [],
    "spam_delay": 30
}

DEVICES = [
    {"phone_manufacturer": "Google", "phone_model": "Pixel 8 Pro", "android_version": 15, "android_release": "15.0.0", "app_version": "323.0.0.46.109"},
    {"phone_manufacturer": "Samsung", "phone_model": "SM-S928B", "android_version": 15, "android_release": "15.0.0", "app_version": "324.0.0.41.110"},
    {"phone_manufacturer": "OnePlus", "phone_model": "PJZ110", "android_version": 15, "android_release": "15.0.0", "app_version": "322.0.0.40.108"},
    {"phone_manufacturer": "Xiaomi", "phone_model": "23127PN0CC", "android_version": 15, "android_release": "15.0.0", "app_version": "325.0.0.42.111"},
]

def log(msg):
    entry = f"[{time.strftime('%H:%M:%S')}] {msg}"
    state["logs"].append(entry)
    if len(state["logs"]) > 500:
        state["logs"] = state["logs"][-500:]
    gc.collect()

def spam_message(cl, thread_id, msg):
    try:
        cl.direct_send(msg, thread_ids=[thread_id])
        return True
    except Exception as e:
        log(f"SEND FAILED → {str(e)[:60]}")
        return False

def get_current_client():
    index = state["current_acc_index"]
    acc = cfg["accounts"][index]
    cl = Client()
    cl.delay_range = [8, 30]
    device = random.choice(DEVICES)
    cl.set_device(device)
    cl.set_user_agent(f"Instagram {device['app_version']} Android (34/15.0.0; 480dpi; 1080x2340; {device['phone_manufacturer']}; {device['phone_model']}; raven; raven; en_US)")

    try:
        cl.login_by_sessionid(acc["sessionid"])
        log(f"LOGIN SUCCESS ACCOUNT #{index+1} (Device: {device['phone_model']})")
        return cl
    except LoginRequired:
        log(f"ACCOUNT #{index+1} SESSION EXPIRED — SKIPPING")
        state["account_stats"][index]["errors"] += 1
    except Exception as e:
        log(f"ACCOUNT #{index+1} LOGIN FAILED → {str(e)[:80]} — SKIPPING")
        state["account_stats"][index]["errors"] += 1
    return None

def combo_loop():
    if len(cfg["accounts"]) < 2 or len(cfg["accounts"]) > 4:
        log("ERROR: 2 to 4 accounts only allowed")
        state["running"] = False
        return

    state["account_stats"] = [{"errors": 0, "sent": 0} for _ in cfg["accounts"]]

    while state["running"]:
        current_index = state["current_acc_index"]
        current_cl = get_current_client()
        if current_cl is None:
            state["current_acc_index"] = (state["current_acc_index"] + 1) % len(cfg["accounts"])
            time.sleep(5)
            continue

        try:
            msg = random.choice(cfg["messages"])
            if spam_message(current_cl, cfg["accounts"][current_index]["thread_id"], msg):
                state["sent"] += 1
                state["account_stats"][current_index]["sent"] += 1
                log(f"SENT #{state['sent']} → {msg[:40]} (Account #{current_index+1})")

            # Alternate: next message next account se
            state["current_acc_index"] = (state["current_acc_index"] + 1) % len(cfg["accounts"])

            time.sleep(cfg["spam_delay"] + random.uniform(-2, 3))
        except ChallengeRequired or FeedbackRequired:
            log("Challenge/Feedback → skipping")
            time.sleep(30)
        except PleaseWaitFewMinutes:
            log("Rate limit → waiting 8 min")
            time.sleep(480)
        except Exception as e:
            log(f"ACTION FAILED → {str(e)[:60]}")
            time.sleep(15)
            state["current_acc_index"] = (state["current_acc_index"] + 1) % len(cfg["accounts"])
            gc.collect()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    global state
    state["running"] = False
    time.sleep(1)
    state = {"running": True, "sent": 0, "logs": ["STARTED - WAIT FOR LOGIN"], "start_time": time.time(), "current_acc_index": 0}

    accounts_raw = request.form["accounts"].strip().split("\n")
    cfg["accounts"] = []
    for line in accounts_raw:
        if line.strip():
            sessionid, thread_id = line.split(":")
            cfg["accounts"].append({"sessionid": sessionid.strip(), "thread_id": int(thread_id.strip())})

    cfg["messages"] = [m.strip() for m in request.form["messages"].split("\n") if m.strip()]
    cfg["spam_delay"] = float(request.form.get("spam_delay", "30"))

    threading.Thread(target=combo_loop, daemon=True).start()
    log(f"STARTED WITH {len(cfg['accounts'])} ACCOUNTS")

    return jsonify({"ok": True})

@app.route("/stop")
def stop():
    state["running"] = False
    log("STOPPED BY USER")
    return jsonify({"ok": True})

@app.route("/status")
def status():
    uptime = "00:00:00"
    if state.get("start_time"):
        t = int(time.time() - state["start_time"])
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        uptime = f"{h:02d}:{m:02d}:{s:02d}"
    return jsonify({
        "running": state["running"],
        "sent": state["sent"],
        "uptime": uptime,
        "logs": state["logs"][-100:]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
