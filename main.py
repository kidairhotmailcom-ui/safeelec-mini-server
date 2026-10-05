from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ==============================================================
# 📋 รายการอุปกรณ์หลัก
# ==============================================================
DEVICE_LIST = [
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น"),
    ("SAFE-002", "แผงหลัก+ย่อย สาขาเชียงใหม่", "CUST-0002", "เชียงใหม่"),
]

# ==============================================================
# 🎯 เกณฑ์มาตรฐานระบบไฟฟ้าไทย
# ==============================================================
STANDARD = {
    "TEMP_MIN": -10, "TEMP_MAX": 75, "TEMP_ALERT": 60,
    "HUMI_MIN": 20, "HUMI_MAX": 90,
    "V3_NOM": 380, "V3_TOL": 0.10,
    "V1_NOM": 220, "V1_TOL": 0.10,
    "BAL_DIFF_A": 5.0, "BAL_RATIO": 0.10,
    "OFFLINE_SEC": 90,
}

# ==============================================================
# 🔧 โครงสร้าง — มีรายการอุปกรณ์ภายในตู้ครบทุกชิ้น
# ==============================================================
TEMPLATE = {
    "last_updated": "-",
    "last_seen": None,
    "is_online": False,
    
    "current_temp": 0.0,
    "humidity": 0.0,
    "wiring_fault": False,
    "critical_shutdown": False,
    "customer_id": "", "province": "", "site": "",
    
    # ⚡ ตู้หลัก 380V
    "v_l1_l2": 380.0, "v_l2_l3": 380.0, "v_l3_l1": 380.0,
    "a_l1": 0.0, "a_l2": 0.0, "a_l3": 0.0, "a_n": 0.0,
    "power_3phase_kw": 0.0, "balance_ok": True,
    
    # 🔌 ตู้ย่อย 220V
    "sub1_phase": 1, "sub1_v": 220.0, "sub1_a": 0.0, "sub1_w": 0.0,
    "sub2_phase": 2, "sub2_v": 220.0, "sub2_a": 0.0, "sub2_w": 0.0,
    "sub3_phase": 3, "sub3_v": 220.0, "sub3_a": 0.0, "sub3_w": 0.0,
    "sub_total_a": 0.0, "sub_balance_ok": True,
    
    # 📋 รายการตรวจ — ทุกอุปกรณ์ภายในตู้
    "checklist": {
        # เซนเซอร์วัดค่า
        "s_temp":       {"name": "เซนเซอร์อุณหภูมิ", "value": 0.0, "ok": True},
        "s_humi":       {"name": "เซนเซอร์ความชื้น", "value": 0.0, "ok": True},
        "s_v_l1_l2":    {"name": "เซนเซอร์แรงดัน L1-L2", "value": 0.0, "ok": True},
        "s_v_l2_l3":    {"name": "เซนเซอร์แรงดัน L2-L3", "value": 0.0, "ok": True},
        "s_v_l3_l1":    {"name": "เซนเซอร์แรงดัน L3-L1", "value": 0.0, "ok": True},
        "s_a_l1":       {"name": "เซนเซอร์กระแสเฟส 1", "value": 0.0, "ok": True},
        "s_a_l2":       {"name": "เซนเซอร์กระแสเฟส 2", "value": 0.0, "ok": True},
        "s_a_l3":       {"name": "เซนเซอร์กระแสเฟส 3", "value": 0.0, "ok": True},
        "s_a_n":        {"name": "เซนเซอร์กระแสสายศูนย์", "value": 0.0, "ok": True},
        "s_sub1_v":     {"name": "ตู้ย่อย1 — เซนเซอร์แรงดัน", "value": 0.0, "ok": True},
        "s_sub1_a":     {"name": "ตู้ย่อย1 — เซนเซอร์กระแส", "value": 0.0, "ok": True},
        "s_sub2_v":     {"name": "ตู้ย่อย2 — เซนเซอร์แรงดัน", "value": 0.0, "ok": True},
        "s_sub2_a":     {"name": "ตู้ย่อย2 — เซนเซอร์กระแส", "value": 0.0, "ok": True},
        "s_sub3_v":     {"name": "ตู้ย่อย3 — เซนเซอร์แรงดัน", "value": 0.0, "ok": True},
        "s_sub3_a":     {"name": "ตู้ย่อย3 — เซนเซอร์กระแส", "value": 0.0, "ok": True},
        # อุปกรณ์ควบคุม/ปิดเปิด
        "r_main":       {"name": "รีเลย์/เบรกเกอร์ตู้หลัก", "value": True, "ok": True},
        "r_sub1":       {"name": "รีเลย์ตู้ย่อยที่ 1", "value": True, "ok": True},
        "r_sub2":       {"name": "รีเลย์ตู้ย่อยที่ 2", "value": True, "ok": True},
        "r_sub3":       {"name": "รีเลย์ตู้ย่อยที่ 3", "value": True, "ok": True},
        "comms":        {"name": "ระบบสื่อสาร/WiFi", "value": True, "ok": True},
        "psu":          {"name": "แหล่งจ่ายไฟภายในตู้", "value": True, "ok": True},
    },
    "fault_list": [],
    "all_sensors_failed": False,  # ✅ แจ้งกรณีเซนเซอร์ทั้งหมดเสีย
}

