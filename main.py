from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = "SAFE-ELEC-PRODUCTION-SECRET-KEY-2026"
CORS(app)

# ==============================================================
# 📍 กำหนดค่าทั้งหมดที่นี่ที่เดียว — ไม่ต้องแก้ที่อื่น
# ==============================================================

# 🔑 บัญชีผู้ใช้ — เพิ่ม/ลูกค้าได้เลย
ACCOUNTS = {
    "admin":    {"password": "123456", "name": "ผู้ดูแลระบบ",       "customer_id": "ALL"},
    "khonkaen": {"password": "123456", "name": "อาคารหลัก ขอนแก่น", "customer_id": "CUST-0891"},
    "chiangmai":{"password": "123456", "name": "สาขาเชียงใหม่",       "customer_id": "CUST-0002"},
    "rayong":   {"password": "123456", "name": "โรงงานผลิต ระยอง",   "customer_id": "CUST-0004"},
}

# ⚙️ มาตรฐาน — ปรับเกณฑ์ที่นี่
STANDARDS = {
    "V3":  {"min": 342, "max": 418, "nom": 380},
    "V1":  {"min": 198, "max": 242, "nom": 220},
    "TEMP":{"min": -10, "max": 75, "alert": 60},
    "HUMI":{"min": 20, "max": 90},
    "BALANCE": {"max_amp": 5.0, "max_pct": 10.0},
    "GROUND":  {"res_ok": 10.0, "res_warn": 30.0, "volt_ok": 2.0},
    "OFFLINE_SEC": 90,
}

# 🏗️ รายการอุปกรณ์ — เพิ่มเครื่องใหม่แค่บรรทัดเดียว
DEVICES_CONFIG = [
    # (device_id, site_name, customer_id, province, site_type)
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    # เพิ่มต่อตรงนี้ เช่น:
    # ("SAFE-002", "สาขาเชียงใหม่-ชั้น1", "CUST-0002", "เชียงใหม่", "office"),
    # ("SAFE-003", "โรงงาน-โซนA", "CUST-0004", "ระยอง", "factory"),
]

# ==============================================================
# 🔧 สร้างระบบอัตโนมัติ — ไม่ต้องแก้โค้ดข้างล่าง
# ==============================================================

def create_device_template():
    """คืนค่าแม่แบบอุปกรณ์ — เพิ่มฟิลด์ที่นี่ครั้งเดียว"""
    return {
        "last_updated": "-",
        "last_seen": None,
        "is_online": False,
        "status_summary": "offline",
        "esp_main_status": "online",
        "esp_backup_active": False,
        "esp_replaced_at": None,
        "current_temp": 0.0,
        "humidity": 0.0,
        "power_status": "MAIN AC",
        "wiring_fault": False,
        "critical_shutdown": False,
        "v_l1_l2": 0.0, "v_l2_l3": 0.0, "v_l3_l1": 0.0,
        "a_l1": 0.0, "a_l2": 0.0, "a_l3": 0.0, "a_n": 0.0,
        "power_kw": 0.0, "balance_3ph_ok": True,
        "zones": {
            1: {"v": 0.0, "a": 0.0, "w": 0.0, "ok": None},
            2: {"v": 0.0, "a": 0.0, "w": 0.0, "ok": None},
            3: {"v": 0.0, "a": 0.0, "w": 0.0, "ok": None},
        },
        "gnd_resistance_ohm": 0.0,
        "gnd_voltage_v": 0.0,
        "gnd_system_ok": True,
        "sensors": {},
        "fault_list": [],
        "alert_level": "normal",
    }

