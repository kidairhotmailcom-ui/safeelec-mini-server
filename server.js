from flask import Flask, request, jsonify, render_template_string, send_from_directory, session, redirect, url_for
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling
import datetime
import os
import xlsxwriter
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "SAFE-ELEC-2026-SECRET-KEY-CHANGE-ME-PLEASE")
CORS(app, supports_credentials=True)

# === เปิดสิทธิ์ให้ระบบเข้าถึงไฟล์โลโก้ในโฟลเดอร์หลัก ===
@app.route('/<path:filename>')
def serve_root_files(filename):
    return send_from_directory(os.getcwd(), filename)

# === ตั้งค่าฐานข้อมูล MySQL ===
try:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=5,
        host='localhost',
        user='root',
        password='',
        database='device_system'
    )
except Exception as e:
    print(f"⚠️ เตือน: ไม่สามารถเชื่อมต่อ MySQL ได้: {e}")

def get_db_connection():
    return db_pool.get_connection()

# === ข้อมูลผู้ใช้งาน ===
USER_DB = {
    "admin": {"password": "123456", "name": "ผู้ดูแลระบบ", "customer_id": "ALL"},
    "cust0891": {"password": "123456", "name": "อาคารหลัก ขอนแก่น", "customer_id": "CUST-0891"},
}

# === API: เพิ่มลูกค้า ===
@app.route('/api/customers', methods=['POST'])
def add_customer():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO customers VALUES (%s, %s, %s, %s)',
                      (data['customer_id'], data['name'], data['email'], data['phone']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': 'เพิ่มลูกค้าสำเร็จ'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# === API: เพิ่มอุปกรณ์ ===
@app.route('/api/devices', methods=['POST'])
def add_device():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO devices VALUES (%s,%s,%s,%s,%s)',
                      (data['device_id'], data['device_name'], data['type'], data['customer_id'], data['serial_number']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'message': 'เพิ่มอุปกรณ์สำเร็จ'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# === API: รับข้อมูลจาก ESP32 ===
@app.route('/api/esp/upload', methods=['POST'])
def esp_upload():
    try:
        data = request.json
        device_id = data['device_id']
        temp = float(data['temperature'])
        humidity = float(data['humidity'])
        voltage = float(data['voltage'])
        current = float(data['current'])
        
        status = 'normal'
        if temp > 40 or voltage < 200: status = 'warning'
        if temp > 50 or voltage < 190: status = 'critical'

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO esp_readings (device_id, temperature, humidity, voltage, current, status) VALUES (%s,%s,%s,%s,%s,%s)',
            (device_id, temp, humidity, voltage, current, status)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'status': status})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# === API: สร้างรายงาน Excel ===
