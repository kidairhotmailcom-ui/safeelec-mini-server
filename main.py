from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_cors import CORS
from datetime import datetime

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
    "VERSION": "2.8.0-FIX-TEMP",
    "STANDARD": {
        "V3_NOM": 380, "V3_MIN": 342, "V3_MAX": 418,
        "V1_NOM": 220, "V1_MIN": 198, "V1_MAX": 242,
        "TEMP_MIN": -10, "TEMP_MAX": 75, "TEMP_ALERT": 60,
        "HUMI_MIN": 20, "HUMI_MAX": 90,
        "BALANCE_MAX_A": 5.0, "BALANCE_MAX_PCT": 10.0,
        "OFFLINE_SEC": 90,
        "GND_RES_OK": 10.0, "GND_RES_WARN": 30.0,
        "GND_V_OK": 2.0,
    },
    "SITE_TYPES": {
        "convenience": "ร้านสะดวกซื้อ", "shop": "ร้านค้าทั่วไป",
        "factory": "โรงงาน", "hotel": "โรงแรม", "office": "สำนักงาน",
    }
}

# ==============================================================
# 📋 รายการอุปกรณ์ — ✅ รองรับทั้ง 2 แบบ
# ==============================================================
DEVICE_LIST = [
    ("SAFE-001",      "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    ("SAFE-00001",    "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    ("SAFE-002",      "สาขาเชียงใหม่", "CUST-0002", "เชียงใหม่", "convenience"),
    ("SAFE-003",      "โรงงานผลิต", "CUST-0004", "ระยอง", "factory"),
]

# ==============================================================
# 📐 โครงสร้างข้อมูล — ✅ เพิ่ม power_status
# ==============================================================
TEMPLATE = {
    "device_id": "", "site_name": "", "customer_id": "",
    "province": "", "site_type": "",
    "last_updated": "-", "last_seen": None,
    "is_online": False, "status_summary": "unknown",
    
    "current_temp": 0.0, "humidity": 0.0,
    "power_status": "MAIN AC",  # ✅ เพิ่มตรงนี้
    "wiring_fault": False, "critical_shutdown": False,
    
    "v_l1_l2": 380.0, "v_l2_l3": 380.0, "v_l3_l1": 380.0,
    "a_l1": 0.0, "a_l2": 0.0, "a_l3": 0.0, "a_n": 0.0,
    "power_kw": 0.0, "balance_3ph_ok": True,
    
    "z1_v": 220.0, "z1_a": 0.0, "z1_w": 0.0,
    "z2_v": 220.0, "z2_a": 0.0, "z2_w": 0.0,
    "z3_v": 220.0, "z3_a": 0.0, "z3_w": 0.0,
    "z_total_a": 0.0, "z_balance_ok": True,
    
    "gnd_resistance_ohm": 0.0, "gnd_voltage_v": 0.0, "gnd_system_ok": True,
    
    "sensors": {
        "temp":      {"name": "อุณหภูมิตู้", "value": 0.0, "ok": True},
        "humidity":  {"name": "ความชื้น", "value": 0.0, "ok": True},
        "v_l1_l2":  {"name": "แรงดัน L1-L2", "value": 0.0, "ok": True},
        "v_l2_l3":  {"name": "แรงดัน L2-L3", "value": 0.0, "ok": True},
        "v_l3_l1":  {"name": "แรงดัน L3-L1", "value": 0.0, "ok": True},
        "a_l1":     {"name": "กระแสเฟส 1", "value": 0.0, "ok": True},
        "a_l2":     {"name": "กระแสเฟส 2", "value": 0.0, "ok": True},
        "a_l3":     {"name": "กระแสเฟส 3", "value": 0.0, "ok": True},
        "z1_v":     {"name": "โซน1 แรงดัน", "value": 0.0, "ok": True},
        "z1_a":     {"name": "โซน1 กระแส", "value": 0.0, "ok": True},
        "z2_v":     {"name": "โซน2 แรงดัน", "value": 0.0, "ok": True},
        "z2_a":     {"name": "โซน2 กระแส", "value": 0.0, "ok": True},
        "z3_v":     {"name": "โซน3 แรงดัน", "value": 0.0, "ok": True},
        "z3_a":     {"name": "โซน3 กระแส", "value": 0.0, "ok": True},
        "gnd_resist":{"name": "กราวด์-ความต้านทาน", "value": 0.0, "unit": "Ω", "ok": True},
        "gnd_volt": {"name": "กราวด์-แรงดันรั่ว", "value": 0.0, "unit": "V", "ok": True},
        "comm":     {"name": "สื่อสาร", "value": "ปกติ", "ok": True},
        "psu":      {"name": "แหล่งจ่ายภายใน", "value": "ปกติ", "ok": True},
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
# 🔍 ตรวจสอบ
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
    if gv < 0:
        pass
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

def check_all(dev):
    S = CONFIG["STANDARD"]
    faults = check_ground(dev)

    t = dev["current_temp"]
    dev["sensors"]["temp"]["value"] = t  # ✅ เชื่อมค่าอุณหภูมิตรงๆ
    if t < S["TEMP_MIN"] or t > S["TEMP_MAX"]:
        dev["sensors"]["temp"]["ok"] = False
        faults.append(f"❌ อุณหภูมิผิดปกติ: {t}°C")
    elif t >= S["TEMP_ALERT"]:
        dev["sensors"]["temp"]["ok"] = False
        faults.append(f"⚠️ อุณหภูมิสูง: {t}°C")
    else:
        dev["sensors"]["temp"]["ok"] = True

    h = dev["humidity"]
    dev["sensors"]["humidity"]["value"] = h
    dev["sensors"]["humidity"]["ok"] = S["HUMI_MIN"] <= h <= S["HUMI_MAX"]

    for k, v in [("v_l1_l2", dev["v_l1_l2"]), ("v_l2_l3", dev["v_l2_l3"]), ("v_l3_l1", dev["v_l3_l1"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = S["V3_MIN"] <= v <= S["V3_MAX"]

    for k, v in [("a_l1", dev["a_l1"]), ("a_l2", dev["a_l2"]), ("a_l3", dev["a_l3"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = True

    for k, v in [("z1_v", dev["z1_v"]), ("z2_v", dev["z2_v"]), ("z3_v", dev["z3_v"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = S["V1_MIN"] <= v <= S["V1_MAX"]

    for k, v in [("z1_a", dev["z1_a"]), ("z2_a", dev["z2_a"]), ("z3_a", dev["z3_a"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = True

    dev["balance_3ph_ok"] = check_balance(dev["a_l1"], dev["a_l2"], dev["a_l3"])
    dev["z_total_a"] = round(dev["z1_a"] + dev["z2_a"] + dev["z3_a"], 2)
    dev["z_balance_ok"] = check_balance(dev["z1_a"], dev["z2_a"], dev["z3_a"])

    if not dev["balance_3ph_ok"]:
        faults.append("⚠️ ระบบ 380V ไม่สมดุล")
    if not dev["z_balance_ok"] and dev["z_total_a"] > 0:
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
    return dev

# ==============================================================
# 🛡️ ตรวจสอบล็อกอิน
# ==============================================================
@app.before_request
def check_login():
    if request.path in ["/login", "/do_login", "/logout", "/api/data"]:
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

# ==============================================================
# 🌐 API รับข้อมูล — ✅ แก้จุดสำคัญที่สุด
# ==============================================================
@app.route("/api/data", methods=["GET"])
def get_data():
    # คืนค่าอุปกรณ์ตัวแรกที่เจอ หรือตาม query
    dev_id = request.args.get("device_id", "SAFE-00001")
    for d in devices:
        if d["device_id"] == dev_id:
            return jsonify({
                "device_id": d["device_id"],
                "current_temp": d["current_temp"],
                "humidity": d["humidity"],
                "power_status": d["power_status"],
                "wiring_fault": d["wiring_fault"]
            })
    return jsonify({"error": "Not found"}), 404

@app.route("/api/data", methods=["POST"])
def receive():
    data = request.get_json(force=True)
    now = datetime.now()
    
    # ✅ รองรับทั้ง SAFE-001 และ SAFE-00001 อัตโนมัติ
    dev_id = data.get("device_id", "")
    d = None
    for dev in devices:
        if dev["device_id"] == dev_id:
            d = dev
            break
    
    if not d:
        return jsonify({"ok": False, "error": f"Device not found: {dev_id}"}), 404
    
    # ✅ รับค่าอุณหภูมิ — ชื่อตรงกันทุกแบบ
    d["current_temp"] = data.get("current_temp", data.get("temperature", d["current_temp"]))
    d["humidity"] = data.get("humidity", data.get("humi", d["humidity"]))
    d["power_status"] = data.get("power_status", d["power_status"])
    d["wiring_fault"] = data.get("wiring_fault", d["wiring_fault"])
    d["critical_shutdown"] = data.get("critical_shutdown", d["critical_shutdown"])
    
    # 3 เฟส
    d["v_l1_l2"] = data.get("v_l1_l2", d["v_l1_l2"])
    d["v_l2_l3"] = data.get("v_l2_l3", d["v_l2_l3"])
    d["v_l3_l1"] = data.get("v_l3_l1", d["v_l3_l1"])
    d["a_l1"] = data.get("a_l1", d["a_l1"])
    d["a_l2"] = data.get("a_l2", d["a_l2"])
    d["a_l3"] = data.get("a_l3", d["a_l3"])
    d["a_n"] = data.get("a_n", d["a_n"])
    
    # กำลัง — รองรับ 2 ชื่อ
    d["power_kw"] = data.get("power_kw", data.get("power_3phase_kw", d["power_kw"]))
    d["balance_3ph_ok"] = data.get("balance_3ph_ok", data.get("balance_ok", d["balance_3ph_ok"]))
    
    # โซน 1-3 — รองรับทั้ง z และ sub
    d["z1_v"] = data.get("z1_v", data.get("sub1_v", d["z1_v"]))
    d["z1_a"] = data.get("z1_a", data.get("sub1_a", d["z1_a"]))
    d["z1_w"] = data.get("z1_w", data.get("sub1_w", d["z1_w"]))
    
    d["z2_v"] = data.get("z2_v", data.get("sub2_v", d["z2_v"]))
    d["z2_a"] = data.get("z2_a", data.get("sub2_a", d["z2_a"]))
    d["z2_w"] = data.get("z2_w", data.get("sub2_w", d["z2_w"]))
    
    d["z3_v"] = data.get("z3_v", data.get("sub3_v", d["z3_v"]))
    d["z3_a"] = data.get("z3_a", data.get("sub3_a", d["z3_a"]))
    d["z3_w"] = data.get("z3_w", data.get("sub3_w", d["z3_w"]))
    
    # กราวด์
    d["gnd_resistance_ohm"] = data.get("gnd_resistance_ohm", d["gnd_resistance_ohm"])
    d["gnd_voltage_v"] = data.get("gnd_voltage_v", d["gnd_voltage_v"])
    
    # อัปเดตเวลา
    d["last_updated"] = now.strftime("%H:%M:%S")
    d["last_seen"] = now
    d["is_online"] = True
    
    # ประมวลผล
    d = check_all(d)
    
    return jsonify({"ok": True, "device_id": dev_id, "current_temp": d["current_temp"]}), 200

@app.route("/api/devices")
def get_devices():
    my_cust = session.get("cust_id", "")
    if my_cust == "ALL":
        return jsonify(devices)
    my_list = [d for d in devices if d["customer_id"] == my_cust]
    return jsonify(my_list)

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
<div class="err">{{err}}</div>
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
# 📊 หน้าจอหลัก
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
</style>
</head>
<body>
<h1>⚡ SAFE-ELEC PLATFORM</h1>
<div class="ver">ตรวจสอบระบบไฟฟ้า — แก้ไขแล้วรองรับอุณหภูมิ ✅</div>
<div class="user-bar">👤 {{session['name']}} <a href="/logout">ออกจากระบบ</a></div>
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
function getGndClass(val){
  if(val<=0) return '';
  if(val>30) return 'gnd-fail';
  if(val>10) return 'gnd-warn';
  return 'gnd-ok';
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
    d.current_temp+'', d.humidity+''
  ].join(' ').toLowerCase();
  return searchText.includes(kw);
}
function applyFilterAndRender(){
  const kw = document.getElementById('q').value.trim().toLowerCase();
  const filtered = all.filter(d => matchDevice(d, kw));
  document.getElementById('result-info').innerHTML = 
    kw ? `พบ <b>${filtered.length}</b> จากทั้งหมด <b>${all.length}</b> รายการ` 
       : `ทั้งหมด <b>${all.length}</b> รายการ`;
  render(filtered);
}
function render(list){
  if(list.length === 0){
    document.getElementById('list').innerHTML = `<div class="no-result">ไม่พบข้อมูล 😔</div>`;
    return;
  }
  document.getElementById('list').innerHTML = list.map(d=>`
    <div class="card ${d.status_summary}">
      <div class="name">${getIcon(d)} ${d.device_id} — ${d.site_name}</div>
      <div class="meta">🏢 ${d.customer_id} | 📍 ${d.province} | ⏰ ${d.last_updated}</div>
      ${d.fault_list.length>0?`<div class="fbox"><b>⚠️ พบ ${d.fault_list.length} ปัญหา</b>${d.fault_list.map(f=>`<div class="row">${f}</div>`).join('')}</div>`:''}
      
      <div class="${currentView!=='mini'?'hidden':''}">
        <div class="section">
          <b>🌡️ สภาพแวดล้อม</b>
          <div class="row">อุณหภูมิ: <b class="${d.current_temp>=60?'dang':'ok'}">${d.current_temp}°C</b></div>
          <div class="row">ความชื้น: ${d.humidity}%</div>
          <div class="row">สถานะไฟ: ${d.power_status||'MAIN AC'}</div>
        </div>
        <div class="section">
          <b>📋 สถานะเซนเซอร์</b>
          <div class="grid">
            ${['temp','humidity','comm','psu'].map(k=>{
              const s=d.sensors[k];
              return `<div class="item ${s.ok===true?'ok':s.ok===false?'dang':'warn'}">
                ${getSensorIcon(s)} ${s.name}<br><b>${s.value}${s.unit||''}</b>
              </div>`;
            }).join('')}
          </div>
        </div>
      </div>
      
      <div class="${currentView!=='full'?'hidden':''}">
        <div class="section">
          <b>🌡️ สภาพแวดล้อม</b>
          <div class="row">อุณหภูมิ: <b class="${d.current_temp>=60?'dang':'ok'}">${d.current_temp}°C</b></div>
          <div class="row">ความชื้น: ${d.humidity}%</div>
          <div class="row">สถานะไฟ: ${d.power_status||'MAIN AC'}</div>
          <div class="row ${d.wiring_fault?'dang':'ok'}">สายไฟ: ${d.wiring_fault?'⚠️ ผิดปกติ':'✅ ปกติ'}</div>
        </div>
        <div class="section">
          <b>⚡ ตู้หลัก 380V</b>
          <div class="row">L1-L2: ${d.v_l1_l2}V | L2-L3: ${d.v_l2_l3}V | L3-L1: ${d.v_l3_l1}V</div>
          <div class="row">กระแส L1: ${d.a_l1}A | L2: ${d.a_l2}A | L3: ${d.a_l3}A</div>
          <div class="row">กำลัง: ${d.power_kw}kW | สมดุล: ${d.balance_3ph_ok?'✅ ปกติ':'⚠️ ไม่สมดุล'}</div>
        </div>
      </div>
    </div>
  `).join('');
}
document.getElementById('q').oninput = applyFilterAndRender;
load();
setInterval(load, 5000);
</script>
</body>
</html>
""", CONFIG_SITE_TYPES=CONFIG["SITE_TYPES"])

# ==============================================================
# 🚀 รัน
# ==============================================================
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  {CONFIG['SYSTEM_NAME']} — {CONFIG['VERSION']}")
    print(f"  ✅ รองรับ SAFE-001 / SAFE-00001")
    print(f"  ✅ รองรับ current_temp / humidity ตรงๆ")
    print(f"  ✅ เพิ่ม power_status รับและแสดงผล")
    print(f"  ✅ GET /api/data คืนค่าอุณหภูมิได้เลย")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=5000)