def init_sensors_struct(dev):
    """สร้างโครงสร้างเซนเซอร์อัตโนมัติ"""
    dev["sensors"] = {
        "a_l1":      {"name": "กระแสเฟส 1",       "value": 0.0,  "ok": None},
        "a_l2":      {"name": "กระแสเฟส 2",       "value": 0.0,  "ok": None},
        "a_l3":      {"name": "กระแสเฟส 3",       "value": 0.0,  "ok": None},
        "comm":      {"name": "สถานะสื่อสาร",      "value": "ไม่เชื่อมต่อ", "ok": None},
        "esp":       {"name": "สถานะอุปกรณ์",      "value": "ไม่เชื่อมต่อ", "ok": None},
        "psu":       {"name": "แหล่งจ่ายภายใน",    "value": "ตรวจสอบ",     "ok": None},
        "temp":      {"name": "อุณหภูมิตู้",       "value": 0.0,  "ok": None, "unit": "°C"},
        "humidity":  {"name": "ความชื้นสัมพัทธ์",  "value": 0,    "ok": None, "unit": "%"},
        "v_l1_l2":  {"name": "แรงดัน L1-L2",      "value": 0.0,  "ok": None, "unit": "V"},
        "v_l2_l3":  {"name": "แรงดัน L2-L3",      "value": 0.0,  "ok": None, "unit": "V"},
        "v_l3_l1":  {"name": "แรงดัน L3-L1",      "value": 0.0,  "ok": None, "unit": "V"},
        "z1_a":      {"name": "โซน 1 — กระแส",     "value": 0.0,  "ok": None, "unit": "A"},
        "z1_v":      {"name": "โซน 1 — แรงดัน",     "value": 0.0,  "ok": None, "unit": "V"},
        "z2_a":      {"name": "โซน 2 — กระแส",     "value": 0.0,  "ok": None, "unit": "A"},
        "z2_v":      {"name": "โซน 2 — แรงดัน",     "value": 0.0,  "ok": None, "unit": "V"},
        "z3_a":      {"name": "โซน 3 — กระแส",     "value": 0.0,  "ok": None, "unit": "A"},
        "z3_v":      {"name": "โซน 3 — แรงดัน",     "value": 0.0,  "ok": None, "unit": "V"},
        "gnd_resist":{"name": "กราวด์ — ความต้านทาน", "value": 0.0, "ok": None, "unit": "Ω"},
        "gnd_volt": {"name": "กราวด์ — แรงดันรั่ว",  "value": 0.0, "ok": None, "unit": "V"},
    }

# 📦 สร้างรายการอุปกรณ์ทั้งหมด — อัตโนมัติ
devices = []
for dev_id, site, cust_id, prov, stype in DEVICES_CONFIG:
    dev = create_device_template()
    dev.update({
        "device_id": dev_id,
        "site_name": site,
        "customer_id": cust_id,
        "province": prov,
        "site_type": stype,
    })
    init_sensors_struct(dev)
    devices.append(dev)

# ==============================================================
# 🧠 ตรวจสอบสถานะ — ไม่ต้องแก้เมื่อเพิ่มเครื่อง
# ==============================================================

def check_esp_status(dev):
    now = datetime.now()
    if dev["last_seen"]:
        sec_since = (now - dev["last_seen"]).total_seconds()
        dev["is_online"] = sec_since < STANDARDS["OFFLINE_SEC"]
    else:
        dev["is_online"] = False
        sec_since = 99999

    s = dev["sensors"]
    if dev["is_online"]:
        dev["esp_main_status"] = "online"
        dev["esp_backup_active"] = False
        s["esp"]["value"] = "ทำงานปกติ"; s["esp"]["ok"] = True
        s["comm"]["value"] = "เชื่อมต่อปกติ"; s["comm"]["ok"] = True
        s["psu"]["value"] = "ปกติ"; s["psu"]["ok"] = True
    elif sec_since >= STANDARDS["OFFLINE_SEC"]:
        dev["esp_main_status"] = "fault"
        dev["esp_backup_active"] = True
        s["esp"]["value"] = "ขาดการติดต่อ"; s["esp"]["ok"] = False
        s["comm"]["value"] = "ขาดสัญญาณ"; s["comm"]["ok"] = False
        s["psu"]["value"] = "ผิดปกติ"; s["psu"]["ok"] = False
    else:
        s["esp"]["value"] = "รอสัญญาณ"; s["esp"]["ok"] = None
        s["comm"]["value"] = "รอเชื่อมต่อ"; s["comm"]["ok"] = None
        s["psu"]["value"] = "ตรวจสอบ"; s["psu"]["ok"] = None

def check_balance(i1, i2, i3):
    total = i1 + i2 + i3
    if total <= 0: return True
    avg = total / 3
    for v in (i1, i2, i3):
        if abs(v - avg) > STANDARDS["BALANCE"]["max_amp"]: return False
        if avg > 0 and abs(v - avg) / avg * 100 > STANDARDS["BALANCE"]["max_pct"]: return False
    return True

