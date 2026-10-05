from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ==============================================================
# 🎯 แผ่นเต็ม 100% — เพิ่มส่วนตรวจกราวด์ครบ
# ==============================================================
CONFIG = {
    "SYSTEM_NAME": "SAFE-ELEC PLATFORM",
    "VERSION": "2.1.0-FULL+GND",
    
    "FEATURES": {
        "basic_monitor": True,
        "sensor_check": True,
        "ground_check": True,          # ✅ ตรวจกราวด์ — เพิ่มใหม่
        "balance_check": True,
        "offline_alert": True,
        "data_log": False,
        "alert_notify": False,
        "user_permission": False,
        "energy_analysis": False,
        "predict_fault": False,
    },
    
    "STANDARD": {
        "V3_NOM": 380, "V3_MIN": 342, "V3_MAX": 418,
        "V1_NOM": 220, "V1_MIN": 198, "V1_MAX": 242,
        "TEMP_MIN": -10, "TEMP_MAX": 75, "TEMP_ALERT": 60,
        "HUMI_MIN": 20, "HUMI_MAX": 90,
        "BALANCE_MAX_A": 5.0, "BALANCE_MAX_PCT": 10.0,
        "OFFLINE_SEC": 90,
        # ✅ มาตรฐานกราวด์ — การไฟฟ้าไทย
        "GND_RESISTANCE_OK": 10.0,      # ≤ 10 Ω = ดีมาก
        "GND_RESISTANCE_WARN": 30.0,    # 10–30 Ω = ควรปรับปรุง
        "GND_VOLTAGE_OK": 2.0,          # ≤ 2V = ปกติ
    },
    
    "SITE_TYPES": {
        "convenience": "ร้านสะดวกซื้อ",
        "supermarket": "ห้างสรรพสินค้า",
        "factory": "โรงงาน",
        "hotel": "โรงแรม",
        "office": "อาคารสำนักงาน",
        "warehouse": "โกดัง",
        "other": "อื่นๆ"
    }
}

# ==============================================================
# 📋 รายการอุปกรณ์
# ==============================================================
DEVICE_LIST = [
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น", "office"),
    ("SAFE-002", "สาขาเชียงใหม่", "CUST-0002", "เชียงใหม่", "convenience"),
    ("SAFE-003", "โรงงานผลิต", "CUST-0004", "ระยอง", "factory"),
]

