from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)

def init_db():
    conn = sqlite3.connect('safeelec.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS devices
                 (id TEXT PRIMARY KEY, site TEXT, temp REAL, power TEXT, updated_at TIMESTAMP)''')
    for dev_id, site in [
        ("SAFE-TH001", "CP_ALL_WOKWI_TEST"),
        ("SAFE-TH002", "CP_ALL_KHONKAEN_MAIN"),
        ("SAFE-TH003", "CPF_TEST_NODE")
    ]:
        c.execute("INSERT OR IGNORE INTO devices (id, site, power) VALUES (?, ?, ?)",
                  (dev_id, site, "ไฟหลัก AC"))
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = sqlite3.connect('safeelec.db')
    c = conn.cursor()
    c.execute("SELECT * FROM devices ORDER BY id")
    devices = c.fetchall()
    conn.close()
    
    html = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SAFE-ELEC Mini Console</title>
    <style>
        *{box-sizing:border-box;font-family:sans-serif}
        body{background:#1a1a2e;color:#eee;margin:0;padding:20px}
        h1{text-align:center;color:#4cc9f0}
        .device{background:#16213e;border-radius:12px;padding:20px;margin:15px 0;box-shadow:0 4px 12px rgba(0,0,0,0.3)}
        .status{display:inline-block;width:12px;height:12px;border-radius:50%;background:#4ade80;margin-right:8px}
        .id{font-size:18px;font-weight:bold;color:#a855f7}
        .row{margin:10px 0}
        .label{color:#94a3b8;display:inline-block;width:90px}
        .value{font-weight:500}
    </style>
</head>
<body>
    <h1>📊 SAFE-ELEC แดชบอร์ดระบบคลาวด์ฟรี</h1>
    {% for dev in devices %}
    <div class="device">
        <div class="id">
            <span class="status"></span>{{dev[0]}}
            <span style="float:right;color:#4ade80">● ACTIVE</span>
        </div>
        <div class="row"><span class="label">📍 Site:</span> <span class="value">{{dev[1]}}</span></div>
        <div class="row"><span class="label">🌡️ Temp:</span> <span class="value">{{dev[2] if dev[2] is not none else '-'}} °C</span></div>
        <div class="row"><span class="label">⚡ Power:</span> <span class="value" style="color:#60a5fa">{{dev[3]}}</span></div>
        <div class="row"><span class="label">🕐 อัปเดต:</span> <span class="value">{{dev[4] if dev[4] else '-'}}</span></div>
    </div>
    {% endfor %}
</body>
</html>
    '''
    return render_template_string(html, devices=devices)

@app.route('/api/data', methods=['POST'])
def receive_data():
    data = request.get_json(force=True)
    print(f"✅ ได้รับ: {data}")
    
    dev_id = data.get('device_id')
    temp = data.get('temperature')
    power = data.get('power_status')
    
    if not dev_id:
        return jsonify({"error": "missing device_id"}), 400
    
    conn = sqlite3.connect('safeelec.db')
    c = conn.cursor()
    c.execute('''UPDATE devices SET temp=?, power=?, updated_at=? WHERE id=?''',
              (temp, power, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), dev_id))
    
    if c.rowcount == 0:
        return jsonify({"error": "device not found"}), 404
    
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"}), 200

@app.route('/api/data/cmd', methods=['GET'])
def get_command():
    return jsonify({"cmd": "none"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
