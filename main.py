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
app.secret_key = "SAFE-ELEC-2026-SECRET-KEY-CHANGE-ME-PLEASE"
CORS(app)

# ==============================================================
# 🔐 บัญชีผู้ใช้
# ==============================================================
USER_DB = {
    "admin": {"password": "123456", "name": "ผู้ดูแลระบบ", "customer_id": "ALL"},
    "cust0891": {"password": "123456", "name": "อาคารหลัก ขอนแก่น", "customer_id": "CUST-0891"},
    "cust0002": {"password": "123456", "name": "สาขาเชียงใหม่", "customer_id": "CUST-0002"},
    "cust0004": {"password": "123456", "name": "โรงงานผลิต ระยอง", "customer_id": "CUST-0004"},
}

# ==============================================================
# ⚙️ ค่าคงที่
# ==============================================================
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
        "EMAIL_TO": "",
        "EMAIL_FROM": "",
        "SMTP_SERVER": "smtp.gmail.com",
        "SMTP_PORT": 587,
        "SMTP_PASS": "",
        "SEND_REPEAT_DELAY_MIN": 30,
    },
    "REPORT": {
        "AUTO_SEND": True,
        "SCHEDULE_TIME": "09:00",
        "DAY_OF_MONTH": 1,
    }
}

# ==============================================================
# 🔄 แปลงชื่อฟิลด์
# ==============================================================
FIELD_MAP = {
    "id":               "device_id",
    "esp_id":           "device_id",
    "esp":              "device_id",
    "site":             "site_name",
    "cust":             "customer_id",
    "role":             "role",
    "is_master":        "is_master",
    "active":           "backup_active",
    "backup_active":    "backup_active",
    "partner":          "partner_online",
    "partner_online":   "partner_online",
    "master":           "is_master",
    "t":                "current_temp",
    "temp":             "current_temp",
    "temperature":      "current_temp",
    "temp_max_c":       "current_temp",
    "humi":             "humidity",
    "rh":               "humidity",
    "humidity_rh":      "humidity",
    "v12":              "v_l1_l2",
    "v23":              "v_l2_l3",
    "v31":              "v_l3_l1",
    "vl1l2":            "v_l1_l2",
    "vl2l3":            "v_l2_l3",
    "vl3l1":            "v_l3_l1",
    "v_ab":             "v_l1_l2",
    "v_bc":             "v_l2_l3",
    "v_ca":             "v_l3_l1",
    "i1":               "a_l1",
    "i2":               "a_l2",
    "i3":               "a_l3",
    "il1":              "a_l1",
    "il2":              "a_l2",
    "il3":              "a_l3",
    "ia":               "a_l1",
    "ib":               "a_l2",
    "ic":               "a_l3",
    "in":               "a_n",
    "power":            "power_kw",
    "kw":               "power_kw",
    "p_total":          "power_kw",
    "power_total_kw":   "power_kw",
    "vz1":              "z1_v", "v_z1": "z1_v", "vzone1": "z1_v", "sub1_v": "z1_v",
    "az1":              "z1_a", "a_z1": "z1_a", "azone1": "z1_a", "sub1_a": "z1_a",
    "wz1":              "z1_w", "w_z1": "z1_w", "sub1_w": "z1_w",
    "vz2":              "z2_v", "v_z2": "z2_v", "vzone2": "z2_v", "sub2_v": "z2_v",
    "az2":              "z2_a", "a_z2": "z2_a", "azone2": "z2_a", "sub2_a": "z2_a",
    "wz2":              "z2_w", "w_z2": "z2_w", "sub2_w": "z2_w",
    "vz3":              "z3_v", "v_z3": "z3_v", "vzone3": "z3_v", "sub3_v": "z3_v",
    "az3":              "z3_a", "a_z3": "z3_a", "azone3": "z3_a", "sub3_a": "z3_a",
    "wz3":              "z3_w", "w_z3": "z3_w", "sub3_w": "z3_w",
    "gnd_r":            "gnd_resistance_ohm",
    "ground_res":       "gnd_resistance_ohm",
    "res_gnd":          "gnd_resistance_ohm",
    "r_gnd":            "gnd_resistance_ohm",
    "gnd_ohm":          "gnd_resistance_ohm",
    "ground_resistance_ohm": "gnd_resistance_ohm",
    "gnd_v":            "gnd_voltage_v",
    "ground_v":         "gnd_voltage_v",
    "v_leak":           "gnd_voltage_v",
    "v_gnd":            "gnd_voltage_v",
    "leak_volt":        "gnd_voltage_v",
    "ground_leak_voltage_v": "gnd_voltage_v",
    "wiring":           "wiring_fault",
    "shutdown":         "critical_shutdown",
    "psu_status":       "power_status",
    "relay":            "relay_state",
    "relay_state":      "relay_state",
    "lock":             "safety_lock",
    "safety_lock":      "safety_lock",
}

