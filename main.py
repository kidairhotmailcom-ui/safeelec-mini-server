from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, send_file
from flask_cors import CORS
from datetime import datetime
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import xlsxwriter
import io
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "SAFE-ELEC-2026-SECRET-KEY-CHANGE-ME-PLEASE")
CORS(app, supports_credentials=True)

# ==================== ข้อมูลผู้ใช้ ====================
USER_DB = {
    "admin": {"password": "123456", "name": "ผู้ดูแลระบบ", "customer_id": "ALL"},
    "cust0891": {"password": "123456", "name": "อาคารหลัก ขอนแก่น", "customer_id": "CUST-0891"},
    "cust0002": {"password": "123456", "name": "สาขาเชียงใหม่", "customer_id": "CUST-0002"},
}

# ==================== การตั้งค่าระบบ ====================
CONFIG = {
    "SYSTEM_NAME": "SAFE-ELEC",
    "VERSION": "3.0.0-FULL",
    "STANDARD": {
        "V3_NOM": 380, "V3_MIN": 342, "V3_MAX": 418,
        "V1_NOM": 220, "V1_MIN": 198, "V1_MAX": 242,
        "TEMP_MIN": -10, "TEMP_MAX": 75, "TEMP_ALERT": 60,
        "HUMI_MIN": 20, "HUMI_MAX": 90,
        "BALANCE_MAX_A": 5.0, "BALANCE_MAX_PCT": 10.0,
        "OFFLINE_SEC": 90,
        "GND_RES_OK": 10.0, "GND_RES_WARN": 30.0,
        "GND_V_OK": 2.0,
        "BACKUP_HEARTBEAT_SEC": 3,
    },
    "ALERT": {
        "ENABLED": True,
        "LINE_TOKEN": os.environ.get("LINE_TOKEN", ""),
        "EMAIL_TO": os.environ.get("EMAIL_TO", ""),
        "EMAIL_FROM": os.environ.get("EMAIL_FROM", ""),
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 587,
        "SMTP_PASS": os.environ.get("SMTP_PASS", ""),
        "SEND_REPEAT_DELAY_MIN": 30,
    },
    "REPORT": {
        "AUTO_SEND": True,
        "SCHEDULE_TIME": "09:00",
        "DAY_OF_MONTH": 1,
    }
}

FIELD_MAP = {
    "id": "device_id", "esp_id": "device_id", "esp": "device_id",
    "site": "site_name", "cust": "customer_id", "role": "role",
    "is_master": "is_master", "active": "backup_active",
    "partner": "partner_online", "t": "current_temp", "temp": "current_temp",
    "temperature": "current_temp", "temp_c": "current_temp",
    "humi": "humidity", "rh": "humidity", "humidity_rh": "humidity",
    "v12": "v_l1_l2", "v23": "v_l2_l3", "v31": "v_l3_l1",
    "v_ab": "v_l1_l2", "v_bc": "v_l2_l3", "v_ca": "v_l3_l1",
    "i1": "a_l1", "i2": "a_l2", "i3": "a_l3", "in": "a_n",
    "ia": "a_l1", "ib": "a_l2", "ic": "a_l3", "i_n": "a_n",
    "kw": "power_kw", "p": "power_kw", "power": "power_kw",
    "gnd_r": "gnd_resistance_ohm", "ground_resistance": "gnd_resistance_ohm",
    "gnd_v": "gnd_voltage_v", "ground_leakage_v": "gnd_voltage_v",
    "alarm": "fault_list", "faults": "fault_list",
}

