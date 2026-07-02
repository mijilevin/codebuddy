from flask import Flask
from flask_socketio import SocketIO, emit, join_room
import os
import datetime
from openai import OpenAI

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'codebuddy-secret')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """אתה CodeBuddy, בוט בקבוצת וואטסאפ בעברית. ענה רק כשמתייגים אותך. תשובות קצרות, ידידותיות, עם קוד נקי כשמבקשים. דבר כמו חבר."""

histories = {}

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
            emit("message", {"user": "CodeBuddy 🤖", "text": ai_text, "time": now()}, room=room)
        except Exception as e:
            emit("message", {"user": "מערכת", "text": f"שגיאה: {e}", "time": now()}, room=room)

def now(): return datetime.datetime.now().strftime("%H:%M")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
