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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Sarabun:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: radial-gradient(circle at top right, #0a2540 0%, #020c1b 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      font-family: 'Sarabun', sans-serif;
      color: #e6f1ff;
      position: relative;
    }
    body::before {
      content: ''; position: absolute; width: 500px; height: 500px;
      background: rgba(0, 98, 255, 0.15); border-radius: 50%;
      filter: blur(80px); top: 10%; left: 10%; z-index: 0;
    }
    .box {
      background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px);
      padding: 50px 40px; border-radius: 28px; text-align: center; max-width: 500px;
      border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 20px 50px rgba(0,0,0,0.4);
      position: relative; z-index: 1; transition: transform 0.3s ease;
    }
    .box:hover { transform: translateY(-5px); border-color: rgba(0, 98, 255, 0.3); }
    .logo-container { background: #fff; padding: 15px; border-radius: 20px; display: inline-block; margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); }
    .logo { max-width: 140px; }
    h1 { font-family: 'Chakra Petch', sans-serif; font-size: 1.6rem; margin-bottom: 6px; }
    .en { font-family: 'Chakra Petch', sans-serif; color: #00d2ff; font-size: 0.85rem; text-transform: uppercase; margin-bottom: 24px; }
    .divider { height: 2px; width: 60px; background: linear-gradient(90deg, #0062ff, #00d2ff); margin: 0 auto 24px; border-radius: 2px; }
    p { color: #a0aec0; font-size: 1.1rem; margin-bottom: 35px; }
    .btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 10px;
      background: linear-gradient(135deg, #0062ff, #004bd4); color: #fff;
      padding: 16px 32px; border-radius: 14px; text-decoration: none; font-weight: 600;
      transition: all 0.3s ease;
    }
    .btn:hover { background: linear-gradient(135deg, #1a75ff, #0056f5); transform: translateY(-2px); }
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Sarabun:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: radial-gradient(circle at top right, #0a2540 0%, #020c1b 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      font-family: 'Sarabun', sans-serif;
      color: #e6f1ff;
    }
    .box {
      background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px);
      padding: 40px 30px; border-radius: 28px; max-width: 450px; width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 20px 50px rgba(0,0,0,0.4);
      text-align: center;
    }
    .logo-container { 
      background: #fff; padding: 12px 20px; border-radius: 20px; 
      display: inline-block; margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); 
    }
    .logo { max-width: 130px; }
    h2 { font-family: 'Chakra Petch', sans-serif; font-size: 1.4rem; margin-bottom: 25px; }
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
      font-weight: 600; cursor: pointer; transition: opacity 0.3s;
    }
    .btn:hover { opacity: 0.9; }
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

# === หน้าแดชบอร์ด ===
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>แดชบอร์ด — SAFE-ELEC</title>
        <style>
            body {{ background: #0f1629; color: #fff; font-family: sans-serif; padding: 30px; text-align: center; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1a2342; padding: 40px; border-radius: 16px; border: 1px solid #2a3b63; }}
            h1 {{ color: #6cf; margin-bottom: 20px; }}
            .user {{ margin-bottom: 30px; color: #8ac; }}
            a {{ color: #f66; text-decoration: none; display: inline-block; margin-top: 20px; padding: 10px 20px; background: #251a30; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>✅ ยินดีต้อนรับสู่ SAFE-ELEC</h1>
            <div class="user">👤 คุณ: <strong>{session.get('name', '')}</strong><br>รหัสลูกค้า: {session.get('cust_id', '')}</div>
            <p>เข้าสู่ระบบสำเร็จแล้ว!</p>
            <a href="/logout">🚪 ออกจากระบบ</a>
        </div>
    </body>
    </html>
    """

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
