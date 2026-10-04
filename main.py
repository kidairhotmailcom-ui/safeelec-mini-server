from flask import Flask, jsonify, request, render_template_string
import sqlite3
import json
from datetime import datetime, timezone

app = Flask(__name__)
DB_NAME = "safeelec_v2.db"

# ==============================================
# 🗄️ สร้างฐานข้อมูล
# ==============================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS industrial_fleet (
        device_id TEXT PRIMARY KEY,
        device_pass TEXT,
        site_code TEXT,
        region TEXT DEFAULT 'ภาคอีสาน',
        province TEXT DEFAULT 'ขอนแก่น',
        business_type TEXT DEFAULT 'ร้านสะดวกซื้อ',
        status TEXT DEFAULT 'ACTIVE',
        last_ping TEXT,
        temp_max TEXT,
        grid_status TEXT,
        gnd_leakage TEXT,
        system_mad_status TEXT,
        cb_total INTEGER DEFAULT 0,
        cb_active INTEGER DEFAULT 0,
        cb_vacant INTEGER DEFAULT 0,
        cb_warning INTEGER DEFAULT 0,
        cb_danger INTEGER DEFAULT 0,
        cb_data TEXT,
        is_backup INTEGER DEFAULT 0,
        assigned_to TEXT DEFAULT 'ทีมช่างจังหวัดขอนแก่น',
        backup_device_id TEXT,
        daily_kwh TEXT,
        power_factor TEXT
    )
    ''')
    
    # ข้อมูลเริ่มต้น
    init_nodes = [
        ('SAFE-TH001', 'A2K9M4P7', 'CP_ALL_WOKWI_TEST', 'ภาคอีสาน', 'ขอนแก่น', 'ร้านสะดวกซื้อ', 'ACTIVE', '-', '41.5', 'MAIN AC', '0.00', 'OPERATIONAL', 38, 0, 38, 0, 0, '{}', 0, 'SAFE-TH001-BAK', '45.8', '0.88'),
        ('SAFE-TH002', 'A2K9M4P7', 'CP_ALL_KHONKAEN_MAIN', 'ภาคอีสาน', 'ขอนแก่น', 'ร้านสะดวกซื้อ', 'ACTIVE', '-', '42.0', 'MAIN AC', '0.00', 'OPERATIONAL', 38, 0, 38, 0, 0, '{}', 0, 'SAFE-TH002-BAK', '42.3', '0.89'),
        ('SAFE-TH003', 'A2K9M4P7', 'CPF_TEST_NODE', 'ภาคอีสาน', 'ขอนแก่น', 'ทดสอบระบบ', 'ACTIVE', '-', '39.5', 'MAIN AC', '0.00', 'OPERATIONAL', 38, 0, 38, 0, 0, '{}', 0, 'SAFE-TH003-BAK', '38.2', '0.91')
    ]
    cur.executemany('''
        INSERT OR IGNORE INTO industrial_fleet VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', init_nodes)
    conn.commit()
    conn.close()

init_db()

# ==============================================
# 📡 รับข้อมูลจากอุปกรณ์
# ==============================================
@app.route('/api/data', methods=['POST'])
def receive_data():
    data = request.json
    if not data:
        return jsonify({"status": "ERROR"}), 400
    
    dev_id = data.get("device_id")
    dev_pass = data.get("device_pass")
    if not dev_id:
        return jsonify({"status": "MISSING_ID"}), 400

    cb_count = int(data.get("cb_count", 0))
    cb_data = {}
    active = vacant = warning = danger = 0
    max_rating = 20.0

    for i in range(1, cb_count + 1):
        val = float(data.get(f"cb{i}", 0))
        cb_data[f"cb{i}"] = round(val, 1)
        if val > 0.1:
            active += 1
            if val >= max_rating * 0.9:
                danger += 1
            elif val >= max_rating * 0.7:
                warning += 1
        else:
            vacant += 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute('''
        UPDATE industrial_fleet SET
            device_pass=?, site_code=?, last_ping=?, temp_max=?, grid_status=?,
            gnd_leakage=?, system_mad_status=?, cb_total=?, cb_active=?, cb_vacant=?,
            cb_warning=?, cb_danger=?, cb_data=?, is_backup=?, daily_kwh=?, power_factor=?
        WHERE device_id=?
    ''', (
        dev_pass,
        data.get("site_code", "-"),
        now,
        data.get("current_temp", "-"),
        data.get("power_status", "-"),
        data.get("gnd_leakage", "0.00"),
        data.get("system_mad_status", "OPERATIONAL"),
        cb_count,
        active,
        vacant,
        warning,
        danger,
        json.dumps(cb_data),
        1 if data.get("is_backup") else 0,
        data.get("daily_kwh", "0"),
        data.get("power_factor", "0"),
        dev_id
    ))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "SUCCESS", "device_id": dev_id}), 200