# ==============================================================
# 🔧 โครงสร้าง — เพิ่มส่วนกราวด์
# ==============================================================
TEMPLATE = {
    "device_id": "",
    "site_name": "",
    "customer_id": "",
    "province": "",
    "site_type": "",
    "last_updated": "-",
    "last_seen": None,
    "is_online": False,
    "status_summary": "unknown",
    
    # 📊 พื้นฐาน
    "current_temp": 0.0,
    "humidity": 0.0,
    "wiring_fault": False,
    "critical_shutdown": False,
    
    # ⚡ 380V
    "v_l1_l2": 380.0, "v_l2_l3": 380.0, "v_l3_l1": 380.0,
    "a_l1": 0.0, "a_l2": 0.0, "a_l3": 0.0, "a_n": 0.0,
    "power_kw": 0.0, "balance_3ph_ok": True,
    
    # 🔌 220V
    "z1_phase": 1, "z1_v": 220.0, "z1_a": 0.0, "z1_w": 0.0,
    "z2_phase": 2, "z2_v": 220.0, "z2_a": 0.0, "z2_w": 0.0,
    "z3_phase": 3, "z3_v": 220.0, "z3_a": 0.0, "z3_w": 0.0,
    "z_total_a": 0.0, "z_balance_ok": True,
    
    # 🌍 ✅ ส่วนตรวจกราวด์ — ใหม่
    "gnd_resistance_ohm": 0.0,       # ค่าความต้านทานกราวด์ Ω
    "gnd_voltage_v": 0.0,            # แรงดันรั่ว/ศักยภาพกราวด์ V
    "gnd_system_ok": True,            # ระบบกราวด์โดยรวมปกติไหม
    
    # 📋 สถานะเซนเซอร์ — เพิ่มกราวด์เข้าไป
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
        # ✅ กราวด์
        "gnd_resist":{"name": "กราวด์-ความต้านทาน", "value": 0.0, "unit": "Ω", "ok": True},
        "gnd_volt": {"name": "กราวด์-แรงดันรั่ว", "value": 0.0, "unit": "V", "ok": True},
        "comm":     {"name": "สื่อสาร", "value": "ปกติ", "ok": True},
    },
    
    "fault_list": [],
    "all_sensors_failed": False,
    "alert_level": "normal",
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
# 🔍 ตรวจกราวด์ — ตามมาตรฐานการไฟฟ้าไทย
# ==============================================================
def check_ground(dev):
    S = CONFIG["STANDARD"]
    F = CONFIG["FEATURES"]
    if not F["ground_check"]:
        return dev
    
    faults = []
    
    # 🌍 1. ตรวจความต้านทานกราวด์
    gr = dev["gnd_resistance_ohm"]
    dev["sensors"]["gnd_resist"]["value"] = gr
    
    if gr <= 0:
        dev["sensors"]["gnd_resist"]["ok"] = None  # ยังไม่ได้ติดตั้ง/เซนเซอร์ไม่อ่าน
    elif gr > S["GND_RESISTANCE_WARN"]:
        dev["sensors"]["gnd_resist"]["ok"] = False
        faults.append(f"🔴 กราวด์ไม่ดี! ความต้านทานสูง {gr}Ω (มาตรฐาน ≤ {S['GND_RESISTANCE_OK']}Ω)")
        dev["gnd_system_ok"] = False
    elif gr > S["GND_RESISTANCE_OK"]:
        dev["sensors"]["gnd_resist"]["ok"] = False
        faults.append(f"⚠️ กราวด์ควรปรับปรุง: {gr}Ω (เป้าหมาย ≤ {S['GND_RESISTANCE_OK']}Ω)")
    else:
        dev["sensors"]["gnd_resist"]["ok"] = True
    
    # 🌍 2. ตรวจแรงดันรั่วที่จุดกราวด์
    gv = dev["gnd_voltage_v"]
    dev["sensors"]["gnd_volt"]["value"] = gv
    
    if gv < 0:
        pass
    elif gv > S["GND_VOLTAGE_OK"]:
        dev["sensors"]["gnd_volt"]["ok"] = False
        faults.append(f"🔴 แรงดันรั่วที่กราวด์สูง: {gv}V (ปกติ ≤ {S['GND_VOLTAGE_OK']}V)")
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
# 🔍 ตรวจทั้งหมด
# ==============================================================
def check_all(dev):
    S = CONFIG["STANDARD"]
    faults = []
    
    # 🌍 ตรวจกราวด์ก่อน — สำคัญที่สุด
    faults.extend(check_ground(dev))
    
    # 🌡️ อุณหภูมิ
    t = dev["current_temp"]
    if t < S["TEMP_MIN"] or t > S["TEMP_MAX"]:
        faults.append(f"❌ อุณหภูมิผิดปกติ: {t}°C")
    elif t >= S["TEMP_ALERT"]:
        faults.append(f"⚠️ อุณหภูมิสูง: {t}°C")
    
    # 💧 ความชื้น
    h = dev["humidity"]
    if h < S["HUMI_MIN"] or h > S["HUMI_MAX"]:
        faults.append(f"❌ ความชื้นผิดปกติ: {h}%")
    
    # ⚡ แรงดัน 3 เฟส
    for name, val in [("L1-L2", dev["v_l1_l2"]), ("L2-L3", dev["v_l2_l3"]), ("L3-L1", dev["v_l3_l1"])]:
        if val < S["V3_MIN"] or val > S["V3_MAX"]:
            faults.append(f"❌ แรงดัน {name} ผิดปกติ: {val}V")
    
    # 🔌 แรงดัน 220V
    for z, val in [("โซน1", dev["z1_v"]), ("โซน2", dev["z2_v"]), ("โซน3", dev["z3_v"])]:
        if val < S["V1_MIN"] or val > S["V1_MAX"]:
            faults.append(f"❌ {z} แรงดันผิดปกติ: {val}V")
    
    # ⚖️ สมดุล
    dev["balance_3ph_ok"] = check_balance(dev["a_l1"], dev["a_l2"], dev["a_l3"])
    dev["z_total_a"] = round(dev["z1_a"] + dev["z2_a"] + dev["z3_a"], 2)
    dev["z_balance_ok"] = check_balance(dev["z1_a"], dev["z2_a"], dev["z3_a"])
    
    if not dev["balance_3ph_ok"]:
        faults.append("⚠️ ระบบ 380V ไม่สมดุล")
    if not dev["z_balance_ok"] and dev["z_total_a"] > 0:
        faults.append("⚠️ ระบบ 220V ไม่สมดุล")
    
    # 📊 ระดับรวม
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
# 🌐 API
# ==============================================================
@app.before_request
def update_online():
    now = datetime.now()
    for d in devices:
        if d["last_seen"]:
            sec = (now - d["last_seen"]).total_seconds()
            d["is_online"] = sec < CONFIG["STANDARD"]["OFFLINE_SEC"]
        else:
            d["is_online"] = False

