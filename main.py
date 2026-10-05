from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # เปิดให้เรียกได้จากทุกที่

# ตัวแปรเก็บค่าล่าสุด
latest_data = {
    "device_id": "SAFE-00001",
    "current_temp": 0.0,
    "humidity": 0.0,
    "power_status": "MAIN AC",
    "wiring_fault": False
}

# ✅ รับข้อมูลจาก ESP32 (POST)
@app.route("/api/data", methods=["POST"])
def receive_data():
    global latest_data
    data = request.get_json(force=True)
    print("📥 รับข้อมูลจาก ESP32:", data)
    
    # อัปเดตค่าล่าสุด
    latest_data.update(data)
    return jsonify({"status": "success", "received": data}), 200

# ✅ ให้หน้าเว็บดึงข้อมูล (GET)
@app.route("/api/data", methods=["GET"])
def get_data():
    return jsonify(latest_data), 200

# ✅ หน้าแดชบอร์ด
@app.route("/")
def dashboard():
    return f"""
    <html>
        <body style="font-family:sans-serif; padding:20px; background:#f5f5f5;">
            <h1>SAFE-ELEC Dashboard</h1>
            <div style="background:white; padding:20px; border-radius:10px;">
                <h3>อุณหภูมิ: {latest_data['current_temp']} °C</h3>
                <h3>ความชื้น: {latest_data['humidity']} %</h3>
                <h3>สถานะไฟ: {latest_data['power_status']}</h3>
                <h3>สถานะสาย: {'ปกติ' if not latest_data['wiring_fault'] else 'ผิดปกติ'}</h3>
            </div>
            <p>อัปเดตล่าสุด: {latest_data}</p>
        </body>
    </html>
    """

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
