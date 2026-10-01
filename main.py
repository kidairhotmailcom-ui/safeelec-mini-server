from flask import Flask, jsonify, request, render_template_string
import sqlite3
import os
from datetime import datetime, timezone

app = Flask(__name__)
DB_NAME = "/tmp/safeelec_mini_global.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mini_fleet (
            device_id TEXT PRIMARY KEY,
            device_pass TEXT,
            site_name TEXT,
            subscription_status TEXT,
            expire_date TEXT,
            last_ping_utc TEXT,
            highest_temp TEXT,
            power_status TEXT
        )
    ''')
    initial_devices = [
        ('SAFE-TH001', 'A2K9M4P7', 'CP_ALL_WOKWI_TEST', 'ACTIVE', '2027-10-01', '-', '-', 'MAIN AC'),
        ('SAFE-TH002', 'B3L8N5Q8', 'CP_ALL_KHONKAEN_MAIN', 'ACTIVE', '2027-10-01', '-', '-', 'MAIN AC'),
        ('SAFE-TH003', 'C4M9P2R7', 'CPF_TEST_NODE', 'ACTIVE', '2027-12-31', '-', '-', 'MAIN AC')
    ]
    for dev in initial_devices:
        cursor.execute("INSERT OR IGNORE INTO mini_fleet VALUES (?,?,?,?,?,?,?,?)", dev)
    conn.commit()
    conn.close()

@app.route('/api/v2/global-fleet-ping', methods=['POST'])
def mini_ping_gateway():
    data = request.json
    if not data:
        return jsonify({"status": "ERROR", "message": "Malformed Payload"}), 400
        
    dev_id = data.get("device_id")
    dev_pass = data.get("device_pass")
    live_temp = data.get("current_temp", "0.0")
    power_stat = data.get("power_status", "MAIN AC")
    
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT device_pass FROM mini_fleet WHERE device_id = ?", (dev_id,))
    record = cursor.fetchone()
    
    if not record or record[0] != dev_pass:
        conn.close()
        return jsonify({"auth": "UNAUTHORIZED"}), 403
        
    utc_now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cursor.execute('''
        UPDATE mini_fleet SET last_ping_utc = ?, highest_temp = ?, power_status = ? WHERE device_id = ?
    ''', (utc_now_str, str(live_temp), power_stat, dev_id))
    conn.commit()
    conn.close()
    
    return jsonify({"auth": "SUCCESS", "remote_command": "RUN_NORMAL"}), 200

@app.route('/global-fleet')
def mini_fleet_dashboard():
    init_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mini_fleet ORDER BY device_id ASC")
    fleet_rows = cursor.fetchall()
    conn.close()
    
    html_layout = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SAFE-ELEC Mini Console</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; background-color: #0d1117; color: #c9d1d9; padding: 15px; margin: 0; }
            h3 { color: #58a6ff; text-align: center; text-transform: uppercase; font-size: 15px; }
            .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; margin-bottom: 12px; }
            .row { display: flex; justify-content: space-between; font-size: 13px; margin: 5px 0; }
            .dev-id { font-weight: bold; color: #ffffff; }
            .stat-active { color: #56d364; font-weight: bold; }
            .power-ac { color: #58a6ff; font-weight: bold; }
            .power-bat { color: #f0883e; font-weight: bold; }
        </style>
    </head>
    <body>
        <h3>📊 SAFE-ELEC แดชบอร์ดระบบคลาวด์ฟรี (iPhone Control)</h3>
        {% for dev in fleet_rows %}
        <div class="card">
            <div class="row"><span class="dev-id">🆔 {{ dev[0] }}</span><span class="stat-active">● {{ dev[3] }}</span></div>
            <div class="row"><span style="color:#8b949e;">📍 Site:</span> <span>{{ dev[2] }}</span></div>
            <div class="row"><span style="color:#8b949e;">🌡️ Temp:</span> <span><b>{{ dev[6] }} °C</b></span></div>
            <div class="row"><span style="color:#8b949e;">⚡ Power:</span> <span class="{% if dev[7]=='MAIN AC' %}power-ac{% else %}power-bat{% endif %}">{% if dev[7]=='MAIN AC' %}ไฟหลัก AC{% else %}แบตสำรอง BATT{% endif %}</span></div>
            <div class="row" style="font-size:10px; color:#8b949e; margin-top:6px;">🕒 {{ dev[5] }}</div>
        </div>
        {% endfor %}
    </body>
    </html>
    '''
    return render_template_string(html_layout, fleet_rows=fleet_rows)

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