# ==============================================================
# 📋 รายการอุปกรณ์
# ==============================================================
DEVICE_LIST = [
    ("SAFE-001",      "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    ("SAFE-001-BAK",  "สำรอง — แผงหลัก อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
]

# ==============================================================
# 📐 โครงสร้างข้อมูล
# ==============================================================
TEMPLATE = {
    "device_id": "", "site_name": "", "customer_id": "",
    "province": "", "site_type": "",
    "last_updated": "-", "last_seen": None,
    "is_online": False, "status_summary": "offline",
    "last_alert_sent": None,
    "role": "UNKNOWN",
    "is_master": False,
    "backup_active": False,
    "partner_online": True,
    "partner_id": "",
    "current_temp": 0.0, "humidity": 0.0,
    "power_status": "MAIN AC",
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
        "temp":      {"name": "อุณหภูมิตู้", "value": 0.0, "ok": None},
        "humidity":  {"name": "ความชื้น", "value": 0.0, "ok": None},
        "comm":      {"name": "สื่อสาร", "value": "ไม่เชื่อมต่อ", "ok": None},
        "psu":       {"name": "แหล่งจ่ายภายใน", "value": "ตรวจสอบ", "ok": None},
        "esp":       {"name": "อุปกรณ์ ESP", "value": "ไม่เชื่อมต่อ", "ok": None},
        "v_l1_l2":  {"name": "แรงดัน L1-L2", "value": 0.0, "ok": None},
        "v_l2_l3":  {"name": "แรงดัน L2-L3", "value": 0.0, "ok": None},
        "v_l3_l1":  {"name": "แรงดัน L3-L1", "value": 0.0, "ok": None},
        "a_l1":     {"name": "กระแสเฟส 1", "value": 0.0, "ok": None},
        "a_l2":     {"name": "กระแสเฟส 2", "value": 0.0, "ok": None},
        "a_l3":     {"name": "กระแสเฟส 3", "value": 0.0, "ok": None},
        "z1_v":     {"name": "โซน1 แรงดัน", "value": 0.0, "ok": None},
        "z1_a":     {"name": "โซน1 กระแส", "value": 0.0, "ok": None},
        "z2_v":     {"name": "โซน2 แรงดัน", "value": 0.0, "ok": None},
        "z2_a":     {"name": "โซน2 กระแส", "value": 0.0, "ok": None},
        "z3_v":     {"name": "โซน3 แรงดัน", "value": 0.0, "ok": None},
        "z3_a":     {"name": "โซน3 กระแส", "value": 0.0, "ok": None},
        "gnd_resist":{"name": "กราวด์-ความต้านทาน", "value": 0.0, "unit": "Ω", "ok": None},
        "gnd_volt": {"name": "กราวด์-แรงดันรั่ว", "value": 0.0, "unit": "V", "ok": None},
        "dualmode": {"name": "ระบบคู่ขนาน", "value": "รอข้อมูล", "ok": None},
    },
    "fault_list": [], "alert_level": "normal",
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

# ==============================================================
# 🔔 ระบบแจ้งเตือน
# ==============================================================
def send_line_alert(message):
    token = CONFIG["ALERT"]["LINE_TOKEN"]
    if not token:
        print("[LINE] ยังไม่ได้ตั้งค่า Token")
        return False
    try:
        url = "https://notify-api.line.me/api/notify"
        headers = {"Authorization": f"Bearer {token}"}
        data = {"message": f"\n{message}"}
        res = requests.post(url, headers=headers, data=data, timeout=15)
        if res.status_code == 200:
            print("[LINE] ส่งสำเร็จ")
            return True
        else:
            print(f"[LINE] ส่งไม่สำเร็จ: รหัส {res.status_code}")
            return False
    except Exception as e:
        print(f"[LINE] ข้อผิดพลาด: {e}")
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

# ==============================================================
# 📊 รายงาน Excel
# ==============================================================
def generate_excel_report():
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    ws = workbook.add_worksheet("สรุปภาพรวม")
    
    header = workbook.add_format({'bold': True, 'bg_color': '#2f9', 'color': '#032', 'align': 'center'})
    normal = workbook.add_format({'text_wrap': True})
    red = workbook.add_format({'font_color': '#f44', 'bold': True})
    green = workbook.add_format({'font_color': '#4f9'})
    
    headers = ["รหัส", "สถานที่", "บทบาท", "ออนไลน์", "สถานะ", "อุณหภูมิ", "กราวด์ R(Ω)", "กราวด์ V(V)", "ปัญหา"]
    for col, h in enumerate(headers):
        ws.write(0, col, h, header)
    
    for row, d in enumerate(devices, start=1):
        status_fmt = green if d["alert_level"]=="normal" else red
        role_label = d.get("role", "-")
        if d.get("backup_active"):
            role_label += " (ทำงานแทน)"
        ws.write(row, 0, d["device_id"], normal)
        ws.write(row, 1, d["site_name"], normal)
        ws.write(row, 2, role_label, normal)
        ws.write(row, 3, "✅ ใช่" if d["is_online"] else "❌ ไม่", green if d["is_online"] else red)
        ws.write(row, 4, d["status_summary"], status_fmt)
        ws.write(row, 5, d["current_temp"], normal)
        ws.write(row, 6, d["gnd_resistance_ohm"], normal)
        ws.write(row, 7, d["gnd_voltage_v"], normal)
        ws.write(row, 8, f"{len(d['fault_list'])} รายการ", normal)
    
    ws.set_column(0, 8, 18)
    workbook.close()
    output.seek(0)
    return {
        "data": output.read(),
        "name": f"SAFE-ELEC-Report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    }

# ==============================================================
# 🔍 ตรวจสอบกราวด์
# ==============================================================
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

# ==============================================================
# ⚡ ตรวจสอบระบบสำรอง ESP
# ==============================================================
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

# ==============================================================
# ✅ ตรวจสอบทุกอย่าง
# ==============================================================
def check_all(dev):
    S = CONFIG["STANDARD"]
    faults = check_ground(dev)
    faults += check_dual_backup(dev)

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

# ==============================================================
# 🛡️ ตรวจสอบล็อกอิน
# ==============================================================
@app.before_request
def check_login():
    if request.path in ["/login", "/do_login", "/logout", "/api/data", "/api/devices", "/api/report-excel"]:
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

# ==============================================================
# 🌐 API รับข้อมูล
# ==============================================================
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
    report = generate_excel_report()
    return send_file(
        io.BytesIO(report["data"]),
        download_name=report["name"],
        as_attachment=True
    )

# ==============================================================
# 📲 ล็อกอิน
# ==============================================================
@app.route("/login")
def login():
    err = request.args.get("err", "")
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เข้าสู่ระบบ — SAFE-ELEC</title>
<style>
body{background:#0f1629;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;padding:20px}
.box{background:#1a2342;padding:30px;border-radius:16px;width:100%;max-width:400px;border:1px solid #2a3b63}
h2{text-align:center;color:#6cf;margin-bottom:25px}
input{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:none;background:#0f1f3f;color:#fff;font-size:16px}
button{width:100%;padding:12px;background:#2f9;border:none;border-radius:8px;color:#032;font-weight:bold;font-size:16px;margin-top:10px;cursor:pointer}
.err{color:#f44;text-align:center;margin-top:15px}
</style>
</head>
<body>
<div class="box">
<h2>🔐 เข้าสู่ระบบ SAFE-ELEC</h2>
<form method="post" action="/do_login">
<input type="text" name="user" placeholder="ชื่อผู้ใช้" required>
<input type="password" name="pwd" placeholder="รหัสผ่าน" required>
<button type="submit">เข้าสู่ระบบ</button>
{% if err %}<div class="err">{{err}}</div>{% endif %}
</form>
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

# ==============================================================
# 📊 หน้าจอหลัก — ครบถ้วน ✅
# ==============================================================
@app.route("/")
def dashboard():
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
<h1>⚡ SAFE-ELEC PLATFORM</h1>
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
const CONFIG_SITE_TYPES = {{CONFIG_SITE_TYPES|tojson}};

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
          <b>🌡️ สภาพแวดล้อม</b>
          <div class="row">อุณหภูมิ: <b class="${d.current_temp>=60?'dang':'ok'}">${d.current_temp}°C</b></div>
          <div class="row">ความชื้น: ${d.humidity}%</div>
          <div class="row">สถานะไฟ: ${d.power_status||'MAIN AC'}</div>
          <div class="row ${d.wiring_fault?'dang':'ok'}">สายไฟ: ${d.wiring_fault?'⚠️ ผิดปกติ':'✅ ปกติ'}</div>
        </div>
        
        <div class="section">
          <b>📋 สถานะระบบคู่ขนาน</b>
          <div class="grid">
            ${Object.entries(d.sensors).filter(([k])=>k==='dualmode'||k==='comm'||k==='esp').map(([k,s])=>{
              return `<div class="item ${s.ok===true?'ok':s.ok===false?'dang':'warn'}">
                ${getSensorIcon(s)} ${s.name}<br><b>${s.value}</b>
              </div>`;
            }).join('')}
          </div>
        </div>
        
        <div class="section">
          <b>⚡ ตู้หลัก 380V</b>
          <div class="row">L1-L2: ${d.v_l1_l2}V | L2-L3: ${d.v_l2_l3}V | L3-L1: ${d.v_l3_l1}V</div>
          <div class="row">กระแส L1: ${d.a_l1}A | L2: ${d.a_l2}A | L3: ${d.a_l3}A</div>
          <div class="row">กำลัง: ${d.power_kw}kW | สมดุล: ${d.balance_3ph_ok?'✅ ปกติ':'⚠️ ไม่สมดุล'}</div>
        </div>
        
        <div class="section ${d.gnd_system_ok?'gnd-ok':'gnd-fail'}">
          <b>🛡️ ตรวจสอบกราวด์</b>
          <div class="row">ความต้านทาน: ${d.sensors.gnd_resist.value}Ω — ${d.sensors.gnd_resist.ok===true?'✅ ปกติ':d.sensors.gnd_resist.ok===false?'❌ ผิดปกติ':'⏳ รอข้อมูล'}</div>
          <div class="row">แรงดันรั่ว: ${d.sensors.gnd_volt.value}V — ${d.sensors.gnd_volt.ok===true?'✅ ปกติ':d.sensors.gnd_volt.ok===false?'❌ ผิดปกติ':'⏳ รอข้อมูล'}</div>
        </div>
        
        <div class="section ${currentView!=='full'?'hidden':''}">
          <b>🏘️ โซน 1-3</b>
          <div class="row">โซน1: ${d.z1_v}V / ${d.z1_a}A / ${d.z1_w}kW</div>
          <div class="row">โซน2: ${d.z2_v}V / ${d.z2_a}A / ${d.z2_w}kW</div>
          <div class="row">โซน3: ${d.z3_v}V / ${d.z3_a}
