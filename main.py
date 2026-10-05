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
}

# ==============================================================
# ⚙️ ค่าคงที่
# ==============================================================
CONFIG = {
    "SYSTEM_NAME": "SAFE-ELEC",
    "VERSION": "3.0.0-ESP-BACKUP",
    "STANDARD": {
        "V3_NOM": 380, "V3_MIN": 342, "V3_MAX": 418,
        "V1_NOM": 220, "V1_MIN": 198, "V1_MAX": 242,
        "TEMP_MIN": -10, "TEMP_MAX": 75, "TEMP_ALERT": 60,
        "HUMI_MIN": 20, "HUMI_MAX": 90,
        "BALANCE_MAX_A": 5.0, "BALANCE_MAX_PCT": 10.0,
        "OFFLINE_SEC": 90,       # หลังจากหมดเวลานี้ ถือว่า ESP หลักเสีย
        "BACKUP_ACTIVE_SEC": 15,  # เวลารอหลัง ESP สำรองทำงาน
        "GND_RES_OK": 10.0, "GND_RES_WARN": 30.0,
        "GND_V_OK": 2.0,
    },
}

# ==============================================================
# 📋 รายการอุปกรณ์
# ==============================================================
DEVICE_LIST = [
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
]

# ==============================================================
# 📐 โครงสร้างข้อมูล — เพิ่มฟิลด์ ESP สำรอง
# ==============================================================
TEMPLATE = {
    "device_id": "", "site_name": "", "customer_id": "",
    "province": "", "site_type": "",
    "last_updated": "-", "last_seen": None,
    "is_online": False, "status_summary": "offline",
    
    # === ระบบ ESP หลัก/สำรอง ===
    "esp_main_status": "online",      # online / fault / replaced
    "esp_backup_active": False,       # True = กำลังใช้ตัวสำรอง
    "esp_backup_since": None,         # เวลาที่เปลี่ยนไปใช้สำรอง
    "esp_replaced_at": None,          # เวลาที่เปลี่ยนตัวใหม่แล้ว
    
    "current_temp": 0.0, "humidity": 0.0,
    "power_status": "MAIN AC",
    
    "v_l1_l2": 380.0, "v_l2_l3": 380.0, "v_l3_l1": 380.0,
    "a_l1": 0.0, "a_l2": 0.0, "a_l3": 0.0,
    "z1_v": 220.0, "z1_a": 0.0, "z2_v": 220.0, "z2_a": 0.0,
    "gnd_resistance_ohm": 0.0, "gnd_voltage_v": 0.0,
    
    "sensors": {
        "temp":      {"name": "อุณหภูมิตู้", "value": 0.0, "ok": None},
        "humidity":  {"name": "ความชื้น", "value": 0.0, "ok": None},
        "comm":      {"name": "สื่อสาร", "value": "ไม่เชื่อมต่อ", "ok": None},
        "psu":       {"name": "แหล่งจ่ายภายใน", "value": "ตรวจสอบ", "ok": None},
        "esp":       {"name": "อุปกรณ์ ESP", "value": "ไม่เชื่อมต่อ", "ok": None},
        "a_l1":     {"name": "กระแสเฟส 1", "value": 0.0, "ok": None},
        "a_l2":     {"name": "กระแสเฟส 2", "value": 0.0, "ok": None},
        "a_l3":     {"name": "กระแสเฟส 3", "value": 0.0, "ok": None},
        "v_l1_l2":  {"name": "แรงดัน L1-L2", "value": 0.0, "ok": None},
        "v_l2_l3":  {"name": "แรงดัน L2-L3", "value": 0.0, "ok": None},
        "v_l3_l1":  {"name": "แรงดัน L3-L1", "value": 0.0, "ok": None},
        "z1_v":     {"name": "โซน1 แรงดัน", "value": 0.0, "ok": None},
        "z1_a":     {"name": "โซน1 กระแส", "value": 0.0, "ok": None},
        "z2_v":     {"name": "โซน2 แรงดัน", "value": 0.0, "ok": None},
        "z2_a":     {"name": "โซน2 กระแส", "value": 0.0, "ok": None},
        "gnd_resist":{"name": "กราวด์-ความต้านทาน", "value": 0.0, "unit": "Ω", "ok": None},
        "gnd_volt": {"name": "กราวด์-แรงดันรั่ว", "value": 0.0, "unit": "V", "ok": None},
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
# 🔍 ตรวจสอบสถานะ ESP หลัก/สำรอง
# ==============================================================
def check_esp_status(dev):
    """
    ตรวจสอบและตั้งสถานะ ESP:
    - ออนไลน์ปกติ → "เชื่อมต่อปกติ" ✅
    - ขาดการติดต่อเกินเวลา → เปลี่ยนเป็น ESP สำรอง ⚠️
    - ส่งสัญญาณเปลี่ยนใหม่ → กลับเป็นปกติ ✅
    """
    now = datetime.now()
    S = CONFIG["STANDARD"]
    
    if dev["last_seen"]:
        sec_since_seen = (now - dev["last_seen"]).total_seconds()
        dev["is_online"] = sec_since_seen < S["OFFLINE_SEC"]
    else:
        dev["is_online"] = False
        sec_since_seen = 9999
    
    # 1. ESP กลับมาออนไลน์หลังจากเคยเสีย → แจ้งเปลี่ยนเรียบร้อย
    if dev["is_online"] and dev["esp_main_status"] in ["fault", "recovering"]:
        if dev["esp_replaced_at"]:
            dev["esp_main_status"] = "replaced"
            dev["esp_backup_active"] = False
            dev["sensors"]["esp"]["value"] = "✅ ESP เปลี่ยนใหม่ — ปกติ"
            dev["sensors"]["esp"]["ok"] = True
        else:
            dev["esp_main_status"] = "online"
            dev["esp_backup_active"] = False
            dev["sensors"]["esp"]["value"] = "เชื่อมต่อปกติ"
            dev["sensors"]["esp"]["ok"] = True
    
    # 2. ESP ขาดการติดต่อเกินเวลา → เปิดโหมดสำรอง
    elif not dev["is_online"] and sec_since_seen >= S["OFFLINE_SEC"]:
        if dev["esp_main_status"] == "online":
            dev["esp_main_status"] = "fault"
            dev["esp_backup_active"] = True
            dev["esp_backup_since"] = now
        elif dev["esp_main_status"] == "fault":
            # ยังใช้สำรองอยู่
            dev["sensors"]["esp"]["value"] = "⚠️ ใช้โหมด ESP สำรอง – รอเปลี่ยน"
            dev["sensors"]["esp"]["ok"] = False
            dev["sensors"]["comm"]["value"] = "ทำงานผ่านสำรอง"
            dev["sensors"]["comm"]["ok"] = False
            dev["sensors"]["psu"]["value"] = "ตรวจสอบ"
            dev["sensors"]["psu"]["ok"] = None
    
    # 3. ยังไม่เคยเชื่อมต่อเลย
    else:
        dev["sensors"]["esp"]["value"] = "ไม่เชื่อมต่อ"
        dev["sensors"]["esp"]["ok"] = None
        dev["sensors"]["comm"]["value"] = "ไม่เชื่อมต่อ"
        dev["sensors"]["comm"]["ok"] = None
        dev["sensors"]["psu"]["value"] = "ตรวจสอบ"
        dev["sensors"]["psu"]["ok"] = None

# ==============================================================
# 🔍 ตรวจสอบเซนเซอร์อื่นๆ
# ==============================================================
def check_sensors(dev):
    S = CONFIG["STANDARD"]
    faults = []
    
    # อุณหภูมิ
    t = dev["current_temp"]
    dev["sensors"]["temp"]["value"] = t
    if t != 0:
        if t < S["TEMP_MIN"] or t > S["TEMP_MAX"]:
            dev["sensors"]["temp"]["ok"] = False
            faults.append(f"❌ อุณหภูมิผิดปกติ: {t}°C")
        elif t >= S["TEMP_ALERT"]:
            dev["sensors"]["temp"]["ok"] = False
            faults.append(f"⚠️ อุณหภูมิสูง: {t}°C")
        else:
            dev["sensors"]["temp"]["ok"] = True
    else:
        dev["sensors"]["temp"]["ok"] = None
    
    # ความชื้น
    h = dev["humidity"]
    dev["sensors"]["humidity"]["value"] = h
    if h != 0:
        dev["sensors"]["humidity"]["ok"] = S["HUMI_MIN"] <= h <= S["HUMI_MAX"]
    else:
        dev["sensors"]["humidity"]["ok"] = None
    
    # แรงดัน 3 เฟส
    for k, v in [("v_l1_l2", dev["v_l1_l2"]), ("v_l2_l3", dev["v_l2_l3"]), ("v_l3_l1", dev["v_l3_l1"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = S["V3_MIN"] <= v <= S["V3_MAX"] if v != 0 else None
    
    # กระแส
    for k, v in [("a_l1", dev["a_l1"]), ("a_l2", dev["a_l2"]), ("a_l3", dev["a_l3"])]:
        dev["sensors"][k]["value"] = v
        dev["sensors"][k]["ok"] = True if v != 0 else None
    
    # กราวด์
    gr = dev["gnd_resistance_ohm"]
    dev["sensors"]["gnd_resist"]["value"] = gr
    if gr > 0:
        if gr > S["GND_RES_WARN"]:
            dev["sensors"]["gnd_resist"]["ok"] = False
            faults.append(f"🔴 กราวด์ไม่ดี! {gr}Ω")
        elif gr > S["GND_RES_OK"]:
            dev["sensors"]["gnd_resist"]["ok"] = False
            faults.append(f"⚠️ กราวด์ควรปรับปรุง: {gr}Ω")
        else:
            dev["sensors"]["gnd_resist"]["ok"] = True
    else:
        dev["sensors"]["gnd_resist"]["ok"] = None
    
    gv = dev["gnd_voltage_v"]
    dev["sensors"]["gnd_volt"]["value"] = gv
    if gv > 0:
        dev["sensors"]["gnd_volt"]["ok"] = True if gv <= S["GND_V_OK"] else False
    else:
        dev["sensors"]["gnd_volt"]["ok"] = None
    
    return faults

# ==============================================================
# ✅ ตรวจสอบทั้งหมด
# ==============================================================
def check_all(dev):
    check_esp_status(dev)
    faults = check_sensors(dev)
    
    # สรุประดับความสำคัญ
    if dev["esp_backup_active"]:
        dev["status_summary"] = "warning"
        dev["alert_level"] = "warning"
        faults.insert(0, "⚠️ กำลังใช้ ESP สำรอง — กรุณาเปลี่ยนอุปกรณ์หลัก")
    elif not dev["is_online"]:
        dev["status_summary"] = "offline"
        dev["alert_level"] = "critical"
    elif any("🔴" in f for f in faults):
        dev["status_summary"] = "critical"
        dev["alert_level"] = "critical"
    elif any("⚠️" in f for f in faults):
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
    if request.path in ["/login", "/do_login", "/logout", "/api/data", "/api/replace-esp"]:
        return
    if "username" not in session:
        return redirect("/login")

@app.before_request
def update_status():
    for d in devices:
        check_all(d)

# ==============================================================
# 🌐 API รับข้อมูล
# ==============================================================
@app.route("/api/data", methods=["POST"])
def receive():
    data = request.get_json(force=True)
    now = datetime.now()
    
    dev_id = data.get("device_id", "")
    d = next((dev for dev in devices if dev["device_id"] == dev_id), None)
    
    if not d:
        return jsonify({"ok": False, "error": f"ไม่พบอุปกรณ์: {dev_id}"}), 404
    
    # อัปเดตค่าทุกอย่าง
    d["current_temp"] = data.get("current_temp", d["current_temp"])
    d["humidity"] = data.get("humidity", d["humidity"])
    d["v_l1_l2"] = data.get("v_l1_l2", d["v_l1_l2"])
    d["v_l2_l3"] = data.get("v_l2_l3", d["v_l2_l3"])
    d["v_l3_l1"] = data.get("v_l3_l1", d["v_l3_l1"])
    d["a_l1"] = data.get("a_l1", d["a_l1"])
    d["a_l2"] = data.get("a_l2", d["a_l2"])
    d["a_l3"] = data.get("a_l3", d["a_l3"])
    d["z1_v"] = data.get("z1_v", d["z1_v"])
    d["z1_a"] = data.get("z1_a", d["z1_a"])
    d["z2_v"] = data.get("z2_v", d["z2_v"])
    d["z2_a"] = data.get("z2_a", d["z2_a"])
    d["gnd_resistance_ohm"] = data.get("gnd_resistance_ohm", d["gnd_resistance_ohm"])
    d["gnd_voltage_v"] = data.get("gnd_voltage_v", d["gnd_voltage_v"])
    
    d["last_updated"] = now.strftime("%H:%M:%S")
    d["last_seen"] = now
    
    # ถ้ามี flag บอกว่าเปลี่ยน ESP แล้ว
    if data.get("esp_replaced", False):
        d["esp_replaced_at"] = now
        d["esp_main_status"] = "recovering"
    
    check_all(d)
    return jsonify({"ok": True, "esp_status": d["esp_main_status"]}), 200

# ==============================================================
# 🔧 API แจ้งเปลี่ยน ESP
# ==============================================================
@app.route("/api/replace-esp", methods=["POST"])
def replace_esp():
    """เรียกเมื่อเปลี่ยนตัว ESP ใหม่เสร็จแล้ว"""
    data = request.get_json(force=True)
    dev_id = data.get("device_id", "")
    d = next((dev for dev in devices if dev["device_id"] == dev_id), None)
    
    if not d:
        return jsonify({"ok": False, "error": "ไม่พบอุปกรณ์"}), 404
    
    d["esp_replaced_at"] = datetime.now()
    d["esp_main_status"] = "recovering"
    d["esp_backup_active"] = False
    
    return jsonify({
        "ok": True,
        "message": "บันทึกการเปลี่ยน ESP เรียบร้อย — รอสัญญาณจากอุปกรณ์เพื่อกลับสู่สถานะปกติ"
    })

@app.route("/api/devices")
def get_devices():
    my_cust = session.get("cust_id", "")
    list_filtered = devices if my_cust == "ALL" else [d for d in devices if d["customer_id"] == my_cust]
    return jsonify(list_filtered)

# ==============================================================
# 📲 ล็อกอิน
# ==============================================================
@app.route("/login")
def login():
    err = request.args.get("err", "")
    return render_template_string("""
<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>เข้าสู่ระบบ — SAFE-ELEC</title>
<style>body{background:#0f1629;color:#fff;font-family:sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh}.box{background:#1a2342;padding:30px;border-radius:16px;width:100%;max-width:400px;border:1px solid #2a3b63}h2{text-align:center;color:#6cf;margin-bottom:25px}input{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:none;background:#0f1f3f;color:#fff;font-size:16px}button{width:100%;padding:12px;background:#2f9;border:none;border-radius:8px;color:#032;font-weight:bold;font-size:16px;margin-top:10px;cursor:pointer}.err{color:#f44;text-align:center;margin-top:15px}</style>
</head><body><div class="box"><h2>🔐 เข้าสู่ระบบ SAFE-ELEC</h2><form method="post" action="/do_login"><input type="text" name="user" placeholder="ชื่อผู้ใช้" required><input type="password" name="pwd" placeholder="รหัสผ่าน" required><button type="submit">เข้าสู่ระบบ</button><div class="err">{{err}}</div></form></div></body></html>
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
<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>SAFE-ELEC PLATFORM</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:16px}
h1{text-align:center;color:#6cf;margin-bottom:4px}
.ver{text-align:center;color:#8ac;margin-bottom:12px}
.user-bar{text-align:right;margin-bottom:12px;padding:8px 12px;background:#1a2342;border-radius:8px;font-size:14px}
.user-bar a{color:#f66;text-decoration:none;margin-left:12px}
.card{background:#1a2342;border-radius:16px;padding:16px;margin-bottom:16px;border:1px solid #2a3b63}
.card.online{border-left:4px solid #4f9}
.card.warning{border-left:4px solid #fa4;background:#2a2618}
.card.critical{border-left:4px solid #f44;background:#2e1515}
.card.offline{border-left:4px solid #666;opacity:0.85}
.name{font-size:17px;font-weight:bold;color:#c9f;margin-bottom:8px}
.meta{font-size:13px;color:#aaa;margin-bottom:10px}
.section{margin:12px 0;padding:12px;border-radius:10px;background:#0f1f3f}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-top:10px}
.item{padding:8px 10px;border-radius:6px;background:#1e2b4d;font-size:13px}
.ok{color:#4f9}
.warn{color:#fa4}
.dang{color:#f44}
.fbox{border:1px solid #f44;background:#2e1515;padding:12px;border-radius:8px;margin:10px 0}
.backup-banner{background:#3a2a00;border:1px solid #fc3;border-radius:8px;padding:10px;margin:10px 0;text-align:center;font-weight:bold;color:#ffc}
.replace-btn{background:#2f9;color:#032;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-weight:bold;margin-top:8px}
</style>
</head><body>
<h1>⚡ SAFE-ELEC PLATFORM</h1>
<div class="ver">ระบบตรวจสอบ + ESP สำรองอัตโนมัติ</div>
<div class="user-bar">👤 {{session['name']}} <a href="/logout">ออกจากระบบ</a></div>
<div id="list"></div>
<script>
let all = [];

function getIcon(d){
  const m={online:'🟢',warning:'🟡',critical:'🔴',offline:'⚫'};
  return m[d.status_summary]||'❓';
}
function getSensorIcon(s){
  if(s.ok===true) return '✅';
  if(s.ok===false) return '❌';
  return '⏳';
}
async function load(){
  const res = await fetch('/api/devices');
  all = await res.json();
  render();
}
function render(){
  document.getElementById('list').innerHTML = all.map(d=>`
    <div class="card ${d.status_summary}">
      <div class="name">${getIcon(d)} ${d.device_id} — ${d.site_name}</div>
      <div class="meta">📍 ${d.province} | ⏰ อัปเดตล่าสุด: ${d.last_updated}</div>
      
      ${d.esp_backup_active ? `
      <div class="backup-banner">
        ⚠️ กำลังใช้ ESP สำรอง — กรุณาเปลี่ยนอุปกรณ์หลัก<br>
        <button class="replace-btn" onclick="reportReplace('${d.device_id}')">✅ เปลี่ยน ESP ใหม่แล้ว</button>
      </div>` : ''}
      
      ${d.fault_list.length>0 ? `
      <div class="fbox"><b>📋 รายการแจ้งเตือน</b>
        ${d.fault_list.map(f=>`<div>${f}</div>`).join('')}
      </div>` : ''}
      
      <div class="section">
        <b>📋 ทุกเซนเซอร์</b>
        <div class="grid">
          ${Object.entries(d.sensors).map(([k,s])=>`
            <div class="item ${s.ok===true?'ok':s.ok===false?'dang':'warn'}">
              ${getSensorIcon(s)} ${s.name}<br><b>${s.value}${s.unit||''}</b>
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `).join('');
}
async function reportReplace(devId){
  if(!confirm('ยืนยันเปลี่ยน ESP ใหม่?')) return;
  await fetch('/api/replace-esp', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({device_id: devId})
  });
  alert('บันทึกแล้ว! รอสัญญาณจากอุปกรณ์จะกลับเป็นปกติ');
  load();
}
load();
setInterval(load, 5000);
</script>
</body></html>
""")

# ==============================================================
# 🚀 รัน
# ==============================================================
if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  {CONFIG['SYSTEM_NAME']} — {CONFIG['VERSION']}")
    print(f"  ✅ เซนเซอร์มีค่าแล้วแสดงทันที ไม่ต้องรอ")
    print(f"  ✅ ESP หลักเสีย → แสดง: ⚠️ ใช้โหมด ESP สำรอง – รอเปลี่ยน")
    print(f"  ✅ กดปุ่ม/ส่งสัญญาณเปลี่ยน → รับข้อมูลครั้งถัดไปแสดง ✅ ปกติ")
    print(f"  ⏳ หากยังไม่มีข้อมูลจริง → แสดงนาฬิกาทราย ไม่แจ้งผิด")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=5000)
