from flask import Flask, request
from flask_socketio import SocketIO, emit, join_room
import os
import datetime
import json
import threading
from openai import OpenAI

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'codebuddy-secret')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """אתה CodeBuddy, בוט בקבוצת וואטסאפ בעברית. ענה רק כשמתייגים אותך. תשובות קצרות, ידידותיות, עם קוד נקי כשמבקשים. דבר כמו חבר."""

HISTORY_FILE = "histories.json"
histories = {}
lock = threading.Lock()

# טעינת היסטוריה שמורה
if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            histories = json.load(f)
    except:
        histories = {}

def save_histories():
    with lock:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(histories, f, ensure_ascii=False, indent=2)

def get_history(room):
    if room not in histories:
        histories[room] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return histories[room]

@app.route("/")
def index():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@socketio.on("join")
def on_join(data):
    username = data.get("username", "אורח")
    room = data.get("room", "main")
    join_room(room)
    # שלח היסטוריה שמורה
    history = get_history(room)
    for msg in history[1:][-30:]:  # 30 הודעות אחרונות
        if msg["role"] == "user":
            content = msg["content"]
            if ": " in content:
                u, t = content.split(": ", 1)
            else:
                u, t = "משתמש", content
            emit("message", {"user": u, "text": t, "time": ""}, to=request.sid)
        elif msg["role"] == "assistant":
            emit("message", {"user": "CodeBuddy 🤖", "text": msg["content"], "time": ""}, to=request.sid)
    
    emit("message", {"user": "מערכת", "text": f"{username} הצטרף לחדר {room}", "time": now()}, room=room)

@socketio.on("send_message")
def handle_message(data):
    username = data.get("username", "אורח")
    room = data.get("room", "main")
    text = data.get("text", "").strip()
    if not text: return
    emit("message", {"user": username, "text": text, "time": now()}, room=room)
    
    history = get_history(room)
    history.append({"role": "user", "content": f"{username}: {text}"})
    save_histories()
    
    if any(t in text.lower() for t in ["@בוט","@bot","בוט","codebuddy","קוד"]):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=history[-14:],
                temperature=0.5,
                max_tokens=500
            )
            ai_text = resp.choices[0].message.content
            history.append({"role": "assistant", "content": ai_text})
            save_histories()
            emit("message", {"user": "CodeBuddy 🤖", "text": ai_text, "time": now()}, room=room)
        except Exception as e:
            emit("message", {"user": "מערכת", "text": f"שגיאה: {e}", "time": now()}, room=room)

def now(): return datetime.datetime.now().strftime("%H:%M")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