devices = []
for dev_id, site, cust, prov in DEVICE_LIST:
    d = TEMPLATE.copy()
    d["device_id"] = dev_id
    d["site"] = site
    d["customer_id"] = cust
    d["province"] = prov
    devices.append(d)

# ==============================================================
# 🔍 ตรวจสอบทุกอุปกรณ์ — แยกชัดเจน
# ==============================================================
def check_all(dev):
    S = STANDARD
    cl = dev["checklist"]
    faults = []
    
    # 🌡️ อุณหภูมิ
    t = dev["current_temp"]
    cl["s_temp"]["value"] = t
    cl["s_temp"]["ok"] = S["TEMP_MIN"] <= t <= S["TEMP_MAX"]
    if not cl["s_temp"]["ok"]:
        faults.append(f"❌ {cl['s_temp']['name']}: ค่า {t}°C อยู่นอกช่วงปกติ")
    elif t >= S["TEMP_ALERT"]:
        faults.append(f"⚠️ {cl['s_temp']['name']}: อุณหภูมิสูง {t}°C")
    
    # 💧 ความชื้น
    h = dev["humidity"]
    cl["s_humi"]["value"] = h
    cl["s_humi"]["ok"] = S["HUMI_MIN"] <= h <= S["HUMI_MAX"]
    if not cl["s_humi"]["ok"]:
        faults.append(f"❌ {cl['s_humi']['name']}: ค่า {h}% อยู่นอกช่วงปกติ")
    
    # ⚡ แรงดัน 3 เฟส
    v3_min = S["V3_NOM"] * (1 - S["V3_TOL"])
    v3_max = S["V3_NOM"] * (1 + S["V3_TOL"])
    v3_items = [
        ("s_v_l1_l2", dev["v_l1_l2"]),
        ("s_v_l2_l3", dev["v_l2_l3"]),
        ("s_v_l3_l1", dev["v_l3_l1"]),
    ]
    for key, val in v3_items:
        cl[key]["value"] = val
        cl[key]["ok"] = v3_min <= val <= v3_max
        if not cl[key]["ok"]:
            faults.append(f"❌ {cl[key]['name']}: {val}V (ปกติ {v3_min:.0f}–{v3_max:.0f}V)")
    
    # ⚡ กระแส 3 เฟส
    a_items = [
        ("s_a_l1", dev["a_l1"]),
        ("s_a_l2", dev["a_l2"]),
        ("s_a_l3", dev["a_l3"]),
        ("s_a_n", dev["a_n"]),
    ]
    for key, val in a_items:
        cl[key]["value"] = val
        cl[key]["ok"] = val >= -5 and val <= 200  # ค่าลบผิดปกติ/เกินพิกัด
        if not cl[key]["ok"]:
            faults.append(f"❌ {cl[key]['name']}: ค่าผิดปกติ {val}A")
    
    # 🔌 ตู้ย่อย
    v1_min = S["V1_NOM"] * (1 - S["V1_TOL"])
    v1_max = S["V1_NOM"] * (1 + S["V1_TOL"])
    sub_items = [
        ("s_sub1_v", dev["sub1_v"], v1_min, v1_max),
        ("s_sub1_a", dev["sub1_a"], -5, 100),
        ("s_sub2_v", dev["sub2_v"], v1_min, v1_max),
        ("s_sub2_a", dev["sub2_a"], -5, 100),
        ("s_sub3_v", dev["sub3_v"], v1_min, v1_max),
        ("s_sub3_a", dev["sub3_a"], -5, 100),
    ]
    for key, val, lo, hi in sub_items:
        cl[key]["value"] = val
        cl[key]["ok"] = lo <= val <= hi
        if not cl[key]["ok"]:
            faults.append(f"❌ {cl[key]['name']}: ค่าผิดปกติ {val}")
    
    # ⚖️ สมดุล
    dev["balance_ok"] = check_balance(dev["a_l1"], dev["a_l2"], dev["a_l3"])
    if not dev["balance_ok"]:
        faults.append("⚠️ ระบบ 380V ไม่สมดุล")
    
    sa1, sa2, sa3 = dev["sub1_a"], dev["sub2_a"], dev["sub3_a"]
    dev["sub_total_a"] = round(sa1 + sa2 + sa3, 2)
    dev["sub_balance_ok"] = check_balance(sa1, sa2, sa3)
    if not dev["sub_balance_ok"] and dev["sub_total_a"] > 0:
        faults.append("⚠️ ระบบ 220V ไม่สมดุล")
    
    # ✅ ตรวจกรณีเซนเซอร์ทั้งหมดเสีย
    sensor_keys = [k for k in cl.keys() if k.startswith("s_")]
    failed_sensors = [k for k in sensor_keys if not cl[k]["ok"]]
    dev["all_sensors_failed"] = len(failed_sensors) == len(sensor_keys)
    
    if dev["all_sensors_failed"]:
        faults.insert(0, "🔴 !!! แจ้งเตือนสำคัญ: เซนเซอร์ทั้งหมดในระบบทำงานผิดปกติ !!!")
    
    # อุปกรณ์อื่นๆ
    cl["comms"]["ok"] = dev["is_online"]
    cl["comms"]["value"] = "เชื่อมต่อ" if dev["is_online"] else "ขาดการติดต่อ"
    if not dev["is_online"]:
        faults.append("❌ ระบบสื่อสารขาดการติดต่อ")
    
    dev["fault_list"] = faults
    return dev