# ==================== ข้อมูลอุปกรณ์ ====================
DEVICE_LIST = [
    {
        "device_id": "SAFE-001", "site_name": "อาคารหลัก ขอนแก่น", "customer_id": "CUST-0891",
        "role": "MASTER", "is_master": True, "backup_active": False, "partner_online": True,
        "last_updated": "2026-10-10 23:30:00", "current_temp": 28.5, "humidity": 58,
        "v_l1_l2": 382, "v_l2_l3": 379, "v_l3_l1": 381,
        "a_l1": 12.5, "a_l2": 12.3, "a_l3": 12.4, "a_n": 0.25,
        "balance_3ph_ok": True, "power_kw": 8.45,
        "gnd_resistance_ohm": 4.2, "gnd_voltage_v": 0.85, "gnd_system_ok": True,
        "is_online": True, "status_summary": "online", "alert_level": "normal",
        "fault_list": []
    },
    {
        "device_id": "SAFE-002", "site_name": "อาคารหลัก ขอนแก่น (สำรอง)", "customer_id": "CUST-0891",
        "role": "BACKUP", "is_master": False, "backup_active": False, "partner_online": True,
        "last_updated": "2026-10-10 23:29:50", "current_temp": 29.1, "humidity": 60,
        "v_l1_l2": 380, "v_l2_l3": 378, "v_l3_l1": 379,
        "a_l1": 11.8, "a_l2": 11.6, "a_l3": 11.7, "a_n": 0.30,
        "balance_3ph_ok": True, "power_kw": 7.90,
        "gnd_resistance_ohm": 5.5, "gnd_voltage_v": 1.10, "gnd_system_ok": True,
        "is_online": True, "status_summary": "online", "alert_level": "normal",
        "fault_list": []
    },
    {
        "device_id": "SAFE-003", "site_name": "สาขาเชียงใหม่", "customer_id": "CUST-0002",
        "role": "MASTER", "is_master": True, "backup_active": False, "partner_online": False,
        "last_updated": "2026-10-10 23:15:00", "current_temp": 32.0, "humidity": 65,
        "v_l1_l2": 375, "v_l2_l3": 368, "v_l3_l1": 372,
        "a_l1": 15.2, "a_l2": 14.8, "a_l3": 15.5, "a_n": 0.80,
        "balance_3ph_ok": False, "power_kw": 10.25,
        "gnd_resistance_ohm": 12.5, "gnd_voltage_v": 3.20, "gnd_system_ok": False,
        "is_online": True, "status_summary": "warning", "alert_level": "warning",
        "fault_list": ["แรงดันเฟส L2 ต่ำ", "กราวด์ผิดปกติ"]
    }
]

# ==================== ฟังก์ชันส่งแจ้งเตือน ====================
def send_line_notify(message):
    token = CONFIG["ALERT"]["LINE_TOKEN"]
    if not token:
        return False
    try:
        res = requests.post(
            "https://notify-api.line.me/api/notify",
            headers={"Authorization": f"Bearer {token}"},
            data={"message": message}
        )
        return res.status_code == 200
    except Exception as e:
        print(f"[LINE ERROR] {e}")
        return False

def send_email_alert(subject, body):
    cfg = CONFIG["ALERT"]
    if not cfg.get("EMAIL_TO") or not cfg.get("SMTP_PASS"):
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = cfg["EMAIL_FROM"]
        msg["To"] = cfg["EMAIL_TO"]
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP(cfg["SMTP_SERVER"], cfg["SMTP_PORT"]) as server:
            server.starttls()
            server.login(cfg["EMAIL_FROM"], cfg["SMTP_PASS"])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False

