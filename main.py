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
import json  

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "SAFE-ELEC-2026-SECRET-KEY-CHANGE-ME-PLEASE")
CORS(app, supports_credentials=True)

USER_DB = {
    "admin": {"password": "123456", "name": "ผู้ดูแลระบบ", "customer_id": "ALL"},
    "cust0891": {"password": "123456", "name": "อาคารหลัก ขอนแก่น", "customer_id": "CUST-0891"},
    "cust0002": {"password": "123456", "name": "สาขาเชียงใหม่", "customer_id": "CUST-0002"},
    "cust0004": {"password": "123456", "name": "โรงงานผลิต ระยอง", "customer_id": "CUST-0004"},
}

CONFIG = {
    "SYSTEM_NAME": "SAFE-ELEC Smart Energy System",
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
    },

   "ENERGY": {
        "ENABLED": True,
        "DAILY_TARGET_KWH": 4.0,
        "ELECTRICITY_RATE": 4.22,
        "PF": 0.9,
        "WARNING_PCT": 105,
        "LOSS_CURRENT_THRESHOLD": 0.2,
    } 
}
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

DEVICE_LIST = [
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    ("SAFE-001-BAK", "สำรอง — แผงหลัก อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
]

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
    "energy_today_kwh": 0.0,
    "energy_yesterday_kwh": 0.0,
    "energy_cost_today": 0.0,
    "energy_target_kwh": 4.0,
    "energy_percent_of_target": 0.0,
    "energy_trend": "-",
    "energy_status": "normal",
    "energy_loss_kwh": 0.0,
    "energy_alerts": [],
    "energy_history": [],
    }

devices = []
for dev_id, site, cust, prov, stype in DEVICE_LIST:
    d = TEMPLATE.copy()
    d["device_id"] = dev_id
    d["site_name"] = site
    d["customer_id"] = cust
    d["province"] = prov
    d["site_type"] = stype
    devices.append(d)

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