@app.route("/api/data", methods=["POST"])
def receive():
    data = request.get_json(force=True)
    now = datetime.now()
    for d in devices:
        if d["device_id"] == data.get("device_id"):
            for k, v in data.items():
                if k not in ["sensors", "fault_list", "alert_level"]:
                    d[k] = v
            d["last_updated"] = now.strftime("%H:%M:%S")
            d["last_seen"] = now
            d["is_online"] = True
            d = check_all(d)
            break
    return jsonify({"ok": True, "alert_level": d["alert_level"]})

@app.route("/api/devices")
def get_devices():
    return jsonify(devices)

# ==============================================================
# 📊 หน้าแดชบอร์ด — มีส่วนกราวด์ชัดเจน
# ==============================================================
@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC — ตรวจกราวด์ครบระบบ</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:16px}
h1{text-align:center;color:#6cf;margin-bottom:8px}
.ver{text-align:center;color:#8ac;margin-bottom:20px;font-size:13px}
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
.search{max-width:450px;margin:0 auto 20px}
.search input{width:100%;padding:11px;border-radius:8px;border:none;background:#1a2342;color:#fff;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-top:10px}
.item{padding:8px 10px;border-radius:6px;background:#1e2b4d;font-size:13px}
.fbox{border:1px solid #f44;background:#2e1515;padding:12px;border-radius:8px;margin:10px 0}
.gnd-ok{border-left:3px solid #4f9;padding-left:10px}
.gnd-warn{border-left:3px solid #fa4;padding-left:10px}
.gnd-fail{border-left:3px solid #f44;padding-left:10px}
</style>
</head>
<body>
<h1>⚡ SAFE-ELEC PLATFORM</h1>
<div class="ver">ตรวจกราวด์ตามมาตรฐานการไฟฟ้าไทย — เวอร์ชัน {{ver}}</div>
<div class="search">
  <input id="q" placeholder="🔍 ค้นหารหัส / สถานที่ / กราวด์เสีย...">
</div>
<div id="list"></div>

<script>
let all = [];
async function load(){
  const res = await fetch('/api/devices');
  all = await res.json();
  render(all);
}
function getIcon(d){
  const m={online:'🟢',warning:'🟡',critical:'🔴',offline:'⚫'};
  return m[d.status_summary]||'❓';
}
function getGndClass(val,limit1,limit2){
  if(val<=0) return '';
  if(val>limit2) return 'gnd-fail';
  if(val>limit1) return 'gnd-warn';
  return 'gnd-ok';
}
function render(list){
  document.getElementById('list').innerHTML = list.map(d=>`
    <div class="card ${d.status_summary}">
      <div class="name">${getIcon(d)} ${d.device_id} — ${d.site_name}</div>
      <div class="meta">🏢 ${d.customer_id} | 📍 ${d.province} | ⏰ ${d.last_updated}</div>
      
      ${d.fault_list.length>0?`
      <div class="fbox">
        <b>⚠️ พบ ${d.fault_list.length} ปัญหา</b>
        ${d.fault_list.map(f=>`<div class="row">${f}</div>`).join('')}
      </div>`:''}
      
      <!-- 🌍 ส่วนกราวด์ -- สำคัญ -->
      <div class="section">
        <b>🌍 ระบบกราวด์ (มาตรฐาน ≤ 10Ω / ≤ 2V)</b>
        <div class="row ${getGndClass(d.gnd_resistance_ohm,10,30)}">
          ความต้านทานกราวด์: <b>${d.gnd_resistance_ohm>0?d.gnd_resistance_ohm+' Ω':'รอตรวจสอบ'}</b>
          ${d.gnd_resistance_ohm>30?'<span class="dang"> ⚠️ สูงผิดปกติ</span>':''}
          ${d.gnd_resistance_ohm>10&&d.gnd_resistance_ohm<=30?'<span class="warn"> ⚠️ ควรปรับปรุง</span>':''}
          ${d.gnd_resistance_ohm>0&&d.gnd_resistance_ohm<=10?'<span class="ok"> ✅ ปกติ</span>':''}
        </div>
        <div class="row ${d.gnd_voltage_v>2?'dang':d.gnd_voltage_v>0.5?'warn':'ok'}">
          แรงดันรั่วที่กราวด์: <b>${d.gnd_voltage_v>0?d.gnd_voltage_v+' V':'ปกติ'}</b>
          ${d.gnd_voltage_v>2?'<span class="dang"> ⚠️ สูงผิดปกติ</span>':''}
        </div>
        <div class="row">สถานะระบบกราวด์: ${d.gnd_system_ok?'<b class="ok">✅ ปกติ</b>':'<b class="dang">❌ ตรวจสอบทันที</b>'}</div>
      </div>
      
      <div class="section">
        <b>⚡ ตู้หลัก 380V</b>
        <div class="row">L1-L2: ${d.v_l1_l2}V | L2-L3: ${d.v_l2_l3}V | L3-L1: ${d.v_l3_l1}V</div>
        <div class="row">กระแส L1: ${d.a_l1}A | L2: ${d.a_l2}A | L3: ${d.a_l3}A | N: ${d.a_n}A</div>
        <div class="row">กำลัง: ${d.power_kw}kW | สมดุล: ${d.balance_3ph_ok?'✅ ปกติ':'⚠️ ไม่สมดุล'}</div>
      </div>
      
      <div class="section">
        <b>🔌 ตู้ย่อย 220V (3 โซน)</b>
        <div class="row">โซน1: ${d.z1_v}V | ${d.z1_a}A | ${d.z1_w}W</div>
        <div class="row">โซน2: ${d.z2_v}V | ${d.z2_a}A | ${d.z2_w}W</div>
        <div class="row">โซน3: ${d.z3_v}V | ${d.z3_a}A | ${d.z3_w}W</div>
        <div class="row">รวม: ${d.z_total_a}A | สมดุล: ${d.z_balance_ok?'✅ ปกติ':'⚠️ ไม่สมดุล'}</div>
      </div>
      
      <div class="section">
        <b>📋 สถานะเซนเซอร์ทั้งหมด</b>
        <div class="grid">
          ${Object.entries(d.sensors).map(([k,s])=>`
            <div class="item ${s.ok===true?'ok':s.ok===false?'dang':'warn'}">
              ${s.ok===true?'✅':s.ok===false?'❌':'⏳'} ${s.name}<br>
              <b>${s.value}${s.unit||''}</b>
            </div>
          `).join('')}
        </div>
      </div>
      
      <div class="row">🌡️ อุณหภูมิ: ${d.current_temp}°C | 💧 ความชื้น: ${d.humidity}%</div>
      <div class="row ${d.wiring_fault?'dang':'ok'}">สายไฟ: ${d.wiring_fault?'⚠️ ผิดปกติ':'✅ ปกติ'}</div>
      <div class="row ${d.critical_shutdown?'dang':'ok'}">ระบบ: ${d.critical_shutdown?'⚠️ ตัดแล้ว':'✅ ทำงานปกติ'}</div>
    </div>
  `).join('');
}
document.getElementById('q').oninput = e => {
  const kw = e.target.value.toLowerCase();
  render(all.filter(d => 
    d.device_id.toLowerCase().includes(kw) ||
    d.site_name.toLowerCase().includes(kw) ||
    d.customer_id.toLowerCase().includes(kw) ||
    d.province.toLowerCase().includes(kw) ||
    (kw.includes('กราวด์') && !d.gnd_system_ok)
  ));
};
load();
setInterval(load, 5000);
</script>
</body>
</html>
""", ver=CONFIG["VERSION"])

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  {CONFIG['SYSTEM_NAME']} — {CONFIG['VERSION']}")
    print(f"  🌍 ตรวจกราวด์: เปิด ✅")
    print(f"  📋 อุปกรณ์: {len(devices)} ชุด")
    print(f"{'='*60}\n")
    app.run(host="0.0.0.0", port=5000)