# ==================== สร้างรายงาน Excel ====================
def generate_excel_report():
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    ws = workbook.add_worksheet("สรุปภาพรวม")
    
    header = workbook.add_format({'bold': True, 'bg_color': '#1e40af', 'color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter'})
    header.set_text_wrap()
    normal = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
    left = workbook.add_format({'text_wrap': True, 'align': 'left', 'valign': 'vcenter'})
    red = workbook.add_format({'font_color': '#dc2626', 'bold': True, 'align': 'center'})
    orange = workbook.add_format({'font_color': '#f97316', 'bold': True, 'align': 'center'})
    green = workbook.add_format({'font_color': '#16a34a', 'bold': True, 'align': 'center'})
    gray = workbook.add_format({'font_color': '#6b7280', 'align': 'center'})

    headers = [
        "รหัสอุปกรณ์", "ชื่อสถานที่", "บทบาท", "สถานะออนไลน์", "สถานะระบบ",
        "เวลาอัปเดตล่าสุด", "อุณหภูมิ\n(°C)", "ความชื้น\n(%)",
        "แรงดัน\nL1-L2 (V)", "แรงดัน\nL2-L3 (V)", "แรงดัน\nL3-L1 (V)",
        "กระแส\nL1 (A)", "กระแส\nL2 (A)", "กระแส\nL3 (A)", "กระแสรวม\nศูนย์ (A)",
        "ดุลยภาพ\n3 เฟส", "กำลังไฟฟ้า\n(kW)",
        "กราวด์\nต้านทาน (Ω)", "กราวด์\นรั่ว (V)", "สถานะ\nกราวด์",
        "จำนวนปัญหา"
    ]
    
    for col, h in enumerate(headers):
        ws.write(0, col, h, header)

    for row, d in enumerate(DEVICE_LIST, start=1):
        role_label = d.get("role", "-")
        if role_label == "MASTER":
            role_label = "ตัวหลัก"
        elif role_label == "BACKUP":
            role_label = "ตัวสำรอง"
        if d.get("backup_active"):
            role_label += "\n(ทำงานแทน)"
        
        online_text = "✅ ออนไลน์" if d["is_online"] else "❌ ขาดการติดต่อ"
        online_fmt = green if d["is_online"] else red
        
        status_map = {
            "online": ("ปกติ", green),
            "warning": ("เฝ้าระวัง", orange),
            "critical": ("อันตราย", red),
            "offline": ("ขาดการติดต่อ", gray),
        }
        status_text, status_fmt = status_map.get(d["status_summary"], ("-", normal))
        
        balance_ok = d.get("balance_3ph_ok", True)
        balance_text = "ปกติ" if balance_ok else "ไม่สมดุล"
        balance_fmt = green if balance_ok else orange
        
        gnd_ok = d.get("gnd_system_ok", True)
        gnd_val = d.get("gnd_resistance_ohm", 0)
        if gnd_val <= 0:
            gnd_status = "รอข้อมูล"
            gnd_fmt = gray
        elif gnd_ok:
            gnd_status = "ปกติ"
            gnd_fmt = green
        else:
            gnd_status = "ผิดปกติ"
            gnd_fmt = red

        ws.write(row, 0, d["device_id"], left)
        ws.write(row, 1, d["site_name"], left)
        ws.write(row, 2, role_label, normal)
        ws.write(row, 3, online_text, online_fmt)
        ws.write(row, 4, status_text, status_fmt)
        ws.write(row, 5, d.get("last_updated", "-"), normal)
        ws.write(row, 6, d.get("current_temp", 0), normal)
        ws.write(row, 7, d.get("humidity", 0), normal)
        ws.write(row, 8, d.get("v_l1_l2", 0), normal)
        ws.write(row, 9, d.get("v_l2_l3", 0), normal)
        ws.write(row, 10, d.get("v_l3_l1", 0), normal)
        ws.write(row, 11, d.get("a_l1", 0), normal)
        ws.write(row, 12, d.get("a_l2", 0), normal)
        ws.write(row, 13, d.get("a_l3", 0), normal)
        ws.write(row, 14, d.get("a_n", 0), normal)
        ws.write(row, 15, balance_text, balance_fmt)
        ws.write(row, 16, d.get("power_kw", 0), normal)
        ws.write(row, 17, d.get("gnd_resistance_ohm", 0), normal)
        ws.write(row, 18, d.get("gnd_voltage_v", 0), normal)
        ws.write(row, 19, gnd_status, gnd_fmt)
        ws.write(row, 20, f"{len(d.get('fault_list', []))} รายการ", normal)
    
    col_widths = [18, 30, 16, 16, 14, 16, 14, 14, 14, 14, 14, 12, 12, 12, 14, 14, 14, 16, 16, 14, 14]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)
    
    workbook.close()
    output.seek(0)
    return {
        "data": output.read(),
        "name": f"SAFE-ELEC-Report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    }

# ==================== เส้นทาง API ====================
@app.route("/")
def index():
    if "username" not in session:
        return redirect(url_for("login_page"))
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC ระบบเฝ้าระวังความปลอดภัยระบบไฟฟ้า</title>
<style>
*{margin:0; padding:0; box-sizing:border-box; font-family:sans-serif;}
body{background:#f0f4f8; min-height:100vh;}
.header{background:linear-gradient(135deg,#1e40af,#3b82f6); color:white; padding:16px 24px; display:flex; justify-content:space-between; align-items:center;}
.header h1{font-size:22px;}
.user-info{display:flex; gap:16px; align-items:center;}
.logout-btn{background:rgba(255,255,255,.2); color:white; border:none; padding:8px 16px; border-radius:6px; cursor:pointer;}
.container{max-width:1400px; margin:0 auto; padding:24px;}
.card{background:white; border-radius:12px; padding:20px; margin-bottom:20px; box-shadow:0 2px 8px rgba(0,0,0,.06);}
.card h2{font-size:18px; margin-bottom:16px; color:#1e293b; border-bottom:1px solid #e2e8f0; padding-bottom:8px;}
.device-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:16px;}
.device-card{border:1px solid #e2e8f0; border-radius:10px; padding:16px; transition:.2s;}
.device-card:hover{box-shadow:0 4px 12px rgba(0,0,0,.08);}
.device-card.online{border-left:4px solid #16a34a;}
.device-card.warning{border-left:4px solid #f97316;}
.device-card.critical{border-left:4px solid #dc2626;}
.device-card.offline{border-left:4px solid #6b7280; opacity:.8;}
.status-badge{display:inline-block; padding:4px 10px; border-radius:20px; font-size:13px; font-weight:600; margin-bottom:10px;}
.status-online{background:#dcfce7; color:#166534;}
.status-warning{background:#ffedd5; color:#9a3412;}
.status-critical{background:#fee2e2; color:#991b1b;}
.status-offline{background:#f3f4f6; color:#4b5563;}
.info-row{display:flex; justify-content:space-between; padding:4px 0; font-size:14px;}
.label{color:#64748b;}
.value{font-weight:500; color:#1e293b;}
.action-bar{display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap;}
.btn{padding:10px 20px; border:none; border-radius:8px; font-size:15px; cursor:pointer; text-decoration:none; display:inline-block; text-align:center;}
.btn-primary{background:#2563eb; color:white;}
.btn-success{background:#16a34a; color:white;}
.btn:hover{opacity:.9;}
@media(max-width:640px){.device-grid{grid-template-columns:1fr;}}
</style>
</head>
<body>
<div class="header">
    <h1>⚡ SAFE-ELEC</h1>
    <div class="user-info">
        <span>{{ session['name'] }}</span>
        <a href="/logout" class="logout-btn">ออกจากระบบ</a>
    </div>
</div>
<div class="container">
    <div class="action-bar">
        <a href="/api/report-excel" class="btn btn-success">📥 ดาวน์โหลดรายงาน Excel</a>
    </div>
    <div class="card">
        <h2>📊 สถานะอุปกรณ์</h2>
        <div class="device-grid">
            {% for dev in devices %}
            <div class="device-card {{ dev.alert_level if dev.is_online else 'offline' }}">
                <span class="status-badge status-{{ dev.alert_level if dev.is_online else 'offline' }}">
                    {{ '✅ ออนไลน์' if dev.is_online else '❌ ขาดการติดต่อ' }} — 
                    {{ {'normal':'ปกติ','warning':'เฝ้าระวัง','critical':'อันตราย'}.get(dev.alert_level,'-') }}
                </span>
                <h3>{{ dev.device_id }}</h3>
                <p style="color:#475569; font-size:14px; margin:6px 0 10px;">{{ dev.site_name }}</p>
                <div class="info-row"><span class="label">บทบาท:</span><span class="value">{{ 'ตัวหลัก' if dev.role=='MASTER' else 'ตัวสำรอง' }}</span></div>
                <div class="info-row"><span class="label">อุณหภูมิ:</span><span class="value">{{ dev.current_temp }} °C</span></div>
                <div class="info-row"><span class="label">ความชื้น:</span><span class="value">{{ dev.humidity }} %</span></div>
                <div class="info-row"><span class="label">แรงดันเฉลี่ย:</span><span class="value">{{ ((dev.v_l1_l2+dev.v_l2_l3+dev.v_l3_l1)/3)|round(1) }} V</span></div>
                <div class="info-row"><span class="label">กราวด์:</span><span class="value">{{ dev.gnd_resistance_ohm }} Ω / {{ dev.gnd_voltage_v }} V</span></div>
                {% if dev.fault_list|length > 0 %}
                <div style="margin-top:10px; padding-top:10px; border-top:1px dashed #fecaca;">
                    <span style="color:#dc2626; font-size:13px; font-weight:500;">⚠️ ปัญหา ({{ dev.fault_list|length }} รายการ):</span>
                    <ul style="margin-top:4px; padding-left:16px; font-size:12px; color:#b91c1c;">
                        {% for f in dev.fault_list %}<li>{{ f }}</li>{% endfor %}
                    </ul>
                </div>
                {% endif %}
                <div style="margin-top:10px; font-size:11px; color:#94a3b8;">อัปเดต: {{ dev.last_updated }}</div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>
</body>
</html>
    """, session=session, devices=DEVICE_LIST)

@app.route("/login")
def login_page():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เข้าสู่ระบบ — SAFE-ELEC</title>
<style>
*{margin:0; padding:0; box-sizing:border-box; font-family:sans-serif;}
body{background:linear-gradient(135deg,#1e40af,#3b82f6); min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px;}
.login-box{background:white; border-radius:16px; padding:32px 24px; width:100%; max-width:400px; box-shadow:0 10px 40px rgba(0,0,0,.15);}
.login-box h1{text-align:center; color:#1e40af; margin-bottom:24px; font-size:26px;}
.login-box p{text-align:center; color:#64748b; margin-bottom:24px; font-size:15px;}
.form-group{margin-bottom:18px;}
.form-group label{display:block; margin-bottom:6px; font-size:14px; color:#334155; font-weight:500;}
.form-group input{width:100%; padding:12px 14px; border:1px solid #cbd5e1; border-radius:8px; font-size:15px;}
.form-group input:focus{outline:none; border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.15);}
.btn{width:100%; padding:12px; background:#2563eb; color:white; border:none; border-radius:8px; font-size:16px; font-weight:600; cursor:pointer;}
.btn:hover{background:#1d4ed8;}
.error{color:#dc2626; text-align:center; margin-bottom:16px; font-size:14px;}
</style>
</head>
<body>
<div class="login-box">
    <h1>⚡ SAFE-ELEC</h1>
    <p>ระบบเฝ้าระวังความปลอดภัยระบบไฟฟ้า</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" action="/do-login">
        <div class="form-group">
            <label>ชื่อผู้ใช้</label>
            <input type="text" name="username" required autofocus>
        </div>
        <div class="form-group">
            <label>รหัสผ่าน</label>
            <input type="password" name="password" required>
        </div>
        <button type="submit" class="btn">เข้าสู่ระบบ</button>
    </form>
</div>
</body>
</html>
    """, error=request.args.get("error"))

@app.route("/do-login", methods=["POST"])
def do_login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    user = USER_DB.get(username)
    if user and user["password"] == password:
        session["username"] = username
        session["name"] = user["name"]
        session["customer_id"] = user["customer_id"]
        return redirect(url_for("index"))
    return redirect(url_for("login_page", error="ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/api/report-excel")
def api_report_excel():
    if "username" not in session:
        return redirect(url_for("login_page"))
    report = generate_excel_report()
    return send_file(
        io.BytesIO(report["data"]),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=report["name"]
    )

@app.route("/api/devices", methods=["GET"])
def api_get_devices():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    cust_id = session.get("customer_id", "ALL")
    if cust_id != "ALL":
        filtered = [d for d in DEVICE_LIST if d.get("customer_id") == cust_id]
        return jsonify({"devices": filtered})
    return jsonify({"devices": DEVICE_LIST})

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "ok",
        "system": CONFIG["SYSTEM_NAME"],
        "version": CONFIG["VERSION"],
        "timestamp": datetime.now().isoformat()
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