def evaluate(dev):
    """ประเมินทุกค่า — เรียกอัตโนมัติ ไม่ต้องแก้เมื่อเพิ่มเครื่อง"""
    S = STANDARDS
    dev["fault_list"] = []
    s = dev["sensors"]

    check_esp_status(dev)

    # อุณหภูมิ
    t = dev["current_temp"]
    s["temp"]["value"] = t
    if not dev["is_online"] or t == 0:
        s["temp"]["ok"] = None
    elif t < S["TEMP"]["min"] or t > S["TEMP"]["max"]:
        s["temp"]["ok"] = False; dev["fault_list"].append(f"🔴 อุณหภูมิผิดปกติ: {t}°C")
    elif t >= S["TEMP"]["alert"]:
        s["temp"]["ok"] = False; dev["fault_list"].append(f"🔴 อุณหภูมิสูง: {t}°C")
    else:
        s["temp"]["ok"] = True

    # ความชื้น
    h = dev["humidity"]
    s["humidity"]["value"] = h
    if not dev["is_online"] or h == 0:
        s["humidity"]["ok"] = None
    elif not (S["HUMI"]["min"] <= h <= S["HUMI"]["max"]):
        s["humidity"]["ok"] = False; dev["fault_list"].append(f"🔴 ความชื้นผิดปกติ: {h}%")
    else:
        s["humidity"]["ok"] = True

    # แรงดัน 3 เฟส
    for key, val in [("v_l1_l2", dev["v_l1_l2"]), ("v_l2_l3", dev["v_l2_l3"]), ("v_l3_l1", dev["v_l3_l1"])]:
        s[key]["value"] = val
        if not dev["is_online"] or val == 0:
            s[key]["ok"] = None
        elif not (S["V3"]["min"] <= val <= S["V3"]["max"]):
            s[key]["ok"] = False; dev["fault_list"].append(f"🔴 {s[key]['name']}: {val}V")
        else:
            s[key]["ok"] = True

    # กระแสเฟส
    for idx, key in enumerate(["a_l1", "a_l2", "a_l3"], start=1):
        val = dev[key]
        s[key]["value"] = val
        if not dev["is_online"] or val == 0:
            s[key]["ok"] = None
        else:
            s[key]["ok"] = True

    # ความสมดุล 3 เฟส
    dev["balance_3ph_ok"] = check_balance(dev["a_l1"], dev["a_l2"], dev["a_l3"])
    if not dev["balance_3ph_ok"] and dev["is_online"]:
        dev["fault_list"].append("🔴 ระบบ 3 เฟสไม่สมดุล")

    # โซน 1-3
    for z in range(1, 4):
        v_key, a_key = f"z{z}_v", f"z{z}_a"
        v, a = dev[v_key], dev[a_key]
        s[v_key]["value"] = v; s[a_key]["value"] = a
        if not dev["is_online"] or v == 0:
            s[v_key]["ok"] = None; s[a_key]["ok"] = None
        elif not (S["V1"]["min"] <= v <= S["V1"]["max"]):
            s[v_key]["ok"] = False; dev["fault_list"].append(f"🔴 โซน{z} แรงดันผิดปกติ: {v}V")
        else:
            s[v_key]["ok"] = True; s[a_key]["ok"] = True if a > 0 else None

    # กราวด์
    gr = dev["gnd_resistance_ohm"]
    s["gnd_resist"]["value"] = gr
    if gr <= 0:
        s["gnd_resist"]["ok"] = None
    elif gr > S["GROUND"]["res_ok"]:
        s["gnd_resist"]["ok"] = False
        if gr > S["GROUND"]["res_warn"]:
            dev["fault_list"].append(f"🔴 กราวด์ไม่ดีมาก: {gr}Ω")
        else:
            dev["fault_list"].append(f"🔴 กราวด์ต้องปรับปรุง: {gr}Ω")
    else:
        s["gnd_resist"]["ok"] = True

    gv = dev["gnd_voltage_v"]
    s["gnd_volt"]["value"] = gv
    if gv <= 0:
        s["gnd_volt"]["ok"] = None
    elif gv > S["GROUND"]["volt_ok"]:
        s["gnd_volt"]["ok"] = False; dev["fault_list"].append(f"🔴 แรงดันรั่วสูง: {gv}V")
    else:
        s["gnd_volt"]["ok"] = True

    # สรุประดับ
    if not dev["is_online"]:
        dev["status_summary"] = "offline"; dev["alert_level"] = "critical"
    elif dev["fault_list"]:
        dev["status_summary"] = "warning"; dev["alert_level"] = "critical" if any("ไม่ดี" in f or "สูง" in f for f in dev["fault_list"]) else "warning"
    else:
        dev["status_summary"] = "online"; dev["alert_level"] = "normal"