def generate_excel_report():
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    
    # === รูปแบบ ===
    fmt_header = workbook.add_format({'bold': True, 'bg_color': '#1e40af', 'color': '#ffffff', 'align': 'center', 'valign': 'vcenter', 'text_wrap': True})
    fmt_center = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
    fmt_left = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
    fmt_online = workbook.add_format({'color': '#22c55e', 'bold': True, 'align': 'center'})
    fmt_offline = workbook.add_format({'color': '#ef4444', 'bold': True, 'align': 'center'})
    fmt_normal = workbook.add_format({'align': 'center', 'valign': 'vcenter'})
    fmt_red = workbook.add_format({'bg_color': '#fef2f2', 'font_color': '#dc2626', 'align': 'center'})
    fmt_yellow = workbook.add_format({'bg_color': '#fffbeb', 'font_color': '#d97706', 'align': 'center'})
    fmt_green = workbook.add_format({'bg_color': '#f0fdf4', 'font_color': '#16a34a', 'align': 'center'})

    # ===== แผ่น 1: สรุปภาพรวม =====
    ws1 = workbook.add_worksheet("สรุปภาพรวม")
    headers_summary = [
        "วันที่", "เวลา", "รหัสอุปกรณ์", "สถานที่ติดตั้ง", "ลูกค้า", "จังหวัด",
        "บทบาท", "สถานะเชื่อมต่อ", "สถานะระบบ",
        "อุณหภูมิ (°C)", "ความชื้น (%)",
        "กราวด์ R (Ω)", "กราวด์ V (V)",
        "จำนวนปัญหา", "รายการปัญหา"
    ]
    for col, h in enumerate(headers_summary):
        ws1.write(0, col, h, fmt_header)
        ws1.set_column(col, col, 16)
    
    for row, d in enumerate(devices, start=1):
        status_fmt = fmt_green if d["alert_level"]=="normal" else fmt_yellow if d["alert_level"]=="warning" else fmt_red
        online_fmt = fmt_online if d["is_online"] else fmt_offline
        role_label = d.get("role", "-")
        if d.get("backup_active"):
            role_label += " (ทำงานแทน)"
        
        ws1.write(row, 0, datetime.now().strftime("%d/%m/%Y"), fmt_center)
        ws1.write(row, 1, d.get("last_updated", "-"), fmt_center)
        ws1.write(row, 2, d["device_id"], fmt_left)
        ws1.write(row, 3, d["site_name"], fmt_left)
        ws1.write(row, 4, d.get("customer_id", "-"), fmt_center)
        ws1.write(row, 5, d.get("province", "-"), fmt_center)
        ws1.write(row, 6, role_label, fmt_center)
        ws1.write(row, 7, "✅ ออนไลน์" if d["is_online"] else "❌ ออฟไลน์", online_fmt)
        ws1.write(row, 8, d["status_summary"], status_fmt)
        ws1.write(row, 9, d.get("current_temp", "-"), fmt_center)
        ws1.write(row, 10, d.get("humidity", "-"), fmt_center)
        ws1.write(row, 11, d.get("gnd_resistance_ohm", "-"), fmt_center)
        ws1.write(row, 12, d.get("gnd_voltage_v", "-"), fmt_center)
        ws1.write(row, 13, len(d.get("fault_list", [])), fmt_center)
        ws1.write(row, 14, "; ".join(d.get("fault_list", ["-"])), fmt_left)

    # ===== แผ่น 2: ข้อมูลเชิงลึก =====
    ws2 = workbook.add_worksheet("ข้อมูลเชิงลึก")
    headers_detail = [
        "รหัส", "สถานที่", "แรงดัน L1-L2 (V)", "แรงดัน L2-L3 (V)", "แรงดัน L3-L1 (V)",
        "กระแส L1 (A)", "กระแส L2 (A)", "กระแส L3 (A)", "กำลังไฟฟ้า (kW)",
        "โซน1 V", "โซน1 A", "โซน2 V", "โซน2 A", "โซน3 V", "โซน3 A",
        "ระบบ 3 เฟส", "ระบบโซน", "แหล่งจ่าย", "รีเลย์", "ล็อกความปลอดภัย"
    ]
    for col, h in enumerate(headers_detail):
        ws2.write(0, col, h, fmt_header)
        ws2.set_column(col, col, 14)
    
    for row, d in enumerate(devices, start=1):
        ws2.write(row, 0, d["device_id"], fmt_left)
        ws2.write(row, 1, d["site_name"], fmt_left)
        ws2.write(row, 2, d.get("v_l1_l2", "-"), fmt_center)
        ws2.write(row, 3, d.get("v_l2_l3", "-"), fmt_center)
        ws2.write(row, 4, d.get("v_l3_l1", "-"), fmt_center)
        ws2.write(row, 5, d.get("a_l1", "-"), fmt_center)
        ws2.write(row, 6, d.get("a_l2", "-"), fmt_center)
        ws2.write(row, 7, d.get("a_l3", "-"), fmt_center)
        ws2.write(row, 8, d.get("power_kw", "-"), fmt_center)
        ws2.write(row, 9, d.get("z1_v", "-"), fmt_center)
        ws2.write(row, 10, d.get("z1_a", "-"), fmt_center)
        ws2.write(row, 11, d.get("z2_v", "-"), fmt_center)
        ws2.write(row, 12, d.get("z2_a", "-"), fmt_center)
        ws2.write(row, 13, d.get("z3_v", "-"), fmt_center)
        ws2.write(row, 14, d.get("z3_a", "-"), fmt_center)
        ws2.write(row, 15, "✅ ปกติ" if d.get("balance_3ph_ok") else "⚠️ ไม่สมดุล", fmt_center)
        ws2.write(row, 16, "✅ ปกติ" if d.get("z_balance_ok") else "⚠️ ไม่สมดุล", fmt_center)
        ws2.write(row, 17, d.get("power_status", "-"), fmt_center)
        ws2.write(row, 18, "ON" if d.get("relay_state") else "OFF", fmt_center)
        ws2.write(row, 19, "ล็อก" if d.get("safety_lock") else "ปกติ", fmt_center)

    # ===== แผ่น 3: สถานะเซ็นเซอร์ =====
    ws3 = workbook.add_worksheet("สถานะเซ็นเซอร์")
    headers_sensor = ["รหัสอุปกรณ์", "ชื่อสถานที่", "เซ็นเซอร์", "ค่าที่วัดได้", "สถานะ"]
    for col, h in enumerate(headers_sensor):
        ws3.write(0, col, h, fmt_header)
        ws3.set_column(col, col, 22)
    
    row_num = 1
    for d in devices:
        for key, s in d.get("sensors", {}).items():
            status_text = "✅ ปกติ" if s.get("ok") is True else "❌ ผิดปกติ" if s.get("ok") is False else "⏳ รอข้อมูล"
            status_fmt = fmt_green if s.get("ok") is True else fmt_red if s.get("ok") is False else fmt_yellow
            ws3.write(row_num, 0, d["device_id"], fmt_left)
            ws3.write(row_num, 1, d["site_name"], fmt_left)
            ws3.write(row_num, 2, s.get("name", key), fmt_left)
            ws3.write(row_num, 3, s.get("value", "-"), fmt_center)
            ws3.write(row_num, 4, status_text, status_fmt)
            row_num += 1

    workbook.close()
    output.seek(0)
    return {
        "data": output.read(),
        "name": f"SAFE-ELEC-Report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    }

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
def calc_power(voltage, current, pf=0.9):
    return round((voltage * current * pf) / 1000, 3)

def update_device_energy(dev, hours=1):
    E = CONFIG["ENERGY"]
    if not E["ENABLED"] or not dev.get("is_online", False):
        return

    z1_kw = calc_power(dev["z1_v"], dev["z1_a"], E["PF"])
    z2_kw = calc_power(dev["z2_v"], dev["z2_a"], E["PF"])
    z3_kw = calc_power(dev["z3_v"], dev["z3_a"], E["PF"])
    total_kw = round(z1_kw + z2_kw + z3_kw, 3)
    
    added_kwh = round(total_kw * hours, 3)
    dev["energy_today_kwh"] = round(dev["energy_today_kwh"] + added_kwh, 3)
    dev["energy_cost_today"] = round(dev["energy_today_kwh"] * E["ELECTRICITY_RATE"], 2)
    
    tgt = dev["energy_target_kwh"]
    dev["energy_percent_of_target"] = round((dev["energy_today_kwh"] / tgt) * 100, 1) if tgt > 0 else 0
    
    if dev["energy_percent_of_target"] > E["WARNING_PCT"]:
        dev["energy_status"] = "🔴 สูงกว่าเป้าหมาย"
    elif dev["energy_percent_of_target"] < 95:
        dev["energy_status"] = "🟢 ประหยัดดี"
    else:
        dev["energy_status"] = "🟡 ปกติ"
    
    if dev["energy_today_kwh"] > dev["energy_yesterday_kwh"]:
        dev["energy_trend"] = "📈 เพิ่มขึ้น"
    elif dev["energy_today_kwh"] < dev["energy_yesterday_kwh"]:
        dev["energy_trend"] = "📉 ลดลง"
    else:
        dev["energy_trend"] = "➡️ คงที่"
    
    dev["energy_alerts"] = []
    for name, v, a in [
        ("โซน1", dev["z1_v"], dev["z1_a"]),
        ("โซน2", dev["z2_v"], dev["z2_a"]),
        ("โซน3", dev["z3_v"], dev["z3_a"])
    ]:
        if 0 < a < E["LOSS_CURRENT_THRESHOLD"] * 5:
            loss_kwh = round(calc_power(v, a) * 24, 2)
            if loss_kwh > 0.01:
                dev["energy_alerts"].append(f"⚠️ {name}: พบกระแสรั่ว สูญเสีย ~{loss_kwh} kWh/วัน")

def check_all(dev):
    S = CONFIG["STANDARD"]
    faults = check_ground(dev)
    faults += check_dual_backup(dev)
    update_device_energy(dev)  
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

@app.before_request
def check_login():
    if request.path in ["/", "/login", "/do_login", "/logout", "/api/data", "/api/devices", "/api/report-excel"]:
        return
    if "username" not in session:
        return redirect("/login")

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

# ===== หน้าแรก =====
@app.route("/")
def home():
    if "username" in session:
        return redirect("/dashboard")
    return redirect("/login")

@app.route("/api/data", methods=["GET"])
def get_data():
    dev_id = request.args.get("device_id", "SAFE-001")
    for d in devices:
        if d["device_id"] == dev_id:
            return jsonify({
                "device_id": d["device_id"],
                "role": d["role"],
                "backup_active": d["backup_active"],
                "partner_online": d["partner_online"],
                "current_temp": d["current_temp"],
                "humidity": d["humidity"],
                "is_online": d["is_online"],
                "relay_state": d["relay_state"],
                "safety_lock": d["safety_lock"]
            })
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
    if my_cust == "ALL":
        return jsonify(devices)
    return jsonify([d for d in devices if d["customer_id"] == my_cust])

@app.route("/api/report-excel")
def download_report():
    if "username" not in session:
        return redirect("/login")
    report = generate_excel_report()
    output = io.BytesIO(report["data"])
    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=report["name"]
    )

