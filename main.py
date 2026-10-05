from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

devices = [
    {
        "device_id": "SAFE-TH001",
        "site": "CP_ALL_WOKWI_TEST",
        "current_temp": 0.0,
        "humidity": 0.0,
        "power_status": "ไฟหลัก AC",
        "last_updated": "-"
    },
    {
        "device_id": "SAFE-TH002",
        "site": "CP_ALL_KHONKAEN_MAIN",
        "current_temp": 0.0,
        "humidity": 0.0,
        "power_status": "ไฟหลัก AC",
        "last_updated": "-"
    },
    {
        "device_id": "SAFE-TH003",
        "site": "CPF_TEST_NODE",
        "current_temp": 0.0,
        "humidity": 0.0,
        "power_status": "ไฟหลัก AC",
        "last_updated": "-"
    }
]

@app.route("/api/data", methods=["POST"])
def receive_data():
    data = request.get_json(force=True)
    dev_id = data.get("device_id")
    for d in devices:
        if d["device_id"] == dev_id:
            d.update(data)
            d["last_updated"] = datetime.now().strftime("%H:%M:%S")
            break
    return jsonify({"status": "success"}), 200

@app.route("/api/devices", methods=["GET"])
def get_devices():
    return jsonify(devices), 200

@app.route("/")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>บอร์ดระบบคลาวด์ฟรี</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:sans-serif}
body{background:#0f1629;color:#fff;padding:20px}
h1{text-align:center;color:#6cf;margin-bottom:30px}
.card{background:#1a2342;border-radius:16px;padding:24px;margin-bottom:20px;border:1px solid #2a3563}
.head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.name{font-size:22px;font-weight:bold;color:#c9f}
.status{display:flex;align-items:center;gap:6px;color:#6f9;font-weight:bold}
.dot{width:10px;height:10px;border-radius:50%;background:#6f9}
.row{margin:12px 0;font-size:18px;display:flex;align-items:center;gap:10px}
</style>
</head>
<body>
<h1>บอร์ดระบบคลาวด์ฟรี</h1>
<div id="list"></div>
<script>
async function load(){
  const res=await fetch('/api/devices');
  const d=await res.json();
  const list=document.getElementById('list');
  list.innerHTML='';
  d.forEach(x=>{
    const t=x.current_temp>0?x.current_temp+' °C':'- °C';
    list.innerHTML+=`
      <div class="card">
        <div class="head">
          <div class="name">${x.device_id}</div>
          <div class="status"><span class="dot"></span> ACTIVE</div>
        </div>
        <div class="row">📍 Site: ${x.site}</div>
        <div class="row">🌡️ Temp: ${t}</div>
        <div class="row">⚡ Power: ${x.power_status}</div>
        <div class="row">⏰ อัปเดต: ${x.last_updated}</div>
      </div>
    `
  })
}
load();
setInterval(load, 10000);
</script>
</body>
</html>
    """)

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