# อัปเดตทุกอุปกรณ์ก่อนเรียกหน้า
@app.before_request
def refresh_all():
    for dev in devices:
        evaluate(dev)

# ==============================================================
# 🌐 API & หน้าเว็บ
# ==============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "")
        p = request.form.get("password", "")
        if u in ACCOUNTS and ACCOUNTS[u]["password"] == p:
            session["user"] = u
            session["cid"] = ACCOUNTS[u]["customer_id"]
            return redirect("/")
        return render_template_string(LOGIN_PAGE, error="ชื่อหรือรหัสไม่ถูกต้อง")
    return render_template_string(LOGIN_PAGE)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")
    cid = session["cid"]
    visible = [d for d in devices if cid == "ALL" or d["customer_id"] == cid]
    return render_template_string(DASHBOARD_PAGE, devices=visible, user=session["user"])

@app.route("/api/data", methods=["POST"])
def upload_data():
    """รับข้อมูลจากอุปกรณ์ — ส่งได้เลย ระบบรู้จักเอง"""
    data = request.get_json(silent=True) or {}
    dev_id = data.get("device_id")
    if not dev_id:
        return jsonify({"ok": False, "msg": "ต้องระบุ device_id"}), 400

    dev = next((d for d in devices if d["device_id"] == dev_id), None)
    if not dev:
        return jsonify({"ok": False, "msg": "ไม่พบอุปกรณ์"}), 404

    # อัปเดตค่าทุกฟิลด์อัตโนมัติ
    for k, v in data.items():
        if k in dev and k not in ["sensors", "fault_list"]:
            dev[k] = v
    dev["last_updated"] = datetime.now().strftime("%H:%M:%S %d/%m/%y")
    dev["last_seen"] = datetime.now()
    return jsonify({"ok": True, "device_id": dev_id})

@app.route("/api/devices")
def list_devices():
    if "user" not in session:
        return jsonify({"error": "เข้าสู่ระบบก่อน"}), 401
    cid = session["cid"]
    visible = [d for d in devices if cid == "ALL" or d["customer_id"] == cid]
    return jsonify(visible)

@app.route("/api/replace-esp", methods=["POST"])
def mark_replaced():
    data = request.get_json(silent=True) or {}
    dev_id = data.get("device_id")
    dev = next((d for d in devices if d["device_id"] == dev_id), None)
    if not dev:
        return jsonify({"ok": False}), 404
    dev["esp_replaced_at"] = datetime.now()
    return jsonify({"ok": True, "msg": "บันทึกเวลาเปลี่ยนอุปกรณ์เรียบร้อย"})

