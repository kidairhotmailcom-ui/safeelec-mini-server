from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ==============================================================
# 📋 รายการอุปกรณ์ — เพิ่มได้เรื่อยๆ
# ==============================================================
DEVICE_LIST = [
    ("SAFE-001", "แผงหลัก+ย่อย อาคารหลัก", "CUST-0891", "ขอนแก่น"),
    ("SAFE-002", "แผงหลัก+ย่อย สาขาเชียงใหม่", "CUST-0002", "เชียงใหม่"),
    # เพิ่มตรงนี้
]

# ==============================================================
# 🔧 โครงสร้างมาตรฐาน — เพิ่มส่วนสมดุล 220V
# ==============================================================
TEMPLATE = {
    "last_updated": "-",
    "power_status": "ออนไลน์",
    "current_temp": 0.0,
    "humidity": 0.0,
    "wiring_fault": False,
    "critical_shutdown": False,
    "customer_id": "",
    "branch_id": "",
    "province": "",
    "site": "",
    
    # ⚡ ระบบตู้หลัก 3 เฟส 380V
    "v_l1_l2": 380.0,
    "v_l2_l3": 380.0,
    "v_l3_l1": 380.0,
    "a_l1": 0.0,
    "a_l2": 0.0,
    "a_l3": 0.0,
    "a_n": 0.0,
    "power_3phase_kw": 0.0,
    "balance_ok": True,
    
    # 🔌 ระบบตู้ย่อย 220V (3 โซน) — เพิ่มฟิลด์ใหม่
    "sub1_phase": 1,
    "sub1_v": 220.0,
    "sub1_a": 0.0,
    "sub1_w": 0.0,
    
    "sub2_phase": 2,
    "sub2_v": 220.0,
    "sub2_a": 0.0,
    "sub2_w": 0.0,
    
    "sub3_phase": 3,
    "sub3_v": 220.0,
    "sub3_a": 0.0,
    "sub3_w": 0.0,
    
    # ✅ เพิ่มส่วนสมดุล 220V
    "sub_total_a": 0.0,
    "sub_balance_ok": True,
}

# สร้างรายการอัตโนมัติ
devices = []
for dev_id, site, cust, prov in DEVICE_LIST:
    d = TEMPLATE.copy()
    d["device_id"] = dev_id
    d["site"] = site
    d["customer_id"] = cust
    d["province"] = prov
    devices.append(d)

# ==============================================================
# 🌐 API — เพิ่มตรรกะคำนวณสมดุล 220V
# ==============================================================
@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.get_json(force=True)
    for x in devices:
        if x["device_id"] == d.get("device_id"):
            # อัปเดตค่าที่ส่งมา
            for k, v in d.items():
                x[k] = v
            x["last_updated"] = datetime.now().strftime("%H:%M:%S")
            
            # ✅ คำนวณกระแสรวม + เช็คสมดุล 220V
            a1 = x["sub1_a"]
            a2 = x["sub2_a"]
            a3 = x["sub3_a"]
            
            x["sub_total_a"] = round(a1 + a2 + a3, 2)
            
            # เช็คสมดุล: ค่าแต่ละเฟสห่างจากค่าเฉลี่ยไม่เกิน 0.5A
            total = a1 + a2 + a3
            if total > 0:
                avg = total / 3
                threshold = 0.5  # เกณฑ์ความคลาดเคลื่อนที่ยอมรับได้ (A)
                x["sub_balance_ok"] = (
                    abs(a1 - avg) <= threshold and
                    abs(a2 - avg) <= threshold and
                    abs(a3 - avg) <= threshold
                )
            else:
                x["sub_balance_ok"] = True  # ไม่มีโหลด = ถือว่าสมดุล
            
            break
    return jsonify({"ok": True})

@app.route("/api/devices")
def get_devices():
    return jsonify(devices)

# ==============================================================
# 📊 หน้าแดชบอร์ด — แสดงสมดุล 220V
# ==============================================================
@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC — 380V+220V ครบชุด</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:20px}
h1{text-align:center;color:#6cf;margin-bottom:25px}
.card{background:#1a2342;border-radius:16px;padding:20px;margin-bottom:16px;border:1px solid #2a3b63}
.name{font-size:19px;font-weight:bold;color:#c9f;margin-bottom:12px}
.section{margin:12px 0;padding:10px;border-radius:10px;background:#0f1f3f}
.row{margin:6px 0;font-size:14px}
.ok{color:#4f9}
.warn{color:#f84}
.search{max-width:400px;margin:0 auto 20px}
.search input{width:100%;padding:10px;border-radius:8px;border:none;background:#1a2342;color:#fff}
</style>
</head>
<body>
<h1>⚡ SAFE-ELEC — ระบบ 380V + 220V ครบชุด</h1>
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
      <div class="name">📟 ${x.device_id} — ${x.site}</div>
      <div class="row">🏢 ${x.customer_id} | 📍 ${x.province} | ⏰ ${x.last_updated}</div>
      
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
        <!-- ✅ เพิ่มบรรทัดแสดงสมดุล 220V -->
        <div class="row">กระแสรวม: ${x.sub_total_a} A | สมดุล: ${x.sub_balance_ok ? '✅ ปกติ' : '⚠️ ไม่สมดุล'}</div>
      </div>
      
      <div class="row">🌡️ อุณหภูมิ: ${x.current_temp}°C | 💧 ความชื้น: ${x.humidity}%</div>
      <div class="row ${x.wiring_fault ? 'warn' : 'ok'}">สายไฟ: ${x.wiring_fault ? '⚠️ ผิดปกติ' : '✅ ปกติ'}</div>
      <div class="row ${x.critical_shutdown ? 'warn' : 'ok'}">ระบบ: ${x.critical_shutdown ? '⚠️ ตัดแล้ว' : '✅ ทำงานปกติ'}</div>
    </div>
  `).join('');
}
document.getElementById('q').oninput = e => {
  const kw = e.target.value.toLowerCase();
  render(all.filter(x => x.device_id.toLowerCase().includes(kw) || x.site.toLowerCase().includes(kw)));
};
load();
setInterval(load, 5000);
</script>
</body>
</html>
""")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
