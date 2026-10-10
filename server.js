from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling
import datetime
import os
import requests
import xlsxwriter
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# === เปิดสิทธิ์ให้ระบบเข้าถึงไฟล์โลโก้ในโฟลเดอร์หลัก (Root) ได้โดยตรง ===
@app.route('/<path:filename>')
def serve_root_files(filename):
    return send_from_directory(os.getcwd(), filename)

# === ตั้งค่าฐานข้อมูล MySQL (Connection Pool) ===
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
    print(f"⚠️ เตือน: ไม่สามารถเชื่อมต่อ MySQL ได้ (โปรดตรวจสอบสิทธิ์การเข้าถึง): {e}")

def get_db_connection():
    return db_pool.get_connection()

# === API: เพิ่มลูกค้า ===
@app.route('/api/customers', methods=['POST'])
def add_customer():
    try:
        data = request.json
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO customers VALUES (%s, %s, %s, %s)',
            (data['customer_id'], data['name'], data['email'], data['phone'])
        )
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
        cursor.execute(
            'INSERT INTO devices (device_id, device_name, type, customer_id, serial_number) VALUES (%s,%s,%s,%s,%s)',
            (data['device_id'], data['device_name'], data['type'], data['customer_id'], data['serial_number'])
        )
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
        
        # ดึงข้อมูลการอ่านค่า
        cursor.execute('SELECT * FROM esp_readings WHERE device_id=%s AND recorded_at BETWEEN %s AND %s', (device_id, start_date, end_date))
        readings = cursor.fetchall()
        
        # ดึงข้อมูลลูกค้า
        cursor.execute('SELECT * FROM customers WHERE customer_id=%s', (customer_id,))
        cust = cursor.fetchone()
        
        if not cust:
            return jsonify({'ok': False, 'message': 'ไม่พบลูกค้า'})

        # สร้างโฟลเดอร์สำหรับเก็บรายงาน
        os.makedirs('./reports', exist_ok=True)
        file_path = f"./reports/{report_id}.xlsx"
        
        # เขียนไฟล์ Excel ด้วย XlsxWriter
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

        # บันทึกลงฐานข้อมูลรายงาน
        cursor.execute(
            'INSERT INTO reports (report_id, customer_id, device_id, start_date, end_date, file_path) VALUES (%s,%s,%s,%s,%s,%s)',
            (report_id, customer_id, device_id, start_date, data['end_date'], file_path)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # หมายเหตุ: ในฝั่ง Python สำหรับระบบส่งเมลจริง แนะนำให้ใช้ flask-mail หรือ smtplib เพิ่มเติม
        return jsonify({'ok': True, 'report_id': report_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# === หน้าที่ 1: หน้าแรกสไตล์ Cyber-Tech ===
@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PNS - เพชรนาคา ซิสเต็มเวิร์ก</title>
  <link rel="preconnect" href="https://googleapis.com">
  <link rel="preconnect" href="https://gstatic.com" crossorigin>
  <link href="https://googleapis.com/css2?family=Chakra+Petch:wght@400;600;700&family=Sarabun:wght@300;400;500;600&display=swap" rel="stylesheet">
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
      overflow-x: hidden;
      position: relative;
    }
    body::before {
      content: ''; position: absolute; width: 500px; height: 500px;
      background: rgba(0, 98, 255, 0.15); border-radius: 50%;
      filter: blur(80px); top: 10%; left: 10%; z-index: 0;
    }
    .box {
      background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
      padding: 50px 40px; border-radius: 28px; text-align: center; max-width: 500px; width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
      position: relative; z-index: 1; transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .box:hover { transform: translateY(-5px); border-color: rgba(0, 98, 255, 0.3); box-shadow: 0 25px 60px rgba(0, 98, 255, 0.15); }
    .logo-container { background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 20px; display: inline-block; margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2); }
    .logo { max-width: 140px; height: auto; display: block; }
    h1 { font-family: 'Chakra Petch', sans-serif; color: #ffffff; font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.5px; }
    .en { font-family: 'Chakra Petch', sans-serif; color: #00d2ff; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 24px; }
    .divider { height: 2px; width: 60px; background: linear-gradient(90deg, #0062ff, #00d2ff); margin: 0 auto 24px; border-radius: 2px; }
    p { color: #a0aec0; font-size: 1.1rem; line-height: 1.6; margin-bottom: 35px; font-weight: 300; }
    .btn {
      display: flex; align-items: center; justify-content: center; gap: 10px;
      background: linear-gradient(135deg, #0062ff 0%, #004bd4 100%); color: white;
      padding: 16px 32px; font-size: 18px; border-radius: 14px; text-decoration: none;
      font-weight: 600; letter-spacing: 0.5px; transition: all 0.25s ease;
      box-shadow: 0 4px 15px rgba(0, 98, 255, 0.3); border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .btn:hover { background: linear-gradient(135deg, #1a75ff 0%, #0056f5 100%); transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 98, 255, 0.5); }
    .btn-icon { font-size: 20px; }
  </style>
</head>
<body>
  <div class="box">
    <div class="logo-container">
      <img src="/865611D1-AE49-4F4F-9460-CA01F09BDD8E.png" alt="PNS เพชรนาคา ซิสเต็มเวิร์ค" class="logo">
    </div>
    <h1>บริษัท เพชรนาคา ซิสเต็มเวิร์ก จำกัด</h1>
    <p class="en">Petchnaka System Work Co.,Ltd.</p>
    <div class="divider"></div>
    <p>ระบบตรวจสอบและเฝ้าดูอุปกรณ์ไฟฟ้า<br><span style="font-size: 0.95rem; color: #718096;">Electrical Device Monitoring System</span></p>
    <a href="/login" class="btn">
      <span class="btn-icon">🔐</span> เข้าสู่ระบบ SAFE-ELEC
    </a>
  </div>
</body>
</html>
    ''')

# === หน้าที่ 2: หน้าล็อกอินหลักที่ถูกจัดแต่งตำแหน่งฝังโลโก้บริษัทไว้ด้านบนฟอร์ม ===
@app.route('/login')
def login_page():
    return render_template_string('''
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>เข้าสู่ระบบ — SAFE-ELEC</title>
  <link rel="preconnect" href="https://googleapis.com">
