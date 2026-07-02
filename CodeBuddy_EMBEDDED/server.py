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

INDEX_HTML = """<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CodeBuddy - צ'אט קבוצתי</title>
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;font-family:'Rubik',sans-serif}
body{margin:0;background:#e5ddd5;height:100vh;display:flex;flex-direction:column}
header{background:#075e54;color:white;padding:12px 16px;font-weight:500;display:flex;justify-content:space-between}
#chat{flex:1;overflow-y:auto;padding:12px;background-image:url('https://user-images.githubusercontent.com/15075759/28719144-86dc0f70-73b1-11e7-911d-60d70fcded21.png')}
.msg{max-width:75%;margin:6px 0;padding:8px 12px;border-radius:8px;position:relative;word-wrap:break-word}
.me{background:#dcf8c6;margin-right:auto}
.other{background:white;margin-left:auto}
.bot{background:#fff3cd;border:1px solid #ffe69c}
.meta{font-size:11px;color:#667781;margin-bottom:3px}
.time{font-size:10px;color:#999;text-align:left;margin-top:4px}
#inputBar{display:flex;padding:8px;background:#f0f0f0;gap:8px}
#msgInput{flex:1;padding:10px;border:none;border-radius:20px;outline:none}
button{background:#075e54;color:white;border:none;padding:0 18px;border-radius:20px;cursor:pointer}
pre{background:#1e1e1e;color:#d4d4d4;padding:8px;border-radius:6px;overflow-x:auto;direction:ltr;text-align:left}
#login{position:fixed;inset:0;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center}
#loginBox{background:white;padding:24px;border-radius:12px;text-align:center;min-width:280px}
select,input{padding:8px;margin:6px;width:220px;border:1px solid #ccc;border-radius:6px}
</style>
</head>
<body>
<header><span>CodeBuddy 🤖</span><span id="roomLabel"></span></header>
<div id="chat"></div>
<div id="inputBar">
  <input id="msgInput" placeholder="כתוב הודעה... תייג @בוט" />
  <button onclick="send()">שלח</button>
</div>

<div id="login">
  <div id="loginBox">
    <h3>כניסה לצ'אט</h3>
    <input id="nameInput" placeholder="השם שלך"/><br>
    <select id="roomSelect">
      <option value="דיבורי">דיבורי</option>
      <option value="טכני">טכני</option>
      <option value="אקראי">אקראי</option>
      <option value="__new__">+ צור חדר חדש</option>
    </select><br>
    <input id="newRoom" placeholder="שם חדר חדש" style="display:none"/><br>
    <button onclick="join()">כניסה</button>
  </div>
</div>

<script>
let socket, username, room;
document.getElementById('roomSelect').onchange = e=>{
  document.getElementById('newRoom').style.display = e.target.value==='__new__'?'inline-block':'none';
};
function join(){
  username = document.getElementById('nameInput').value.trim() || 'אורח';
  const sel = document.getElementById('roomSelect').value;
  room = sel==='__new__' ? (document.getElementById('newRoom').value.trim()||'חדר-חדש') : sel;
  document.getElementById('login').style.display='none';
  document.getElementById('roomLabel').innerText = 'חדר: '+room;
  socket = io();
  socket.emit('join', {username, room});
  socket.on('message', addMsg);
}
function addMsg(m){
  const div = document.createElement('div');
  div.className = 'msg ' + (m.user===username?'me':(m.user.includes('CodeBuddy')?'bot':'other'));
  div.innerHTML = `<div class="meta">${m.user}</div><div>${formatText(m.text)}</div><div class="time">${m.time||''}</div>`;
  document.getElementById('chat').appendChild(div);
  document.getElementById('chat').scrollTop = 1e9;
}
function formatText(t){
  return t.replace(/```([\s\S]*?)```/g, '<pre>$1</pre>').replace(/\n/g,'<br>');
}
function send(){
  const inp = document.getElementById('msgInput');
  const text = inp.value.trim();
  if(!text) return;
  socket.emit('send_message', {username, room, text});
  inp.value='';
}
document.getElementById('msgInput').addEventListener('keydown', e=>{if(e.key==='Enter')send()});
</script>
</body>
</html>"""

@app.route("/")
def index():
    return INDEX_HTML

@socketio.on("join")
def on_join(data):
    username = data.get("username", "אורח")
    room = data.get("room", "main")
    join_room(room)
    history = get_history(room)
    for msg in history[1:][-30:]:
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