# ==============================================================
# 🎨 หน้าเว็บ — แยกส่วน ใช้ได้กับทุกเครื่อง
# ==============================================================

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="th">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>เข้าสู่ระบบ — SAFE-ELEC</title>
<style>
*{box-sizing:border-box;font-family:Sarabun,system-ui}
body{background:#0f1629;color:#fff;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0}
.box{background:#1a233f;padding:2rem;border-radius:16px;width:90%;max-width:400px;box-shadow:0 8px 32px #0003}
h1{text-align:center;margin-bottom:1.5rem;font-size:1.4rem}
input{width:100%;padding:.9rem;margin:.5rem 0;border:none;border-radius:8px;background:#273354;color:#fff;font-size:1rem}
button{width:100%;padding:.9rem;border:none;border-radius:8px;background:#2f9f62;color:#fff;font-weight:bold;font-size:1rem;cursor:pointer;margin-top:.5rem}
.err{color:#ff6b6b;text-align:center;margin-top:1rem}
</style>
</head>
<body>
<div class="box">
<h1>🔐 เข้าสู่ระบบ</h1>
<form method="post">
<input name="username" placeholder="ชื่อผู้ใช้" required>
<input name="password" type="password" placeholder="รหัสผ่าน" required>
<button type="submit">เข้าสู่ระบบ</button>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
</form>
</div>
</body>
</html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html lang="th">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC — แดชบอร์ด</title>
<style>
*{box-sizing:border-box;font-family:Sarabun,system-ui}
body{background:#0f1629;color:#fff;margin:0;padding:1rem}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem}
.top h1{margin:0;font-size:1.3rem}
.top a{color:#ff6b6b;text-decoration:none}
.status-dot{display:inline-block;width:12px;height:12px;border-radius:50%;margin-right:6px}
.online{background:#2f9f62}
.offline{background:#666}
.warning{background:#f9a825}
.critical{background:#ff5252}
.dev-card{background:#1a233f;border-radius:12px;padding:1rem;margin-bottom:1rem}
.dev-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:.8rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.75rem}
.item{border-left:3px solid #555;background:#242f50;border-radius:6px;padding:.75rem}
.item.ok{border-color:#2f9f62;background:#1a3a30}
.item.warn{border-color:#666;background:#2a2f45}
.item.bad{border-color:#ff5252;background:#382029}
.name{font-size:.8rem;color:#aaa;margin-bottom:.25rem}
.val{font-size:1.1rem;font-weight:bold}
.faults{margin-top:.8rem;padding:.7rem;background:#2e2020;border-radius:6px;color:#ffb3b3;font-size:.9rem}
.badge{display:inline-block;padding:.2rem .5rem;border-radius:4px;font-size:.75rem;font-weight:bold}
.badge.ok{background:#2f9f6222;color:#6fdf9c}
.badge.warn{background:#f9a82522;color:#ffd97c}
.badge.critical{background:#ff525222;color:#ff9e9e}
.badge.offline{background:#444;color:#aaa}
</style>
</head>
<body>
<div class="top">
<h1>⚡ SAFE-ELEC — ระบบเฝ้าดูสถานะ</h1>
<div>{{ user }} <a href="/logout">ออกจากระบบ</a></div>
</div>

{% for dev in devices %}
<div class="dev-card">
<div class="dev-head">
<div><strong>{{ dev.device_id }}</strong> — {{ dev.site_name }} <small>({{ dev.province }})</small></div>
<div>
{% if dev.status_summary == 'online' %}
<span class="badge ok">✅ ปกติ</span>
{% elif dev.status_summary == 'warning' %}
<span class="badge warn">⚠️ แจ้งเตือน</span>
{% elif dev.status_summary == 'offline' %}
<span class="badge offline">❌ ไม่ออนไลน์</span>
{% else %}
<span class="badge critical">🔴 ผิดปกติ</span>
{% endif %}
<small>อัปเดต: {{ dev.last_updated }}</small>
</div>
</div>

<div class="grid">
{% for key, s in dev.sensors.items() %}
<div class="item {% if s.ok == true %}ok{% elif s.ok == false %}bad{% else %}warn{% endif %}">
<div class="name">{{ s.name }}</div>
<div class="val">
{% if s.value is number %}{{ "%.1f"|format(s.value) }}{% else %}{{ s.value }}{% endif %}
{% if s.unit %}{{ s.unit }}{% endif %}
{% if s.ok == true %}✅{% elif s.ok == false %}❌{% else %}⏳{% endif %}
</div>
</div>
{% endfor %}
</div>

{% if dev.fault_list %}
<div class="faults">
<strong>รายการแจ้งเตือน:</strong><br>
{% for f in dev.fault_list %}{{ f }}<br>{% endfor %}
</div>
{% endif %}
</div>
{% else %}
<p style="text-align:center;color:#888;padding:2rem">ไม่พบอุปกรณ์ที่เกี่ยวข้อง</p>
{% endfor %}

<script>
setInterval(()=>location.reload(), 5000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"✅ ระบบเริ่มทำงาน — รองรับอุปกรณ์จำนวนมาก")
    print(f"📊 จำนวนอุปกรณ์: {len(devices)} เครื่อง")
    print(f"📍 เพิ่ม/แก้ไขอุปกรณ์ที่: DEVICES_CONFIG")
    print(f"🔑 บัญชีตัวอย่าง: {list(ACCOUNTS.keys())}")
    print(f"🌐 เข้าใช้งาน: http://0.0.0.0:5000")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