# ==============================================
# 📊 หน้าแรก — แสดงรายการอุปกรณ์
# ==============================================
@app.route('/')
def mini_console():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT device_id, site_code, status, temp_max, grid_status, 
               cb_total, cb_active, cb_vacant, cb_warning, cb_danger
        FROM industrial_fleet ORDER BY device_id
    """)
    devices = cur.fetchall()
    conn.close()

    html = '''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC Mini Console</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;}
body{background:#0b0e17;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;padding:12px;}
.header{text-align:center;padding:15px 10px 20px;}
.header h1{color:#00ffff;font-size:18px;}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;margin-bottom:14px;}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;}
.dev-id{background:#7928ca;color:#fff;padding:5px 12px;border-radius:4px;font-weight:bold;font-size:15px;}
.active{color:#00ff88;font-weight:bold;}
.row{display:flex;align-items:center;margin:9px 0;font-size:14px;}
.label{width:90px;color:#8b949e;}
.val{font-weight:bold;}
.temp{color:#ff6b6b;}
.power{color:#58a6ff;}
.stat-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-top:12px;}
.stat{background:#1c2135;padding:8px 5px;border-radius:4px;text-align:center;font-size:12px;}
.stat b{display:block;font-size:16px;}
.total{background:#1c2135;}
.on{background:#132e1f;}
.empty{background:#212634;}
.warn{background:#3d2e08;}
.danger{background:#421c1c;}
.cb-section{margin-top:14px;}
.cb-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(70px,1fr));gap:6px;margin-top:8px;}
.cb{padding:8px 4px;border-radius:4px;font-size:11px;text-align:center;}
.cb-vacant{background:#212634;border-left:4px solid #6e7681;color:#8b949e;}
.cb-ok{background:#132e1f;border-left:4px solid #28c840;color:#8fffa8;}
.cb-warn{background:#3d2e08;border-left:4px solid #d29922;color:#ffd670;}
.cb-danger{background:#421c1c;border-left:4px solid #ff4444;color:#ff9999;animation:blink 1.5s infinite;}
@keyframes blink{50%{opacity:0.4;}}
</style>
</head>
<body>
<div class="header">
  <h1>📊 SAFE-ELEC แดชบอร์ดระบบคลาวด์ฟรี</h1>
</div>
'''

    for d in devices:
        dev_id, site, status, temp, power, total, active, vacant, warn, danger = d
        power_text = "ไฟหลัก AC" if power == "MAIN AC" else "แบตเตอรี่สำรอง"
        html += f'''
<div class="card">
  <div class="top">
    <span class="dev-id">{dev_id}</span>
    <span class="active">● ACTIVE</span>
  </div>
  <div class="row"><span class="label">📍 Site:</span><span class="val">{site}</span></div>
  <div class="row"><span class="label">🌡️ Temp:</span><span class="val temp">{temp} °C</span></div>
  <div class="row"><span class="label">⚡ Power:</span><span class="val power">{power_text}</span></div>
  <div class="stat-grid">
    <div class="stat total">ทั้งหมด<b>{total}</b></div>
    <div class="stat on">ใช้งาน<b>{active}</b></div>
    <div class="stat empty">ว่าง<b>{vacant}</b></div>
    <div class="stat warn">เฝ้าระวัง<b>{warn}</b></div>
    <div class="stat danger">อันตราย<b>{danger}</b></div>
  </div>
</div>
'''

    html += '''
</body>
</html>
'''
    return html

# ==============================================
# 📋 หน้าผังวงจรละเอียด
# ==============================================
@app.route('/detail/<device_id>')
def detail(device_id):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT device_id, site_code, temp_max, grid_status, cb_total, cb_data
        FROM industrial_fleet WHERE device_id=?
    """, (device_id,))
    d = cur.fetchone()
    conn.close()
    
    if not d:
        return "ไม่พบอุปกรณ์", 404
    
    dev_id, site, temp, power, total, cb_json = d
    cb_data = json.loads(cb_json) if cb_json else {}

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{dev_id} — ผังวงจร</title>
<style>
body{{background:#0b0e17;color:#c9d1d9;font-family:sans-serif;padding:12px;}}
.back{{color:#00ffff;text-decoration:none;display:inline-block;margin-bottom:15px;}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:16px;}}
h2{{color:#00ffff;margin-bottom:10px;}}
.cb-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(90px,1fr));gap:8px;margin-top:15px;}}
.cb{{padding:10px 6px;border-radius:5px;text-align:center;font-size:13px;}}
.cb-vacant{{background:#212634;border-left:4px solid #6e7681;color:#8b949e;}}
.cb-ok{{background:#132e1f;border-left:4px solid #28c840;color:#8fffa8;}}
.cb-warn{{background:#3d2e08;border-left:4px solid #d29922;color:#ffd670;}}
.cb-danger{{background:#421c1c;border-left:4px solid #ff4444;color:#ff9999;animation:blink 1.5s infinite;}}
@keyframes blink{{50%{{opacity:0.4;}}}}
</style>
</head>
<body>
<a href="/" class="back">← กลับหน้าหลัก</a>
<div class="card">
  <h2>{dev_id}</h2>
  <p>📍 {site} | 🌡️ {temp} °C | ⚡ {power}</p>
  <h3 style="margin-top:15px;">ผังวงจรภายในตู้ — ทั้งหมด {total} ช่อง</h3>
  <div class="cb-grid">
'''
    for i in range(1, total + 1):
        val = float(cb_data.get(f"cb{i}", 0))
        if val < 0.1:
            cls = "cb-vacant"
            txt = "ว่าง"
        elif val >= 18.0:
            cls = "cb-danger"
            txt = f"{val}A ⚠️"
        elif val >= 14.0:
            cls = "cb-warn"
            txt = f"{val}A"
        else:
            cls = "cb-ok"
            txt = f"{val}A"
        html += f'<div class="cb {cls}"><b>ช่อง {i}</b><br>{txt}</div>'
    
    html += '''
  </div>
</div>
</body>
</html>
'''
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
          
