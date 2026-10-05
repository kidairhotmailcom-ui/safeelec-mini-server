from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

devices = [
    {"device_id":"SAFE-TH001","site":"CP_ALL_WOKWI_TEST","current_temp":0.0,"humidity":0.0,"power_status":"ไฟหลัก AC","last_updated":"-"},
    {"device_id":"SAFE-TH002","site":"CP_ALL_KHONKAEN_MAIN","current_temp":0.0,"humidity":0.0,"power_status":"ไฟหลัก AC","last_updated":"-"},
    {"device_id":"SAFE-TH003","site":"CPF_TEST_NODE","current_temp":0.0,"humidity":0.0,"power_status":"ไฟหลัก AC","last_updated":"-"}
]

@app.route("/api/data", methods=["POST"])
def receive_data():
    d = request.get_json(force=True)
    for x in devices:
        if x["device_id"] == d.get("device_id"):
            x.update(d)
            x["last_updated"] = datetime.now().strftime("%H:%M:%S")
            break
    return jsonify({"ok":True})

@app.route("/api/devices")
def get_devices():
    return jsonify(devices)

@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>แดชบอร์ดอุปกรณ์</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:20px}
h1{text-align:center;color:#6cf;margin-bottom:30px}
.card{background:#1a2342;border-radius:16px;padding:24px;margin-bottom:16px;border:1px solid #2a3b63}
.name{font-size:20px;font-weight:bold;color:#c9f;margin-bottom:10px}
.row{margin:8px 0;font-size:16px}
</style>
</head>
<body>
<h1>📊 ข้อมูลอุปกรณ์</h1>
<div id="list"></div>
<script>
async function load(){
  const res=await fetch('/api/devices');
  const d=await res.json();
  const list=document.getElementById('list');
  list.innerHTML='';
  d.forEach(x=>{
    list.innerHTML+=`
    <div class="card">
      <div class="name">${x.device_id}</div>
      <div class="row">📍 สถานที่: ${x.site}</div>
      <div class="row">🌡️ อุณหภูมิ: ${x.current_temp} °C</div>
      <div class="row">💧 ความชื้น: ${x.humidity} %</div>
      <div class="row">⚡ สถานะไฟ: ${x.power_status}</div>
      <div class="row">⏰ อัปเดตล่าสุด: ${x.last_updated}</div>
    </div>`
  })
}
load();
setInterval(load, 5000);
</script>
</body>
</html>
""")

if __name__ == "__main__":
    app.run(host="0.0.0.0")