@app.route('/api/reports/generate-excel', methods=['POST'])
def generate_excel():
    try:
        data = request.json
        customer_id = data['customer_id']
        device_id = data['device_id']
        start_date = data['start_date']
        end_date = data['end_date'] + ' 23:59:59'
        report_id = f"RPT{int(datetime.datetime.now().timestamp() * 1000)}"

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute('SELECT * FROM esp_readings WHERE device_id=%s AND recorded_at BETWEEN %s AND %s',
                      (device_id, start_date, end_date))
        readings = cursor.fetchall()
        
        cursor.execute('SELECT * FROM customers WHERE customer_id=%s', (customer_id,))
        cust = cursor.fetchone()
        
        if not cust:
            return jsonify({'ok': False, 'message': 'ไม่พบลูกค้า'})

        os.makedirs('./reports', exist_ok=True)
        file_path = f"./reports/{report_id}.xlsx"
        
        workbook = xlsxwriter.Workbook(file_path)
        worksheet = workbook.add_worksheet('ข้อมูล')
        worksheet.write(0, 0, 'เวลา')
        worksheet.write(0, 1, 'อุณหภูมิ')
        worksheet.write(0, 2, 'ความชื้น')
        worksheet.write(0, 3, 'แรงดัน')
        worksheet.write(0, 4, 'กระแส')
        worksheet.write(0, 5, 'สถานะ')
        
        row = 1
        for r in readings:
            worksheet.write(row, 0, str(r['recorded_at']))
            worksheet.write(row, 1, r['temperature'])
            worksheet.write(row, 2, r['humidity'])
            worksheet.write(row, 3, r['voltage'])
            worksheet.write(row, 4, r['current'])
            worksheet.write(row, 5, r['status'])
            row += 1
        workbook.close()

        cursor.execute(
            'INSERT INTO reports VALUES (%s,%s,%s,%s,%s,%s)',
            (report_id, customer_id, device_id, start_date, data['end_date'], file_path)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'ok': True, 'report_id': report_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# === หน้าที่ 1: หน้าแรก ===
@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PNS - เพชรนาคา ซิสเต็มเวิร์ก</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: radial-gradient(circle at top right, #0a2540 0%, #020c1b 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      color: #e6f1ff;
      position: relative;
    }
    body::before {
      content: ''; position: absolute; width: 500px; height: 500px;
      background: rgba(0, 98, 255, 0.15); border-radius: 50%;
      filter: blur(80px); top: 10%; left: 10%; z-index: 0;
    }
    .box {
      background: rgba(255,255,255,0.03); backdrop-filter: blur(16px);
      padding: 50px 40px; border-radius: 28px; text-align: center; max-width: 500px;
      border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 20px 50px rgba(0,0,0,0.4);
      position: relative; z-index: 1;
    }
    .logo-container { background: #fff; padding: 15px; border-radius: 20px; display: inline-block; margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); }
    .logo { max-width: 140px; }
    h1 { font-size: 1.6rem; margin-bottom: 6px; }
    .en { color: #00d2ff; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 24px; }
    .divider { height: 2px; width: 60px; background: linear-gradient(90deg, #0062ff, #00d2ff); margin: 0 auto 24px; border-radius: 2px; }
    p { color: #a0aec0; font-size: 1.1rem; margin-bottom: 35px; }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 10px;
      background: linear-gradient(135deg, #0062ff, #004bd4); color: #fff;
      padding: 16px 32px; border-radius: 14px; text-decoration: none; font-weight: 600;
    }
    .btn:hover { background: linear-gradient(135deg, #1a75ff, #0056f5); }
  </style>
</head>
<body>
  <div class="box">
    <div class="logo-container">
      <img src="/865611D1-AE49-4F4F-9460-CA01F09BDD8E.png" alt="PNS เพชรนาคา ซิสเต็มเวิร์ก" class="logo">
    </div>
    <h1>บริษัท เพชรนาคา ซิสเต็มเวิร์ก จำกัด</h1>
    <p class="en">Petchnaka System Work Co.,Ltd.</p>
    <div class="divider"></div>
    <p>ระบบตรวจสอบและเฝ้าดูอุปกรณ์ไฟฟ้า<br><span style="font-size: 0.95rem; color: #718096;">Electrical Device Monitoring System</span></p>
    <a href="/login" class="btn">🔐 เข้าสู่ระบบ SAFE-ELEC</a>
  </div>
</body>
</html>
    ''')

# === หน้าที่ 2: หน้าล็อกอิน ===
@app.route('/login')
def login_page():
    err = request.args.get("err", "")
    return render_template_string('''
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>เข้าสู่ระบบ — SAFE-ELEC</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: radial-gradient(circle at top right, #0a2540 0%, #020c1b 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      color: #e6f1ff;
    }
    .box {
      background: rgba(255,255,255,0.03); backdrop-filter: blur(16px);
      padding: 40px 30px; border-radius: 28px; max-width: 450px; width: 100%;
      border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 20px 50px rgba(0,0,0,0.4);
      text-align: center;
    }
    .logo-container { 
      background: #fff; padding: 12px 20px; border-radius: 20px; 
      display: inline-block; margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); 
    }
    .logo { max-width: 130px; }
    h2 { font-size: 1.4rem; margin-bottom: 25px; }
    .form-group { text-align: left; margin-bottom: 20px; }
    label { display: block; margin-bottom: 8px; color: #8892b0; font-size: 0.9rem; }
    input {
      width: 100%; padding: 14px 16px; background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1); border-radius: 12px;
      color: #fff; font-size: 1rem;
    }
    input:focus { outline: none; border-color: #0062ff; }
    .btn {
      width: 100%; padding: 14px; background: linear-gradient(90deg, #0062ff, #00d2ff);
      border: none; border-radius: 12px; color: #fff; font-size: 1rem;
      font-weight: 600; cursor: pointer;
    }
    .err { color: #f44; margin-top: 15px; }
  </style>
</head>
<body>
  <div class="box">
    <div class="logo-container">
      <img src="/865611D1-AE49-4F4F-9460-CA01F09BDD8E.png" alt="PNS เพชรนาคา ซิสเต็มเวิร์ก" class="logo">
    </div>
    <h2>🔒 เข้าสู่ระบบ SAFE-ELEC</h2>
    <form method="post" action="/do_login">
      <div class="form-group">
        <label>ชื่อผู้ใช้</label>
        <input type="text" name="user" placeholder="กรอกชื่อผู้ใช้" required>
      </div>
      <div class="form-group">
        <label>รหัสผ่าน</label>
        <input type="password" name="pwd" placeholder="กรอกรหัสผ่าน" required>
      </div>
      <button type="submit" class="btn">เข้าสู่ระบบ</button>
      {% if err %}<div class="err">{{err}}</div>{% endif %}
    </form>
  </div>
</body>
</html>
    ''', err=err)

# === API: ตรวจสอบการเข้าสู่ระบบ ===
@app.route("/do_login", methods=["POST"])
def do_login():
    user = request.form.get("user", "").strip()
    pwd = request.form.get("pwd", "")
    if user in USER_DB and USER_DB[user]["password"] == pwd:
        session["username"] = user
        session["cust_id"] = USER_DB[user]["customer_id"]
        session["name"] = USER_DB[user]["name"]
        return redirect("/dashboard")
    return redirect("/login?err=ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

# === API: ออกจากระบบ ===
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ==============================================
# === API ควบคุมและสถานะอุปกรณ์ ===
# ==============================================
device_command_store = {}

@app.route('/api/set-command', methods=['POST'])
def set_command():
    try:
        data = request.json
        device_id = data.get('device_id', 'SAFE-001')
        zone = data.get('zone')
        state = data.get('state')
        if not zone or state is None:
            return jsonify({'ok': False, 'error': 'ข้อมูลไม่ครบ'})
        if device_id not in device_command_store:
            device_command_store[device_id] = {}
        device_command_store[device_id][f'z{zone}'] = state
        device_command_store[device_id]['cmd_hash'] = str(int(datetime.datetime.now().timestamp() * 1000))
        return jsonify({'ok': True, 'message': 'อัปเดตสถานะสำเร็จ'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/command', methods=['GET'])
def get_command():
    device_id = request.args.get('device_id', 'SAFE-001')
    dev = device_command_store.get(device_id, {})
    return jsonify({
        'cmd_hash': dev.get('cmd_hash', ''),
        'z1': dev.get('z1', False),
        'z2': dev.get('z2', False),
        'z3': dev.get('z3', False),
        'z4': dev.get('z4', False),
        'z5': dev.get('z5', False),
        'z6': dev.get('z6', False)
    })

@app.route('/api/data', methods=['GET'])
def get_device_data():
    device_id = request.args.get('device_id', 'SAFE-001')
    return jsonify(device_command_store.get(device_id, {}))

# === หน้าแดชบอร์ด — รวมปุ่มกดและข้อมูลไว้ที่เดียวกัน ===
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>แดชบอร์ด — SAFE-ELEC</title>
        <style>
            body {{ background: #0f1629; color: #fff; font-family: sans-serif; padding: 20px; text-align: center; }}
            .container {{ max-width: 600px; margin: 0 auto; }}
            h1 {{ color: #6cf; margin-bottom: 10px; font-size: 1.5rem; }}
            .user {{ margin-bottom: 20px; color: #8ac; font-size: 0.95rem; }}
            a {{ color: #f66; text-decoration: none; display: inline-block; margin-top: 20px; padding: 10px 20px; background: #251a30; border-radius: 8px; }}
            
            .card {{ background: #253052; padding: 20px; border-radius: 12px; margin-bottom: 20px; text-align: left; }}
            h2 {{ color: #a0d2ff; font-size: 1rem; margin-bottom: 15px; }}
            
            /* === ส่วนข้อมูลเซนเซอร์ === */
            .sensor-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }}
            .sensor-item {{ background: rgba(51, 65, 85, 0.5); padding: 12px; border-radius: 8px; text-align: center; }}
            .sensor-label {{ font-size: 0.8rem; color: #94a3b8; margin-bottom: 4px; }}
            .sensor-value {{ font-size: 1.1rem; font-weight: 600; color: #e2e8f0; }}
            
            /* === ส่วนปุ่มควบคุม === */
            .zone-row {{ display: flex; align-items: center; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #384470; }}
            .zone-row:last-child {{ border-bottom: none; }}
            .zone-name {{ flex: 1; font-size: 0.9rem; color: #e2e8f0; }}
            .status-badge {{ 
                display: inline-block; min-width: 60px; padding: 3px 8px; border-radius: 12px; 
                font-size: 0.75rem; text-align: center; margin-right: 10px; font-weight: 500;
            }}
            .status-on {{ background: #065f46; color: #6ee7b7; }}
            .status-off {{ background: #374151; color: #9ca3af; }}
            .btn {{ padding: 5px 14px; border: none; border-radius: 6px; font-size: 0.8rem; cursor: pointer; font-weight: 500; min-width: 55px; }}
            .btn-on {{ background: #10b981; color: white; }}
            .btn-off {{ background: #4b5563; color: #e5e7eb; }}
            .refresh-btn {{ 
                background: #3b82f6; color: white; border: none; padding: 7px 14px; 
                border-radius: 6px; cursor: pointer; font-size: 0.8rem; margin-bottom: 12px;
            }}
            .refresh-btn:hover {{ background: #2563eb; }}
            .status-bar {{ margin-top: 10px; font-size: 0.8rem; color: #9ab; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ แดชบอร์ดระบบ SAFE-ELEC</h1>
            <div class="user">👤 คุณ: <strong>{session.get('name', '')}</strong><br>รหัสลูกค้า: {session.get('cust_id', '')}</div>
            <p style="margin-bottom: 25px; color: #94a3b8; font-size: 0.9rem;">เข้าสู่ระบบสำเร็จแล้ว!</p>
            
            {/* === การ์ดที่ 1: ข้อมูลเซนเซอร์ === */}
            <div class="card">
                <h2>📊 ตรวจสอบอุปกรณ์วัด</h2>
                <div class="sensor-grid">
                    <div class="sensor-item">
                        <div class="sensor-label">🌡️ อุณหภูมิ</div>
                        <div class="sensor-value" id="temp">-- °C</div>
                    </div>
                    <div class="sensor-item">
                        <div class="sensor-label">💧 ความชื้น</div>
                        <div class="sensor-value" id="humidity">-- %</div>
                    </div>
                    <div class="sensor-item">
                        <div class="sensor-label">⚡ แรงดันไฟ</div>
                        <div class="sensor-value" id="voltage">-- V</div>
                    </div>
                    <div class="sensor-item">
                        <div class="sensor-label">🔌 กระแสไฟ</div>
                        <div class="sensor-value" id="current">-- A</div>
                    </div>
                </div>
                <div class="status-bar" id="sensor-update">อัปเดตเมื่อ: --</div>
            </div>
            
            {/* === การ์ดที่ 2: ปุ่มควบคุม === */}
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h2>💡 ควบคุมแสงสว่าง</h2>
                    <button class="refresh-btn" onclick="loadAllStatus()">🔄 รีเฟรช</button>
                </div>
                
                <div id="light-controls">
                    <div style="text-align: center; padding: 15px; color: #9ab;">กำลังโหลด...</div>
                </div>
                
                <div class="status-bar" id="light-update">อัปเดตเมื่อ: --</div>
            </div>
            
            <a href="/logout">🚪 ออกจากระบบ</a>
        </div>

        <script>
        const zoneNames = {{
            1: '1. ไฟใต้กันสาด',
            2: '2. ไฟโลโก้ป้าย',
            3: '3. ไฟป้ายเสาสูง',
            4: '4. ไฟลานจอด',
            5: '5. ล็อคเลข 7',
            6: '6. ไฟข้างร้าน'
        }};

        // โหลดสถานะไฟ
        async function loadLightStatus() {{
            try {{
                const res = await fetch('/api/command?device_id=SAFE-001');
                const data = await res.json();
                renderLights(data);
                document.getElementById('light-update').textContent = 
                    'อัปเดตเมื่อ: ' + new Date().toLocaleTimeString('th-TH');
            }} catch (e) {{
                document.getElementById('light-controls').innerHTML = 
                    '<div style="text-align:center; color:#f87171; padding:15px;">❌ โหลดข้อมูลล้มเหลว</div>';
            }}
        }}

        function renderLights(data) {{
            let html = '';
            for (let i = 1; i <= 6; i++) {{
                const isOn = data['z' + i] === true;
                html += `
                    <div class="zone-row">
                        <span class="zone-name">${{zoneNames[i]}}</span>
                        <span class="status-badge ${{isOn ? 'status-on' : 'status-off'}}">
                            ${{isOn ? 'เปิด' : 'ปิด'}}
                        </span>
                        <button class="btn ${{isOn ? 'btn-on' : 'btn-off'}}" 
                                onclick="toggleZone(${{i}}, ${{!isOn}})">
                            ${{isOn ? 'ปิด' : 'เปิด'}}
                        </button>
                    </div>
                `;
            }}
            document.getElementById('light-controls').innerHTML = html;
        }}

        async function toggleZone(zone, newState) {{
            try {{
                await fetch('/api/set-command', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ device_id: 'SAFE-001', zone: zone, state: newState }})
                }});
                await loadLightStatus();
            }} catch (e) {{
                alert('❌ ส่งคำสั่งล้มเหลว');
            }}
        }}

        // โหลดข้อมูลเซนเซอร์ (ตัวอย่าง - เชื่อมกับ API จริงของคุณ)
        async function loadSensorData() {{
            // TODO: เชื่อมกับ API ข้อมูลเซนเซอร์จริง
            // ตัวอย่าง: const res = await fetch('/api/esp/readings?device_id=SAFE-001&limit=1');
            // const data = await res.json();
            // if (data.length > 0) {{
            //     document.getElementById('temp').textContent = data[0].temperature + ' °C';
            //     document.getElementById('humidity').textContent = data[0].humidity + ' %';
            //     document.getElementById('voltage').textContent = data[0].voltage + ' V';
            //     document.getElementById('current').textContent = data[0].current + ' A';
            // }}
            document.getElementById('sensor-update').textContent = 
                'อัปเดตเมื่อ: ' + new Date().toLocaleTimeString('th-TH');
        }}

        // โหลดทั้งหมด
        async function loadAllStatus() {{
            await Promise.all([loadLightStatus(), loadSensorData()]);
        }}

        window.onload = loadAllStatus;
        </script>
    </body>
    </html>
"""

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