@app.route("/login")
def login():
    err = request.args.get("err", "")
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>เข้าสู่ระบบ — SAFE-ELEC</title>
<style>
* {margin: 0; padding: 0; box-sizing: border-box;}
html, body {
    width: 100%;
    height: 100%;
    min-height: 100vh;
}
body {
    background: linear-gradient(180deg, #002b5c 0%, #0052aa 50%, #002b5c 100%);
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 5%;
    position: relative;
}
.circuit-bg {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
    z-index: 0;
}
.circuit-line {
    position: absolute;
    background: linear-gradient(90deg, transparent, rgba(0, 200, 255, 0.5), transparent);
}
.circuit-line.h { width: 100%; height: 1.5px; }
.circuit-line.v { width: 1.5px; height: 100%; }
.circuit-dot {
    position: absolute;
    width: 12px; height: 12px;
    background: rgba(255, 255, 255, 0.9);
    border-radius: 50%;
    box-shadow: 0 0 10px 3px rgba(0, 200, 255, 0.5);
    z-index: 1;
}
.wrapper {
    position: relative;
    z-index: 2;
    width: 100%;
    max-width: 340px;
    text-align: center;
}
.logo-card {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(0, 200, 255, 0.15);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.logo-img {
    max-width: 100%;
    width: 100%;
    height: auto;
    display: block;
    object-fit: contain;
}
.login-title {
    font-size: 22px;
    color: #fff;
    margin-bottom: 28px;
    line-height: 1.35;
}
.safe-blue { color: #94d4ff; }
input {
    width: 100%;
    padding: 14px 16px;
    margin: 8px 0;
    border-radius: 10px;
    border: none;
    background: rgba(10, 30, 60, 0.45);
    color: #fff;
    font-size: 16px;
    outline: none;
}
input::placeholder { color: #fff; opacity: 1; }
button {
    width: 100%;
    padding: 14px;
    background: linear-gradient(90deg, #00d87c, #00e888);
    border: none;
    border-radius: 10px;
    color: #002b5c;
    font-size: 18px;
    font-weight: bold;
    margin-top: 6px;
    cursor: pointer;
}
button:active { transform: scale(0.97); }
.err {
    color: #ff6b6b;
    text-align: center;
    margin-top: 12px;
    font-size: 14px;
}
</style>
</head>
<body>
    <div class="circuit-bg">
        <div class="circuit-line h" style="top: 10%;"></div>
        <div class="circuit-line h" style="top: 22%;"></div>
        <div class="circuit-line h" style="top: 40%;"></div>
        <div class="circuit-line h" style="top: 60%;"></div>
        <div class="circuit-line h" style="top: 78%;"></div>
        <div class="circuit-line v" style="left: 5%;"></div>
        <div class="circuit-line v" style="left: 18%;"></div>
        <div class="circuit-line v" style="left: 44%;"></div>
        <div class="circuit-line v" style="left: 56%;"></div>
        <div class="circuit-line v" style="left: 82%;"></div>
        <div class="circuit-line v" style="left: 95%;"></div>
    </div>

    <div class="circuit-dot" style="top: 10%; left: 5%;"></div>
    <div class="circuit-dot" style="top: 10%; left: 44%;"></div>
    <div class="circuit-dot" style="top: 10%; left: 56%;"></div>
    <div class="circuit-dot" style="top: 10%; left: 82%;"></div>
    <div class="circuit-dot" style="top: 22%; left: 5%;"></div>
    <div class="circuit-dot" style="top: 22%; left: 44%;"></div>
    <div class="circuit-dot" style="top: 22%; left: 56%;"></div>
    <div class="circuit-dot" style="top: 22%; left: 82%;"></div>
    <div class="circuit-dot" style="top: 40%; left: 5%;"></div>
    <div class="circuit-dot" style="top: 40%; left: 44%;"></div>
    <div class="circuit-dot" style="top: 40%; left: 56%;"></div>
    <div class="circuit-dot" style="top: 40%; left: 82%;"></div>
    <div class="circuit-dot" style="top: 60%; left: 5%;"></div>
    <div class="circuit-dot" style="top: 60%; left: 44%;"></div>
    <div class="circuit-dot" style="top: 60%; left: 56%;"></div>
    <div class="circuit-dot" style="top: 60%; left: 82%;"></div>
    <div class="circuit-dot" style="top: 78%; left: 5%;"></div>
    <div class="circuit-dot" style="top: 78%; left: 44%;"></div>
    <div class="circuit-dot" style="top: 78%; left: 56%;"></div>
    <div class="circuit-dot" style="top: 78%; left: 82%;"></div>

    <div class="wrapper">
        <div class="logo-card">
            <img src="https://raw.githubusercontent.com/kidairhotmailcom-ui/safeelec-mini-server/main/119B2CA8-7BC5-4D30-9735-5200A647A172.png" alt="PNS" class="logo-img">
        </div>

        <div class="login-title">
               🔐 <span class="safe-blue">SAFE-ELEC</span> Smart Energy System
        </div>

        <form method="post" action="/do_login">
            <input type="text" name="username" placeholder="ชื่อผู้ใช้" required>
            <input type="password" name="password" placeholder="รหัสผ่าน" required>
            <button type="submit">เข้าสู่ระบบ</button>
            {% if err %}<div class="err">{{err}}</div>{% endif %}
        </form>
    </div>
</body>
</html>
""", err=err)
@app.route("/do_login", methods=["POST"])
def do_login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if username in USER_DB and USER_DB[username]["password"] == password:
        session["username"] = username
        session["cust_id"] = USER_DB[username]["customer_id"]
        session["name"] = USER_DB[username]["name"]
        return redirect("/dashboard")
    return redirect("/login?err=ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC PLATFORM</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:16px}
h1{text-align:center;color:#6cf;margin-bottom:4px}
.ver{text-align:center;color:#8ac;margin-bottom:8px}
.user-bar{text-align:right;margin-bottom:12px;padding:8px 12px;background:#1a2342;border-radius:8px;font-size:14px}
.user-bar a{color:#f66;text-decoration:none;margin-left:12px}
.tabs{display:flex;max-width:450px;margin:0 auto 12px;border-radius:10px;background:#1a2342;padding:4px}
.tab{flex:1;padding:10px 0;text-align:center;border-radius:8px;cursor:pointer;font-weight:bold;transition:all .2s}
.tab.inactive{background:transparent;color:#8ac}
.tab.active.mini{background:#2f9;color:#032}
.tab.active.full{background:#48f;color:#fff}
.search-box{max-width:520px;margin:0 auto 12px}
.search-input-wrap{position:relative}
.search-input-wrap input{width:100%;padding:12px 12px 12px 40px;border-radius:10px;border:none;background:#1a2342;color:#fff;font-size:15px}
.search-icon{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:#8ac}
.result-info{margin:8px 4px;color:#8ac;font-size:13px}
.result-info b{color:#fff}
.card{background:#1a2342;border-radius:16px;padding:16px;margin-bottom:16px;border:1px solid #2a3b63}
.card.online{border-left:4px solid #4f9}
.card.warning{border-left:4px solid #fa4}
.card.critical{border-left:4px solid #f44;background:#251a30}
.card.offline{border-left:4px solid #666;opacity:0.85}
.name{font-size:17px;font-weight:bold;color:#c9f;margin-bottom:8px}
.meta{font-size:13px;color:#aaa;margin-bottom:10px}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;margin-left:8px;font-weight:bold}
.badge-master{background:#2f9;color:#032}
.badge-backup{background:#48f;color:#fff}
.badge-active{background:#f44;color:#fff}
.section{margin:12px 0;padding:12px;border-radius:10px;background:#0f1f3f}
.row{margin:5px 0;font-size:14px;line-height:1.5}
.ok{color:#4f9}
.warn{color:#fa4}
.dang{color:#f44}
.fbox{border:1px solid #f44;background:#2e1515;padding:12px;border-radius:8px;margin:10px 0}
.gnd-ok{border-left:3px solid #4f9;padding-left:10px}
.gnd-warn{border-left:3px solid #fa4;padding-left:10px}
.gnd-fail{border-left:3px solid #f44;padding-left:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:10px}
.item{padding:8px 10px;border-radius:6px;background:#1e2b4d;font-size:13px}
.hidden{display:none !important}
.no-result{text-align:center;padding:40px 20px;color:#8ac}
.btn-report{display:inline-block;margin-left:10px;padding:6px 12px;background:#2f9;color:#032;border-radius:6px;text-decoration:none;font-weight:bold;font-size:13px}
</style>
</head>
<body>
<h1>⚡ SAFE-ELEC Smart Energy System</h1>
<div class="ver">รองรับระบบคู่ขนาน ESP — ตัวหลักเสีย สำรองทำงานแทนทันที ✅</div>
<div class="user-bar">
  👤 {{session['name']}}
  <a href="/api/report-excel" class="btn-report">📊 ดาวน์โหลดรายงาน</a>
  <a href="/logout">ออกจากระบบ</a>
</div>
<div class="tabs">
  <div class="tab active mini" id="tab-mini" onclick="setView('mini')">🟢 มินิ</div>
  <div class="tab inactive full" id="tab-full" onclick="setView('full')">🔵 เต็มระบบ</div>
</div>
<div class="search-box">
  <div class="search-input-wrap">
    <span class="search-icon">🔍</span>
    <input id="q" placeholder="ค้นหา...">
  </div>
  <div id="result-info" class="result-info"></div>
</div>
<div id="list"></div>
<script>
let all = [];
let currentView = 'mini';
const CONFIG_SITE_TYPES = """ + json.dumps(CONFIG["SITE_TYPES"], ensure_ascii=False) + """;

async function load(){
  const res = await fetch('/api/devices');
  all = await res.json();
  applyFilterAndRender();
}
function setView(view){
  currentView = view;
  document.getElementById('tab-mini').className = view==='mini'?'tab active mini':'tab inactive';
  document.getElementById('tab-full').className = view==='full'?'tab active full':'tab inactive';
  applyFilterAndRender();
}
function getIcon(d){
  const m={online:'🟢',warning:'🟡',critical:'🔴',offline:'⚫'};
  return m[d.status_summary]||'❓';
}
function getBadge(d){
  if(d.backup_active) return '<span class="badge badge-active">⚡ ทำงานแทน</span>';
  if(d.role==='MASTER') return '<span class="badge badge-master">ตัวหลัก</span>';
  if(d.role==='BACKUP') return '<span class="badge badge-backup">สำรอง</span>';
  return '';
}
function getSensorIcon(s){
  if(s.ok===true) return '✅';
  if(s.ok===false) return '❌';
  return '⏳';
}
function matchDevice(d, kw){
  if(!kw) return true;
  const typeLabel = CONFIG_SITE_TYPES[d.site_type] || d.site_type;
  const searchText = [
    d.device_id, d.site_name, d.customer_id, d.province, typeLabel,
    d.status_summary, d.is_online ? 'ออนไลน์' : 'ออฟไลน์',
    d.current_temp+'', d.humidity+'', d.role||''
  ].join(' ').toLowerCase();
  return searchText.includes(kw);
}
function applyFilterAndRender(){
  const kw = document.getElementById('q').value.trim().toLowerCase();
  let filtered = all.filter(d => matchDevice(d, kw));
  if (!kw) {
    filtered = filtered.filter(d => d.is_online);
    document.getElementById('result-info').innerHTML = 
      `แสดง <b>${filtered.length}</b> ออนไลน์ จากทั้งหมด <b>${all.length}</b> รายการ`;
  } else {
    document.getElementById('result-info').innerHTML = 
      `พบ <b>${filtered.length}</b> จากทั้งหมด <b>${all.length}</b> รายการ`;
  }
  render(filtered);
}
function render(list){
  if(list.length === 0){
    document.getElementById('list').innerHTML = `<div class="no-result">ไม่พบอุปกรณ์ที่ออนไลน์ 😊<br>รอการเชื่อมต่อจากอุปกรณ์...</div>`;
    return;
  }
  document.getElementById('list').innerHTML = list.map(d=>`
    <div class="card ${d.status_summary}">
      <div class="name">${getIcon(d)} ${d.device_id} — ${d.site_name} ${getBadge(d)}</div>
      <div class="meta">🏢 ${d.customer_id} | 📍 ${d.province} | ⏰ ${d.last_updated}</div>
      ${!d.partner_online && d.role==='MASTER'?'<div class="fbox">⚠️ ไม่พบคู่ขนาน — ตรวจสอบตัวสำรอง</div>':''}
      ${d.backup_active?'<div class="fbox">⚡ ตัวหลักขาดการติดต่อ — สำรองกำลังทำงานแทน</div>':''}
      ${d.fault_list.length>0?`<div class="fbox"><b>⚠️ พบ ${d.fault_list.length} ปัญหา</b>${d.fault_list.map(f=>`<div class="row">${f}</div>`).join('')}</div>`:''}
      
      <div class="${currentView!=='mini'?'hidden':''}">
        <div class="section">
                <b>📊 ตรวจสอบอุปกรณ์วัด</b>
          <div class="grid">
            ${Object.entries(d.sensors)
              .filter(([k]) => k.startsWith('sens_'))
              .map(([k, s]) => `
                <div class="item ${s.ok === true ? 'ok' : s.ok === false ? 'dang' : 'warn'}">
                  ${getSensorIcon(s)} ${s.name}<br><b>${s.value}</b>
                </div>`
              ).join('')}
          </div>
        </div>
      </div>
    </div>
  `).join('');
}
load();
document.getElementById('q').addEventListener('input', applyFilterAndRender);
</script>
</body>
</html>
""")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
