from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ==============================================================
# 📋 เพิ่ม-ลด-แก้ไข อุปกรณ์ได้ที่นี่ที่เดียว
# รูปแบบ: ("รหัสเครื่อง", "ชื่อสถานที่/สาขา", "รหัสลูกค้า", "จังหวัด")
# ==============================================================
DEVICE_LIST = [
    ("SAFE-TH001", "CP_ALL_WOKWI_TEST",        "CUST-0891", "ขอนแก่น"),
    ("SAFE-TH002", "CP_ALL_KHONKAEN_MAIN",     "CUST-0891", "ขอนแก่น"),
    ("SAFE-TH003", "CPF_TEST_NODE",            "CUST-0002", "กรุงเทพฯ"),
    # ✅ เพิ่มเครื่องที่ 4, 5, ... ตรงล่างนี้เลย
    # ("SAFE-TH004", "สาขาเชียงใหม่",            "CUST-0003", "เชียงใหม่"),
    # ("SAFE-TH005", "สาขาสงขลา",               "CUST-0004", "สงขลา"),
    # ("SAFE-TH006", "สาขานครราชสีมา",          "CUST-0005", "นครราชสีมา"),
    # ... เพิ่มได้ไม่จำกัด
]

# ==============================================================
# 🔧 ตั้งค่ามาตรฐานร่วมกันทุกเครื่อง (แก้ที่เดียว เปลี่ยนทั้งระบบ)
# ==============================================================
TEMPLATE = {
    "current_temp": 0.0,
    "humidity": 0.0,
    "voltage": 220.0,
    "current": 0.0,
    "power_w": 0.0,
    "resistance": 0.0,
    "power_status": "ไฟหลัก AC",
    "last_updated": "-",
    "branch_id": "BR-001",
    "device_pass": "A2K9M4P7",
    "wiring_fault": False,
    "hardware_gen_old": 1,
    "hardware_gen_new": 1,
    "critical_shutdown": False
}

# สร้างรายการอุปกรณ์อัตโนมัติ
devices = []
for dev_id, site, cust_id, prov in DEVICE_LIST:
    dev = TEMPLATE.copy()
    dev["device_id"] = dev_id
    dev["site"] = site
    dev["customer_id"] = cust_id
    dev["province"] = prov
    devices.append(dev)

# ==============================================================
# 🌐 API ส่งรับข้อมูล
# ==============================================================
@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.get_json(force=True)
    for x in devices:
        if x["device_id"] == d.get("device_id"):
            for k, v in d.items():
                x[k] = v
            x["last_updated"] = datetime.now().strftime("%H:%M:%S")
            break
    return jsonify({"ok": True})

@app.route("/api/devices", methods=["GET"])
def get_devices():
    return jsonify(devices)

# ==============================================================
# 📊 หน้าแดชบอร์ด
# ==============================================================
@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SAFE-ELEC — ระบบเฝ้าดูความปลอดภัยไฟฟ้า</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:20px}
h1{text-align:center;color:#6cf;margin-bottom:10px}
.subtitle{text-align:center;color:#99c;margin-bottom:30px}
.card{background:#1a2342;border-radius:16px;padding:24px;margin-bottom:16px;border:1px solid #2a3b63}
.name{font-size:20px;font-weight:bold;color:#c9f;margin-bottom:10px}
.row{margin:8px 0;font-size:15px}
.ok{color:#4f9}
.warn{color:#f84}
.search-bar{max-width:500px;margin:0 auto 25px}
.search-bar input{width:100%;padding:12px 16px;border-radius:10px;border:none;background:#1a2342;color:#fff;font-size:16px}
</style>
</head>
<body>
<h1>⚡ SAFE-ELEC — ระบบเฝ้าดูความปลอดภัยไฟฟ้า</h1>
<p class="subtitle">เชื่อมต่อทุกสาขาทั่วประเทศ</p>
<div class="search-bar">
  <input type="text" id="search" placeholder="🔍 ค้นหาตามรหัส/สถานที่/จังหวัด...">
</div>
<div id="list"></div>

<script>
let allDevices = [];
async function load(){
  const res = await fetch('/api/devices');
  allDevices = await res.json();
  render(allDevices);
}
function render(list){
  const container = document.getElementById('list');
  container.innerHTML = '';
  list.forEach(x => {
    container.innerHTML += `
    <div class="card">
      <div class="name">📟 ${x.device_id}</div>
      <div class="row">🏢 ลูกค้า: ${x.customer_id || '-'} | 📍 ${x.province || '-'}</div>
      <div class="row">🏠 สถานที่: ${x.site || '-'}</div>
      <div class="row">🌡️ อุณหภูมิ: ${x.current_temp} °C</div>
      <div class="row">💧 ความชื้น: ${x.humidity} %</div>
      <div class="row">⚡ แรงดัน: ${x.voltage || 220} V</div>
      <div class="row">🔌 กระแส: ${x.current || 0} A</div>
      <div class="row">💡 กำลังไฟ: ${x.power_w || 0} W</div>
      <div class="row">🧱 ความต้านทาน: ${x.resistance || 0} Ω</div>
      <div class="row">🔋 สถานะไฟ: ${x.power_status}</div>
      <div class="row ${x.wiring_fault ? 'warn' : 'ok'}">🔧 สายไฟ: ${x.wiring_fault ? '⚠️ ตรวจสอบ' : '✅ ปกติ'}</div>
      <div class="row ${x.critical_shutdown ? 'warn' : 'ok'}">🛑 ระบบ: ${x.critical_shutdown ? '⚠️ ตัดแล้ว' : '✅ ทำงานปกติ'}</div>
      <div class="row">⏰ อัปเดตล่าสุด: ${x.last_updated}</div>
    </div>`;
  });
}
document.getElementById('search').addEventListener('input', e => {
  const q = e.target.value.toLowerCase();
  render(allDevices.filter(x => 
    x.device_id.toLowerCase().includes(q) ||
    (x.site||'').toLowerCase().includes(q) ||
    (x.province||'').toLowerCase().includes(q)
  ));
});
load();
setInterval(load, 5000);
</script>
</body>
</html>
""")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
