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
    "cust0004": {"password": "123456", "name": "โรงงานผลิต ระยอง", "customer_id": "CUST-0004"},
}

# ==================== การตั้งค่าระบบ ====================
CONFIG = {
    "SYSTEM_NAME": "SAFE-ELEC",
    "VERSION": "3.0.0-FULL-DEPLOY",
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
    "SITE_TYPES": {
        "convenience": "ร้านสะดวกซื้อ", "shop": "ร้านค้าทั่วไป",
        "factory": "โรงงาน", "hotel": "โรงแรม", "office": "สำนักงาน",
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

# ==================== แมปชื่อฟิลด์ ====================
FIELD_MAP = {
    "id": "device_id", "esp_id": "device_id", "esp": "device_id",
    "site": "site_name", "cust": "customer_id", "role": "role",
    "is_master": "is_master", "active": "backup_active", "backup_active": "backup_active",
    "partner": "partner_online", "partner_online": "partner_online", "master": "is_master",
    "t": "current_temp", "temp": "current_temp", "temperature": "current_temp", "temp_max_c": "current_temp",
    "humi": "humidity", "rh": "humidity", "humidity_rh": "humidity",
    "v12": "v_l1_l2", "v23": "v_l2_l3", "v31": "v_l3_l1",
    "vl1l2": "v_l1_l2", "vl2l3": "v_l2_l3", "vl3l1": "v_l3_l1",
    "v_ab": "v_l1_l2", "v_bc": "v_l2_l3", "v_ca": "v_l3_l1",
    "i1": "a_l1", "i2": "a_l2", "i3": "a_l3",
    "il1": "a_l1", "il2": "a_l2", "il3": "a_l3",
    "ia": "a_l1", "ib": "a_l2", "ic": "a_l3", "in": "a_n",
    "power": "power_kw", "kw": "power_kw", "p_total": "power_kw", "power_total_kw": "power_kw",
    "vz1": "z1_v", "v_z1": "z1_v", "vzone1": "z1_v", "sub1_v": "z1_v",
    "az1": "z1_a", "a_z1": "z1_a", "azone1": "z1_a", "sub1_a": "z1_a",
    "wz1": "z1_w", "w_z1": "z1_w", "sub1_w": "z1_w",
    "vz2": "z2_v", "v_z2": "z2_v", "vzone2": "z2_v", "sub2_v": "z2_v",
    "az2": "z2_a", "a_z2": "z2_a", "azone2": "z2_a", "sub2_a": "z2_a",
    "wz2": "z2_w", "w_z2": "z2_w", "sub2_w": "z2_w",
    "vz3": "z3_v", "v_z3": "z3_v", "vzone3": "z3_v", "sub3_v": "z3_v",
    "az3": "z3_a", "a_z3": "z3_a", "azone3": "z3_a", "sub3_a": "z3_a",
    "wz3": "z3_w", "w_z3": "z3_w", "sub3_w": "z3_w",
    "gnd_r": "gnd_resistance_ohm", "ground_res": "gnd_resistance_ohm",
    "res_gnd": "gnd_resistance_ohm", "r_gnd": "gnd_resistance_ohm",
    "gnd_ohm": "gnd_resistance_ohm", "ground_resistance_ohm": "gnd_resistance_ohm",
    "gnd_v": "gnd_voltage_v", "ground_v": "gnd_voltage_v",
    "v_leak": "gnd_voltage_v", "v_gnd": "gnd_voltage_v",
    "leak_volt": "gnd_voltage_v", "ground_leak_voltage_v": "gnd_voltage_v",
    "wiring": "wiring_fault", "shutdown": "critical_shutdown",
    "psu_status": "power_status", "relay": "relay_state",
    "relay_state": "relay_state", "lock": "safety_lock",
    "safety_lock": "safety_lock",
    "sens_current": "sens_current",
    "sens_temp": "sens_temp",
    "sens_volt": "sens_volt",
    "sens_heat": "sens_heat",
    "sens_ground": "sens_ground",
}

# ==================== ข้อมูลอุปกรณ์ ====================
DEVICE_LIST = [
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    ("SAFE-001-BAK", "สำรอง — แผงหลัก อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
]

# ==================== แม่แบบข้อมูลอุปกรณ์ ====================
TEMPLATE = {
    "device_id": "", "site_name": "", "customer_id": "",
    "province": "", "site_type": "",
    "last_updated": "-", "last_seen": None,
    "is_online": False, "status_summary": "offline",
    "last_alert_sent": None,
    "role": "UNKNOWN", "is_master": False,
    "backup_active": False, "partner_online": True, "partner_id": "",
    "current_temp": 0.0, "humidity": 0.0, "power_status": "MAIN AC",
    "wiring_fault": False, "critical_shutdown": False,
    "relay_state": True, "safety_lock": False,
    "v_l1_l2": 380.0, "v_l2_l3": 380.0, "v_l3_l1": 380.0,
    "a_l1": 0.0, "a_l2": 0.0, "a_l3": 0.0, "a_n": 0.0,
    "power_kw": 0.0, "balance_3ph_ok": True,
    "z1_v": 220.0, "z1_a": 0.0, "z1_w": 0.0,
    "z2_v": 220.0, "z2_a": 0.0, "z2_w": 0.0,
    "z3_v": 220.0, "z3_a": 0.0, "z3_w": 0.0,
    "z_total_a": 0.0, "z_balance_ok": True,
    "gnd_resistance_ohm": 0.0, "gnd_voltage_v": 0.0, "gnd_system_ok": True,
    "sensors": {
        "temp": {"name": "อุณหภูมิตู้", "value": 0.0, "ok": None},
        "humidity": {"name": "ความชื้น", "value": 0.0, "ok": None},
        "comm": {"name": "สื่อสาร", "value": "ไม่เชื่อมต่อ", "ok": None},
        "psu": {"name": "แหล่งจ่ายภายใน", "value": "ตรวจสอบ", "ok": None},
        "esp": {"name": "อุปกรณ์ ESP", "value": "ไม่เชื่อมต่อ", "ok": None},
        "v_l1_l2": {"name": "แรงดัน L1-L2", "value": 0.0, "ok": None},
        "v_l2_l3": {"name": "แรงดัน L2-L3", "value": 0.0, "ok": None},
        "v_l3_l1": {"name": "แรงดัน L3-L1", "value": 0.0, "ok": None},
        "a_l1": {"name": "กระแสเฟส 1", "value": 0.0, "ok": None},
        "a_l2": {"name": "กระแสเฟส 2", "value": 0.0, "ok": None},
        "a_l3": {"name": "กระแสเฟส 3", "value": 0.0, "ok": None},
        "z1_v": {"name": "โซน1 แรงดัน", "value": 0.0, "ok": None},
        "z1_a": {"name": "โซน1 กระแส", "value": 0.0, "ok": None},
        "z2_v": {"name": "โซน2 แรงดัน", "value": 0.0, "ok": None},
        "z2_a": {"name": "โซน2 กระแส", "value": 0.0, "ok": None},
        "z3_v": {"name": "โซน3 แรงดัน", "value": 0.0, "ok": None},
        "z3_a": {"name": "โซน3 กระแส", "value": 0.0, "ok": None},
        "gnd_resist": {"name": "กราวด์-ความต้านทาน", "value": 0.0, "unit": "Ω", "ok": None},
        "gnd_volt": {"name": "กราวด์-แรงดันรั่ว", "value": 0.0, "unit": "V", "ok": None},
        "dualmode": {"name": "ระบบคู่ขนาน", "value": "รอข้อมูล", "ok": None},
        "sens_current": {"name": "เซ็นเซอร์กระแส", "value": "รอข้อมูล", "ok": None},
        "sens_temp": {"name": "เซ็นเซอร์อุณหภูมิ", "value": "รอข้อมูล", "ok": None},
        "sens_volt": {"name": "เซ็นเซอร์แรงดัน", "value": "รอข้อมูล", "ok": None},
        "sens_heat": {"name": "เซ็นเซอร์ความร้อน", "value": "รอข้อมูล", "ok": None},
        "sens_ground": {"name": "เซ็นเซอร์กราวด์", "value": "รอข้อมูล", "ok": None},
    },
    "fault_list": [], "alert_level": "normal",
}

# สร้างรายการอุปกรณ์
devices = []
for dev_id, site, cust, prov, stype in DEVICE_LIST:
    d = TEMPLATE.copy()
    d["device_id"] = dev_id
    d["site_name"] = site
    d["customer_id"] = cust
    d["province"] = prov
    d["site_type"] = stype
    devices.append(d)

# ==================== ฟังก์ชันส่งแจ้งเตือน ====================
def send_line_alert(message):
    token = CONFIG["ALERT"]["LINE_TOKEN"]
    if not token or not CONFIG["ALERT"]["ENABLED"]:
        print("[LINE] ข้ามส่ง: ยังไม่ได้ตั้งค่า Token หรือปิดใช้งาน")
        return False
    try:
        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": f"Bearer {token}"}
        data = {"message": f"\n{message}"}
        res = requests.post(url, headers=headers, data=data, timeout=15)
        if res.status_code == 200:
            print("[LINE] ส่งสำเร็จ ✅")
            return True
        else:
            print(f"[LINE] ส่งไม่สำเร็จ: รหัส {res.status_code} — {res.text}")
            return False
    except Exception as e:
        print(f"[LINE] ผิดพลาด: {type(e).__name__} — {e}")
        return False

def send_email_alert(subject, body, attach_file=None):
    cfg = CONFIG["ALERT"]
    if not cfg["EMAIL_TO"] or not cfg["SMTP_PASS"]:
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = cfg["EMAIL_FROM"]
        msg["To"] = cfg["EMAIL_TO"]
        msg["Subject"] = f"SAFE-ELEC: {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if attach_file:
            part = MIMEText(attach_file["data"], _subtype="csv", _charset="utf-8")
            part.add_header("Content-Disposition", f'attachment; filename="{attach_file["name"]}"')
            msg.attach(part)
        with smtplib.SMTP(cfg["SMTP_SERVER"], cfg["SMTP_PORT"], timeout=15) as server:
            server.starttls()
            server.login(cfg["EMAIL_FROM"], cfg["SMTP_PASS"])
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"[อีเมล] ส่งไม่สำเร็จ: {e}")
        return False

def should_send_alert(dev):
    if not CONFIG["ALERT"]["ENABLED"]:
        return False
    if dev["alert_level"] == "normal":
        return False
    if not dev["last_alert_sent"]:
        return True
    delay = CONFIG["ALERT"]["SEND_REPEAT_DELAY_MIN"] * 60
    elapsed = (datetime.now() - dev["last_alert_sent"]).total_seconds()
    return elapsed > delay

def build_alert_message(dev):
    status_text = {
        "offline": "⚠️ ขาดการติดต่อ",
        "warning": "⚠️ มีสิ่งต้องเฝ้าระวัง",
        "critical": "🔴 ปัญหาร้ายแรง"
    }.get(dev["alert_level"], "แจ้งเตือน")
    backup_note = ""
    if dev.get("backup_active"):
        backup_note = "\n🛡️ ระบบสำรองกำลังทำงานแทน"
    if not dev.get("partner_online", True):
        backup_note = "\n⚠️ ไม่พบคู่ขนาน — ตรวจสอบการเชื่อมต่อ"
    msg = f"""
{'='*35}
📢 {status_text}
📌 อุปกรณ์: {dev['device_id']}
🏢 สถานที่: {dev['site_name']}
📍 ลูกค้า: {dev['customer_id']}
🕐 เวลา: {dev['last_updated']}{backup_note}

รายการปัญหา:
"""
    for f in dev["fault_list"]:
        msg += f"  • {f}\n"
    msg += f"\nดูรายละเอียด: {request.host_url}\n{'='*35}"
    return msg

def trigger_alert(dev):
    if not should_send_alert(dev):
        return
    msg = build_alert_message(dev)
    line_ok = send_line_alert(msg)
    status_text = {
        "offline": "ขาดการติดต่อ",
        "warning": "เฝ้าระวัง",
        "critical": "แจ้งเตือนรุนแรง"
    }.get(dev["alert_level"], "แจ้งเตือน")
    email_ok = send_email_alert(f"{dev['device_id']} — {status_text}", msg)
    if line_ok or email_ok:
        dev["last_alert_sent"] = datetime.now()
        print(f"✅ ส่งแจ้งเตือนสำเร็จ: {dev['device_id']}")

# ==================== สร้างรายงาน Excel ====================
def generate_excel_report():
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    ws = workbook.add_worksheet("สรุปภาพรวม")
    
    header_format = workbook.add_format({'bold': True, 'bg_color': '#1e40af', 'color': '#FFFFFF', 'align': 'center', 'valign': 'vcenter'})
    header_format.set_text_wrap()
    normal = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
    left_align = workbook.add_format({'text_wrap': True, 'align': 'left', 'valign': 'vcenter'})
    red_text = workbook.add_format({'font_color': '#dc2626', 'bold': True, 'align': 'center'})
    orange_text = workbook.add_format({'font_color': '#f97316', 'bold': True, 'align': 'center'})
    green_text = workbook.add_format({'font_color': '#16a34a', 'bold': True, 'align': 'center'})
    gray_text = workbook.add_format({'font_color': '#6b7280', 'align': 'center'})

    headers = [
        "รหัสอุปกรณ์", "ชื่อสถานที่", "รหัสลูกค้า", "จังหวัด", "ประเภทสถานที่",
        "บทบาท", "สถานะออนไลน์", "ระดับแจ้งเตือน", "เวลาอัปเดตล่าสุด",
        "อุณหภูมิ (°C)", "ความชื้น (%)", "สถานะแหล่งจ่าย",
        "V L1-L2 (V)", "V L2-L3 (V)", "V L3-L1 (V)",
        "A L1 (A)", "A L2 (A)", "A L3 (A)", "A N (A)",
        "กำลังไฟฟ้า (kW)", "ความสมดุล 3เฟส",
        "โซน1 V(V)", "โซน1 A(A)", "โซน1 kW",
        "โซน2 V(V)", "โซน2 A(A)", "โซน2 kW",
        "โซน3 V(V)", "โซน3 A(A)", "โซน3 kW",
        "กราวด์ ความต้านทาน (Ω)", "กราวด์ แรงดันรั่ว (V)", "สถานะกราวด์",
        "จำนวนปัญหา", "รายการปัญหา"
    ]
    
    for col, h in enumerate(headers):
        ws.write(0, col, h, header_format)

    for row, d in enumerate(devices, start=1):
        role_label = d.get("role", "-")
        if role_label == "MASTER":
            role_label = "ตัวหลัก"
        elif role_label == "BACKUP":
            role_label = "ตัวสำรอง"
        if d.get("backup_active"):
            role_label += " (ทำงานแทน)"
        
        online_text = "✅ ออนไลน์" if d["is_online"] else "❌ ขาดการติดต่อ"
        online_fmt = green_text if d["is_online"] else red_text
        
        alert_text = {
            "normal": "ปกติ",
            "warning": "เฝ้าระวัง",
            "critical": "อันตราย",
            "offline": "ขาดการติดต่อ"
        }.get(d["alert_level"], "-")
        alert_fmt = {
            "normal": green_text,
            "warning": orange_text,
            "critical": red_text,
            "offline": gray_text
        }.get(d["alert_level"], normal)
        
        balance_ok = d.get("balance_3ph_ok", True)
        balance_text = "ปกติ" if balance_ok else "ไม่สมดุล"
        balance_fmt = green_text if balance_ok else orange_text
        
        gnd_ok = d.get("gnd_system_ok", True)
        gnd_val = d.get("gnd_resistance_ohm", 0)
        if gnd_val <= 0:
            gnd_status = "รอข้อมูล"
            gnd_fmt = gray_text
        elif gnd_ok:
            gnd_status = "ปกติ"
            gnd_fmt = green_text
        else:
            gnd_status = "ผิดปกติ"
            gnd_fmt = red_text

        fault_count = len(d.get('fault_list', []))
        fault_text = "; ".join(d.get('fault_list', [])) if fault_count > 0 else "-"

        ws.write(row, 0, d["device_id"], left_align)
        ws.write(row, 1, d["site_name"], left_align)
        ws.write(row, 2, d["customer_id"], normal)
        ws.write(row, 3, d.get("province", "-"), normal)
        ws.write(row, 4, CONFIG["SITE_TYPES"].get(d.get("site_type",""), d.get("site_type","")), normal)
        ws.write(row, 5, role_label, normal)
        ws.write(row, 6, online_text, online_fmt)
        ws.write(row, 7, alert_text, alert_fmt)
        ws.write(row, 8, d.get("last_updated", "-"), normal)
        ws.write(row, 9, d.get("current_temp", 0), normal)
        ws.write(row, 10, d.get("humidity", 0), normal)
        ws.write(row, 11, d.get("power_status", "-"), normal)
        ws.write(row, 12, d.get("v_l1_l2", 0), normal)
        ws.write(row, 13, d.get("v_l2_l3", 0), normal)
        ws.write(row, 14, d.get("v_l3_l1", 0), normal)
        ws.write(row, 15, d.get("a_l1", 0), normal)
        ws.write(row, 16, d.get("a_l2", 0), normal)
        ws.write(row, 17, d.get("a_l3", 0), normal)
        ws.write(row, 18, d.get("a_n", 0), normal)
        ws.write(row, 19, d.get("power_kw", 0), normal)
        ws.write(row, 20, balance_text, balance_fmt)
        ws.write(row, 21, d.get("z1_v", 0), normal)
        ws.write(row, 22, d.get("z1_a", 0), normal)
        ws.write(row, 23, d.get("z1_w", 0), normal)
        ws.write(row, 24, d.get("z2_v", 0), normal)
        ws.write(row, 25, d.get("z2_a", 0), normal)
        ws.write(row, 26, d.get("z2_w", 0), normal)
        ws.write(row, 27, d.get("z3_v", 0), normal)
        ws.write(row, 28, d.get("z3_a", 0), normal)
        ws.write(row, 29, d.get("z3_w", 0), normal)
        ws.write(row, 30, d.get("gnd_resistance_ohm", 0), normal)
        ws.write(row, 31, d.get("gnd_voltage_v", 0), normal)
        ws.write(row, 32, gnd_status, gnd_fmt)
        ws.write(row, 33, fault_count, normal)
        ws.write(row, 34, fault_text, left_align)
    
    col_widths = [16, 28, 14, 12, 14, 16, 14, 12, 18, 12, 12, 14,
                  12, 12, 12, 10, 10, 10, 10, 12, 14, 10, 10, 10,
                  10, 10, 10, 10, 10, 10, 16, 14, 12, 14, 40]
    for i, w in enumerate(col_widths):
        ws.set_column(i, i, w)
    
    workbook.close()
    output.seek(0)
    return {
        "data": output.read(),
        "name": f"SAFE-ELEC-Report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    }

# ==================== ฟังก์ชันตรวจสอบระบบ ====================
def check_ground(dev):
    S = CONFIG["STANDARD"]
    faults = []
    gr = dev["gnd_resistance_ohm"]
    dev["sensors"]["gnd_resist"]["value"] = gr
    if gr <= 0:
        dev["sensors"]["gnd_resist"]["ok"] = None
    elif gr > S["GND_RES_WARN"]:
        dev["sensors"]["gnd_resist"]["ok"] = False
        faults.append(f"🔴 กราวด์ไม่ดี! {gr}Ω (มาตรฐาน ≤ {S['GND_RES_OK']}Ω)")
        dev["gnd_system_ok"] = False
    elif gr > S["GND_RES_OK"]:
        dev["sensors"]["gnd_resist"]["ok"] = False
        faults.append(f"⚠️ กราวด์ควรปรับปรุง: {gr}Ω")
    else:
        dev["sensors"]["gnd_resist"]["ok"] = True
    gv = dev["gnd_voltage_v"]
    dev["sensors"]["gnd_volt"]["value"] = gv
    if gv <= 0:
        dev["sensors"]["gnd_volt"]["ok"] = None
    elif gv > S["GND_V_OK"]:
        dev["sensors"]["gnd_volt"]["ok"] = False
        faults.append(f"🔴 แรงดันรั่วสูง: {gv}V (ปกติ ≤ {S['GND_V_OK']}V)")
        dev["gnd_system_ok"] = False
    else:
        dev["sensors"]["gnd_volt"]["ok"] = True
    return faults

def check_balance(i1, i2, i3):
    total = i1 + i2 + i3
    if total <= 0: return True
    avg = total / 3
    for v in [i1, i2, i3]:
        if abs(v - avg) > CONFIG["STANDARD"]["BALANCE_MAX_A"]: return False
        if avg > 0 and abs(v - avg) / avg * 100 > CONFIG["STANDARD"]["BALANCE_MAX_PCT"]: return False
    return True

def check_dual_backup(dev):
    faults = []
    role = dev.get("role", "UNKNOWN")
    is_active = dev.get("backup_active", False)
    partner_online = dev.get("partner_online", True)
    if role == "MASTER":
        dev["sensors"]["dualmode"]["value"] = "ตัวหลัก"
        dev["sensors"]["dualmode"]["ok"] = partner_online
        if not partner_online:
            faults.append("⚠️ ไม่พบตัวสำรอง — ตรวจสอบการเชื่อมต่อ")
    elif role == "BACKUP":
        if is_active:
            dev["sensors"]["dualmode"]["value"] = "ทำงานแทนหลัก ⚡"
            dev["sensors"]["dualmode"]["ok"] = False
            faults.append("🔴 ตัวหลักขาดการติดต่อ — สำรองรับหน้าที่แล้ว")
        else:
            dev["sensors"]["dualmode"]["value"] = "คอยเฝ้าดู"
            dev["sensors"]["dualmode"]["ok"] = True
    else:
        dev["sensors"]["dualmode"]["value"] = "ไม่ระบุ"
        dev["sensors"]["dualmode"]["ok"] = None
    return faults

def check_all(dev):
    S = CONFIG["STANDARD"]
    faults = check_ground(dev)
    faults += check_dual_backup(dev)
    sensors_list = [
        ("sens_current", "เซ็นเซอร์กระแส"),
        ("sens_temp", "เซ็นเซอร์อุณหภูมิ"),
        ("sens_volt", "เซ็นเซอร์แรงดัน"),
        ("sens_heat", "เซ็นเซอร์ความร้อน"),
        ("sens_ground", "เซ็นเซอร์กราวด์"),
    ]
    
    for key, name in sensors_list:
        val = dev["sensors"][key]["value"]
        if val == "ปกติ" or val is True:
            dev["sensors"][key]["ok"] = True
            dev["sensors"][key]["value"] = "ปกติ"
        elif val in ["เสีย", "ผิดปกติ", False]:
            dev["sensors"][key]["ok"] = False
            dev["sensors"][key]["value"] = "เสีย"
            faults.append(f"❌ {name} ทำงานผิดปกติ")
        else:
            dev["sensors"][key]["ok"] = None
            dev["sensors"][key]["value"] = "รอข้อมูล"
    
    if dev["is_online"]:
        dev["sensors"]["esp"]["value"] = "เชื่อมต่อปกติ"
        dev["sensors"]["esp"]["ok"] = True
        dev["sensors"]["comm"]["value"] = "ปกติ"
        dev["sensors"]["comm"]["ok"] = True
        dev["sensors"]["psu"]["value"] = "ปกติ"
        dev["sensors"]["psu"]["ok"] = True
    else:
        dev["sensors"]["esp"]["value"] = "ไม่เชื่อมต่อ"
        dev["sensors"]["esp"]["ok"] = None
        dev["sensors"]["comm"]["value"] = "ไม่เชื่อมต่อ"
        dev["sensors"]["comm"]["ok"] = None
        dev["sensors"]["psu"]["value"] = "ตรวจสอบ"
        dev["sensors"]["psu"]["ok"] = None
    
    t = dev["current_temp"]
    dev["sensors"]["temp"]["value"] = t
    if not dev["is_online"]:
        dev["sensors"]["temp"]["ok"] = None
    elif t < S["TEMP_MIN"] or t > S["TEMP_MAX"]:
        dev["sensors"]["temp"]["ok"] = False
        faults.append(f"❌ อุณหภูมิผิดปกติ: {t}°C")
    elif t >= S["TEMP_ALERT"]:
        dev["sensors"]["temp"]["ok"] = False
        faults.append(f"⚠️ อุณหภูมิสูง: {t}°C")
    else:
        dev["sensors"]["temp"]["ok"] = True
    
    h = dev["humidity"]
    dev["sensors"]["humidity"]["value"] = h
    if not dev["is_online"] or h == 0:
        dev["sensors"]["humidity"]["ok"] = None
    else:
        dev["sensors"]["humidity"]["ok"] = S["HUMI_MIN"] <= h <= S["HUMI_MAX"]
    
    for k, v in [("v_l1_l2", dev["v_l1_l2"]), ("v_l2_l3", dev["v_l2_l3"]), ("v_l3_l1", dev["v_l3_l1"])]:
        dev["sensors"][k]["value"] = v
        if not dev["is_online"] or v == 0:
            dev["sensors"][k]["ok"] = None
        else:
            dev["sensors"][k]["ok"] = S["V3_MIN"] <= v <= S["V3_MAX"]
    
    for k, v in [("a_l1", dev["a_l1"]), ("a_l2", dev["a_l2"]), ("a_l3", dev["a_l3"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = None if not dev["is_online"] or v == 0 else True
    
    for k, v in [("z1_v", dev["z1_v"]), ("z2_v", dev["z2_v"]), ("z3_v", dev["z3_v"])]:
        dev["sensors"][k]["value"] = v
        if not dev["is_online"] or v == 0:
            dev["sensors"][k]["ok"] = None
        else:
            dev["sensors"][k]["ok"] = S["V1_MIN"] <= v <= S["V1_MAX"]
    
    for k, v in [("z1_a", dev["z1_a"]), ("z2_a", dev["z2_a"]), ("z3_a", dev["z3_a"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = None if not dev["is_online"] or v == 0 else True
    
    dev["balance_3ph_ok"] = check_balance(dev["a_l1"], dev["a_l2"], dev["a_l3"])
    dev["z_total_a"] = round(dev["z1_a"] + dev["z2_a"] + dev["z3_a"], 2)
    dev["z_balance_ok"] = check_balance(dev["z1_a"], dev["z2_a"], dev["z3_a"])
    
    if dev["is_online"] and not dev["balance_3ph_ok"]:
        faults.append("⚠️ ระบบ 380V ไม่สมดุล")
    if dev["is_online"] and not dev["z_balance_ok"] and dev["z_total_a"] > 0:
        faults.append("⚠️ ระบบ 220V ไม่สมดุล")
    
    critical = any("🔴" in f for f in faults)
    warning = any("⚠️" in f for f in faults)
    if not dev["is_online"]:
        dev["status_summary"] = "offline"
        dev["alert_level"] = "critical"
    elif critical:
        dev["status_summary"] = "critical"
        dev["alert_level"] = "critical"
    elif warning:
        dev["status_summary"] = "warning"
        dev["alert_level"] = "warning"
    else:
        dev["status_summary"] = "online"
        dev["alert_level"] = "normal"
    
    dev["fault_list"] = faults
    trigger_alert(dev)
    return dev

# ==================== Middleware ====================
@app.before_request
def update_online():
    now = datetime.now()
    for d in devices:
        if d["last_seen"]:
            sec = (now - d["last_seen"]).total_seconds()
            d["is_online"] = sec < CONFIG["STANDARD"]["OFFLINE_SEC"]
        else:
            d["is_online"] = False
        check_all(d)

# ==================== API Routes ====================
@app.route("/api/data", methods=["GET"])
def get_data():
    dev_id = request.args.get("device_id", "SAFE-001")
    for d in devices:
        if d["device_id"] == dev_id:
            return jsonify(d)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/data", methods=["POST"])
def receive():
    data = request.get_json(force=True) or {}
    now = datetime.now()
    normalized = {}
    for key, value in data.items():
        key_low = key.lower().strip()
        std_key = FIELD_MAP.get(key_low, key_low)
        normalized[std_key] = value
    dev_id = normalized.get("device_id", "")
    if not dev_id:
        return jsonify({"ok": False, "error": "ต้องระบุ device_id"}), 400
    d = next((dev for dev in devices if dev["device_id"] == dev_id), None)
    if not d:
        return jsonify({"ok": False, "error": f"ไม่พบอุปกรณ์: {dev_id}"}), 404
    for k, v in normalized.items():
        if k in d and k not in ["sensors", "fault_list"]:
            d[k] = v
    d["last_updated"] = now.strftime("%H:%M:%S")
    d["last_seen"] = now
    d["is_online"] = True
    d = check_all(d)
    return jsonify({
        "ok": True,
        "device_id": dev_id,
        "role": d["role"],
        "backup_active": d["backup_active"],
        "status": d["status_summary"],
        "received_fields": len(normalized)
    }), 200

@app.route("/api/devices")
def get_devices():
    my_cust = session.get("cust_id", "")
    if my_cust == "ALL" or not my_cust:
        return jsonify(devices)
    return jsonify([d for d in devices if d["customer_id"] == my_cust])

@app.route("/api/report-excel")
def download_report():
    if "username" not in session:
        return redirect("/login")
    report = generate_excel_report()
    return send_file(
        io.BytesIO(report["data"]),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=report["name"]
    )

# ==================== หน้าเข้าสู่ระบบ ====================
@app.route("/login")
def login():
    err = request.args.get("err", "")
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เข้าสู่ระบบ — SAFE-ELEC</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif;
        color: #fff;
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%);
        position: relative;
        overflow-x: hidden;
    }
    .circuit-bg {
        position: fixed; inset: 0;
        background-image: radial-gradient(circle at 20% 30%, rgba(6,182,212,.08) 0%, transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(16,185,129,.08) 0%, transparent 40%);
        z-index: -2;
    }
    .circuit-lines {
        position: fixed; inset: 0; z-index: -1; opacity: 0.4;
        background-image: linear-gradient(90deg, rgba(6,182,212,.3) 1px, transparent 1px),
        linear-gradient(rgba(6,182,212,.3) 1px, transparent 1px);
        background-size: 60px 60px;
        mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
        -webkit-mask-image: radial-gradient(ellipse at center, black 40%, transparent 80%);
    }
    .container { width: 100%; max-width: 440px; padding: 24px; position: relative; z-index: 1; }
    .login-card {
        background: linear-gradient(135deg, rgba(30,41,59,.75), rgba(15,23,42,.8));
        border-radius: 24px; padding: 36px 28px;
        box-shadow: 0 0 0 1px rgba(6,182,212,.15), 0 20px 60px rgba(0,0,0,.4);
        backdrop-filter: blur(12px);
    }
    .logo-box {
        background: linear-gradient(145deg, #1E293B, #0F172A);
        border-radius: 16px; padding: 28px 20px; text-align: center; margin-bottom: 32px;
    }
    .logo-img { width: 180px; margin-bottom: 16px; }
    .company-name { font-size: 22px; font-weight: 600; color: #F1F5F9; margin-bottom: 6px; }
    .company-en { font-size: 13px; color: #94A3B8; letter-spacing: 1px; }
    .header { text-align: center; margin-bottom: 32px; }
    .header h1 {
        font-size: 26px; background: linear-gradient(90deg, #22D3EE, #34D399);
        -webkit-background-clip: text; color: transparent;
    }
    .header p { color: #94A3B8; font-size: 15px; margin-top: 8px; }
    .form-group { margin-bottom: 20px; }
    .input-wrapper {
        display: flex; align-items: center; background: rgba(15,23,42,.6);
        border-radius: 12px; border: 1px solid rgba(6,182,212,.25); padding: 0 18px;
    }
    .input-wrapper:focus-within { border-color: rgba(6,182,212,.7); }
    .input-icon { color: #22D3EE; font-size: 18px; }
    input {
        width: 100%; padding: 16px 12px; background: transparent; border: none;
        outline: none; color: #F1F5F9; font-size: 16px;
    }
    input::placeholder { color: #64748B; }
    .btn-login {
        width: 100%; padding: 16px; border: none; border-radius: 12px; font-size: 18px;
        font-weight: 600; color: #0F172A;
        background: linear-gradient(90deg, #34D399, #22D3EE); cursor: pointer;
        transition: transform .2s; margin-top: 8px;
    }
    .btn-login:hover { transform: translateY(-2px); }
    .error-box {
        background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.3);
        color: #FCA5A5; padding: 12px; border-radius: 8px; text-align: center;
        margin-bottom: 20px; font-size: 14px;
    }
    @media (max-width: 480px) {
        .container { padding: 16px; }
        .login-card { padding: 28px 20px; }
        .header h1 { font-size: 22px; }
    }
</style>
</head>
<body>
    <div class="circuit-bg"></div>
    <div class="circuit-lines"></div>
    <div class="container">
        <div class="login-card">
            <div class="logo-box">
                <img src="https://raw.githubusercontent.com/kidairhotmailcom-ui/safeelec-mini-server/main/865611D1-AE49-4F4F-9460-CA01F09BDD8E.png" 
                     alt="Logo" class="logo-img" onerror="this.style.display='none'">
                <div class="company-name">บริษัท เพชรนาคา</div>
                <div class="company-en">PETCHNAKA SYSTEM WORK CO.,LTD.</div>
            </div>
            <div class="header">
                <h1>🔐 เข้าสู่ระบบ SAFE-ELEC</h1>
                <p>กรุณากรอกข้อมูลเพื่อเข้าใช้งานระบบ</p>
            </div>
            {% if err %}<div class="error-box">{{ err }}</div>{% endif %}
            <form method="post" action="/do_login">
                <div class="form-group">
                    <div class="input-wrapper">
                        <span class="input-icon">👤</span>
                        <input type="text" name="user" placeholder="ชื่อผู้ใช้" required autofocus>
                    </div>
                </div>
                <div class="form-group">
                    <div class="input-wrapper">
                        <span class="input-icon">🔒</span>
                        <input type="password" name="pwd" placeholder="รหัสผ่าน" required>
                    </div>
                </div>
                <button type="submit" class="btn-login">เข้าสู่ระบบ</button>
            </form>
        </div>
    </div>
</body>
</html>
    """, err=err)

@app.route("/do_login", methods=["POST"])
def do_login():
    user = request.form.get("user", "").strip()
    pwd = request.form.get("pwd", "")
    if user in USER_DB and USER_DB[user]["password"] == pwd:
        session["username"] = user
        session["cust_id"] = USER_DB[user]["customer_id"]
        session["name"] = USER_DB[user]["name"]
        return redirect("/")
    return redirect("/login?err=ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ==================== หน้าหลัก/แดชบอร์ด ====================
@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="