def check_balance(i1, i2, i3):
    total = i1 + i2 + i3
    if total <= 0: return True
    avg = total / 3
    for v in [i1, i2, i3]:
        if abs(v - avg) > STANDARD["BAL_DIFF_A"]: return False
        if avg > 0 and abs(v - avg) / avg > STANDARD["BAL_RATIO"]: return False
    return True

# ==============================================================
# 🌐 API
# ==============================================================
@app.before_request
def update_online():
    now = datetime.now()
    for d in devices:
        if d["last_seen"]:
            sec = (now - d["last_seen"]).total_seconds()
            d["is_online"] = sec < STANDARD["OFFLINE_SEC"]
        else:
            d["is_online"] = False

@app.route("/api/data", methods=["POST"])
def receive():
    data = request.get_json(force=True)
    now = datetime.now()
    for d in devices:
        if d["device_id"] == data.get("device_id"):
            for k, v in data.items():
                if k not in ["checklist", "fault_list"]:
                    d[k] = v
            d["last_updated"] = now.strftime("%H:%M:%S")
            d["last_seen"] = now
            d["is_online"] = True
            d = check_all(d)
            break
    return jsonify({"ok": True})

@app.route("/api/devices")
def get_devices():
    return jsonify(devices)

# ==============================================================
# 📊 หน้าแดชบอร์ด — แสดงทุกอย่างชัดเจน
# ==============================================================
@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC — ตรวจครบทุกอุปกรณ์</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:16px}
h1{text-align:center;color:#6cf;margin-bottom:20px;font-size:20px}
.card{background:#1a2342;border-radius:16px;padding:16px;margin-bottom:16px;border:1px solid #2a3b63}
.name{font-size:18px;font-weight:bold;color:#c9f;margin-bottom:10px}
.section{margin:12px 0;padding:12px;border-radius:10px;background:#0f1f3f}
.row{margin:5px 0;font-size:14px;line-height:1.5}
.ok{color:#4f9}
.warn{color:#f84}
.crit{color:#f44;font-weight:bold;background:#3a1515;padding:6px;border-radius:6px;margin:4px 0}
.search{max-width:400px;margin:0 auto 20px}
.search input{width:100%;padding:10px;border-radius:8px;border:none;background:#1a2342;color:#fff;font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-top:10px}
.item{padding:8px 10px;border-radius:6px;background:#1e2b4d;font-size:13px}
.fault-box{border:1px solid #f44;background:#2e1515;padding:12px;border-radius:8px;margin:10px 0}
</style>
</head>
<body>
<h1>⚡ SAFE-ELEC — ตรวจครบทุกอุปกรณ์ภายในตู้</h1>
<div class="search"><input id="q" placeholder="🔍 ค้นหารหัส/สถานที่..."></div>
<div id="list"></div>

<script>
let all = [];
async function load(){
  const res = await fetch('/api/devices');
  all = await res.json();
  render(all);
}
function render(list){
  document.getElementById('list').innerHTML = list.map(x => `
    <div class="card">
      <div class="name">
        ${x.is_online ? '🟢' : '🔴'} ${x.device_id} — ${x.site}
        ${!x.is_online ? '<span class="warn"> ⚠️ ขาดการติดต่อ</span>' : ''}
      </div>
      <div class="row">🏢 ${x.customer_id} | 📍 ${x.province} | ⏰ ${x.last_updated}</div>
      
      ${x.all_sensors_failed ? `
      <div class="crit">
        🔴 เซนเซอร์ทั้งหมดในระบบเสีย/ขัดข้อง — กรุณาตรวจสอบทันที!
      </div>` : ''}
      
      ${x.fault_list.length > 0 ? `
      <div class="fault-box">
        <b>⚠️ พบ ${x.fault_list.length} รายการผิดปกติ</b>
        ${x.fault_list.map(f => `<div class="row warn">${f}</div>`).join('')}
      </div>` : ''}
      
      <div class="section">
        <b>⚡ ตู้หลัก 3 เฟส 380V</b>
        <div class="row">L1-L2: ${x.v_l1_l2} V | L2-L3: ${x.v_l2_l3} V | L3-L1: ${x.v_l3_l1} V</div>
        <div class="row">กระแส L1: ${x.a_l1} A | L2: ${x.a_l2} A | L3: ${x.a_l3} A | N: ${x.a_n} A</div>
        <div class="row">กำลังรวม: ${x.power_3phase_kw} kW | สมดุล: ${x.balance_ok ? '✅ ปกติ' : '⚠️ ไม่สมดุล'}</div>
      </div>
      
      <div class="section">
        <b>🔌 ตู้ย่อย 220V (3 โซน)</b>
        <div class="row">โซน1 (เฟส${x.sub1_phase}): ${x.sub1_v}V | ${x.sub1_a}A | ${x.sub1_w}W</div>
        <div class="row">โซน2 (เฟส${x.sub2_phase}): ${x.sub2_v}V | ${x.sub2_a}A | ${x.sub2_w}W</div>
        <div class="row">โซน3 (เฟส${x.sub3_phase}): ${x.sub3_v}V | ${x.sub3_a}A | ${x.sub3_w}W</div>
        <div class="row">กระแสรวม: ${x.sub_total_a} A | สมดุล: ${x.sub_balance_ok ? '✅ ปกติ' : '⚠️ ไม่สมดุล'}</div>
      </div>
      
      <div class="section">
        <b>📋 สถานะอุปกรณ์และเซนเซอร์ทั้งหมด</b>
        <div class="grid">
          ${Object.entries(x.checklist).map(([k, s]) => `
            <div class="item ${s.ok ? 'ok' : 'warn'}">
              ${s.ok ? '✅' : '❌'} ${s.name}<br>
              <b>${s.value}</b>
            </div>
          `).join('')}
        </div>
      </div>
      
      <div class="row">🌡️ อุณหภูมิ: ${x.current_temp}°C | 💧 ความชื้น: ${x.humidity}%</div>
      <div class="row ${x.wiring_fault ? 'warn' : 'ok'}">สายไฟ: ${x.wiring_fault ? '⚠️ ผิดปกติ' : '✅ ปกติ'}</div>
      <div class="row ${x.critical_shutdown ? 'warn' : 'ok'}">ระบบ: ${x.critical_shutdown ? '⚠️ ตัดแล้ว' : '✅ ทำงานปกติ'}</div>
    </div>
  `).join('');
}
document.getElementById('q').oninput = e => {
  const kw = e.target.value.toLowerCase();
  render(all.filter(x => 
    x.device_id.toLowerCase().includes(kw) || 
    x.site.toLowerCase().includes(kw) ||
    x.customer_id.toLowerCase().includes(kw)
  ));
};
load();
setInterval(load, 5000);
</script>
</body>
</html>
""")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
