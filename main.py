# ==============================================================================
# 🌐 SAFE-ELEC V1.7 - 7-ELEVEN & INDUSTRIAL NATIONAL FLEET COMMAND (PRODUCTION)
# ==============================================================================
from flask import Flask, jsonify, request, render_template_string
import sqlite3
from datetime import datetime, timezone

app = Flask(__name__)
DB_NAME = "safeelec_v1_7_perfect.db"


def init_v1_7_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # 📊 ฐานข้อมูลรองรับระบบไฟฟ้า 3 เฟส, แยกหมวดหมู่ธุรกิจ, แยกลูกเซอร์กิตย่อย และล็อกรหัสฮาร์ดแวร์เปลี่ยนรุ่น
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS industrial_fleet (
        device_id TEXT PRIMARY KEY, site_code TEXT, business_type TEXT, region TEXT, province TEXT,
        status TEXT, last_ping TEXT, temp_max TEXT, grid_status TEXT, gnd_leakage TEXT,
        system_mad_status TEXT, wiring_fault_status TEXT, sensor_1_id TEXT, pzem_a_id TEXT,
        v_a TEXT, a_a TEXT, r_a TEXT, v_b TEXT, a_b TEXT, r_b TEXT, v_c TEXT, a_c TEXT, r_c TEXT,
        cb1 TEXT, cb2 TEXT, cb3 TEXT, cb4 TEXT, cb5 TEXT, cb6 TEXT, daily_kwh TEXT, power_factor TEXT
    )
    ''')
    
    # 🏬 ลงทะเบียนข้อมูลตู้จำลองแยกหมวดหมู่สำหรับใช้รูดขายไอเดียพรีเซนต์งาน
    sample_nodes = [
        ('SAFE-TH001', 'STORE-14201', '🏪 ร้านสะดวกซื้อ 7-Eleven', 'ภาคอีสาน', 'ขอนแก่น', 'ACTIVE', '-', '41.5', 'MAIN AC', '0.00', 'OPERATIONAL', 'NORMAL_WIRING', '28-AA-7B-45-00-11', 'PZEM-V3.0', '220.1', '12.5', '17.6', '219.5', '11.8', '18.6', '220.8', '13.2', '16.7', '14.2', '15.1', '0.0', '8.4', '0.0', '19.5', '45.8', '0.88'),
        ('SAFE-PUB-S012', 'CLUB-00892', '🍹 สถานบันเทิง ผับ/บาร์', 'ภาคใต้', 'ภูเก็ต', 'ACTIVE', '-', '44.2', 'MAIN AC', '0.00', 'OPERATIONAL', 'NORMAL_WIRING', '28-AA-9C-88-22-33', 'PZEM-V3.0', '219.2', '45.4', '4.8', '218.6', '42.1', '5.1', '220.1', '44.8', '4.7', '22.4', '24.1', '35.0', '12.4', '8.5', '6.2', '124.5', '0.74'),
        ('SAFE-FAC-C005', 'FACTORY-99', '🏭 โรงงานอุตสาหกรรม', 'ภาคกลาง', 'ชลบุรี', 'ACTIVE', '-', '39.8', 'MAIN AC', '0.00', 'OPERATIONAL', 'NORMAL_WIRING', '28-BB-11-22-33-44', 'PZEM-V4.0', '222.4', '88.5', '2.5', '221.8', '84.2', '2.6', '223.1', '89.1', '2.4', '45.2', '52.4', '12.5', '0.0', '0.0', '0.0', '485.2', '0.81')
    ]
    cursor.executemany("INSERT OR IGNORE INTO industrial_fleet VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", sample_nodes)
    conn.commit()
    conn.close()

@app.route('/api/data', methods=['POST'])
def wokwi_direct_gateway():
    """ 📡 ท่อดักรับข้อมูล JSON ตรงจากบอร์ด Wokwi คุณพี่เพื่อแปรผลขึ้นระบบออนไลน์เรียลไทม์ """
    data = request.json
    if not data: return jsonify({"status": "ERROR"}), 400
    dev_id = data.get("device_id")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    cursor.execute('''
        UPDATE industrial_fleet 
        SET last_ping=?, temp_max=?, grid_status=?, gnd_leakage=?, system_mad_status=?, wiring_fault_status=?,
            sensor_1_id=?, pzem_a_id=?,
            v_a=?, a_a=?, r_a=?, v_b=?, a_b=?, r_b=?, v_c=?, a_c=?, r_c=?,
            cb1=?, cb2=?, cb3=?, cb4=?, cb5=?, cb6=?, daily_kwh=?, power_factor=?
        WHERE device_id=?
    ''', (utc_now, data.get("current_temp"), data.get("power_status"), data.get("gnd_leakage", "0.00"), data.get("system_mad_status", "OPERATIONAL"), data.get("wiring_fault_status", "NORMAL_WIRING"),
          data.get("sensor_1_id", "28-AA-7B-45-00-11"), data.get("pzem_a_id", "PZEM-V3.0"),
          data.get("v_a", "220.0"), data.get("a_a", "10.0"), data.get("r_a", "22.0"), data.get("v_b", "220.0"), data.get("a_b", "10.0"), data.get("r_b", "22.0"), data.get("v_c", "220.0"), data.get("a_c", "10.0"), data.get("r_c", "22.0"),
          data.get("cb1", "12.0"), data.get("cb2", "15.0"), data.get("cb3", "0.0"), data.get("cb4", "8.0"), data.get("cb5", "0.0"), data.get("cb6", "19.5"), data.get("daily_kwh", "45.8"), data.get("power_factor", "0.88"), dev_id))
    conn.commit()
    conn.close()
    return jsonify({"status": "SUCCESS"}), 200

@app.route('/global-fleet')
def global_fleet_dashboard():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM industrial_fleet ORDER BY business_type ASC, device_id ASC")
    all_nodes = cursor.fetchall()
    conn.close()

    html_layout = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SAFE-ELEC Infrastructure Console</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link rel="stylesheet" href="https://cloudflare.com">
        <style>
            body { font-family: Arial, sans-serif; background-color: #060913; color: #c9d1d9; padding: 12px; margin: 0; }
            .header { text-align: center; padding: 12px; background: #161b22; border-bottom: 2px solid #00ffff; border-radius: 6px; margin-bottom: 12px; }
            h2 { color: #00ffff; font-size: 13px; margin: 0; text-transform: uppercase; }
            .card { background-color: #121622; border: 1px solid #21263d; border-radius: 6px; padding: 14px; margin-bottom: 15px; }
            .biz-type { background: #00ffff; color: #0b0f19; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; }
            .section-title { font-size: 11px; color: #58a6ff; font-weight: bold; margin: 12px 0 5px 0; text-transform: uppercase; border-bottom: 1px solid #21263d; padding-bottom: 2px; }
            .row { display: flex; justify-content: space-between; font-size: 12px; margin: 4px 0; }
            .val-bold { font-weight: bold; color: #ffffff; }
            .cb-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 8px; }
            .cb-box { background: #1c2135; padding: 8px; border-radius: 4px; border: 1px solid #2d3554; text-align: center; font-size: 10px; }
            .cb-active { border-left: 4px solid #00ff66; }
            .cb-vacant { border-left: 4px solid #8b949e; color: #8b949e; }
            .cb-full { border-left: 4px solid #ff3333; background: #421c1c; animation: blinker 1.5s infinite; }
            .ai-box { background: #0b1a30; border: 1px solid #1c3d6e; padding: 10px; border-radius: 4px; margin-top: 10px; font-size: 11px; }
            .btn-buy { display: inline-block; background: #ff9800; color: #0d1117; padding: 4px 8px; text-decoration: none; border-radius: 3px; font-weight: bold; font-size: 10px; margin-top: 5px; text-transform: uppercase; }
            @keyframes blinker { 50% { opacity: 0.3; } }
        </style>
    </head>
    <body>
        <div class="header"><h2>📊 SAFE-ELEC ศูนย์ควบคุมโครงข่ายตู้ไฟฟ้า 3 เฟสระดับประเทศ (V1.7)</h2></div>
        
        {% for node in all_nodes %}
        <div class="card">
            <div class="row">
                <span class="val-bold" style="color:#00ffff;"><i class="fa-solid fa-building-shield"></i> {{ node[2] }}</span>
                <span class="biz-type">{{ node[2] }}</span>
            </div>
            <div class="row"><span>🆔 รหัสตู้ควบคุม:</span> <span class="val-bold">{{ node[0] }} (จังหวัด{{ node[4] }})</span></div>
            <div class="row"><span>🌡️ อุณหภูมิภายในตู้สูงสุด:</span> <span class="val-bold" style="color:#ff3333;">{{ node[7] }} °C</span></div>
            
            <div class="section-title">🔮 ระบบจัดเก็บและรองรับชิ้นส่วนอุปกรณ์ไอทีเปลี่ยนรุ่น (Auto/Manual Registry)</div>
            <div class="status-box" style="background:#161b22; padding:8px; border-radius:4px; font-size:10.5px; border:1px solid #232a3d;">
                <div>📌 รหัสโมดูลเซนเซอร์ (ROM ID): <span class="val-bold" style="color:#00ff66;">{{ node[12] }}</span></div>
                <div style="margin-top:4px;">⚡ โมเดลชิปมิเตอร์ 3 เฟส: <span class="val-bold" style="color:#00e6ff;">{{ node[13] }}</span></div>
                <div style="color:#8b949e; font-size:9.5px; margin-top:4px;"><i class="fa-solid fa-circle-info"></i> เปลี่ยนชิ้นส่วนไอทีต่างรุ่นข้ามคลาวด์ได้ระบบจะดึงรหัสลงทะเบียนออโต้ทันที [1.3]</div>
            </div>

            <div class="section-title">⚡ ผังไดอะแกรมแรงดันและความต้านทาน 3 เฟสเมนหลัก</div>
            <div class="row"><span>🔴 Phase A (L1):</span> <span class="val-bold">{{ node[14] }}V | {{ node[15] }}A | {{ node[16] }}Ω</span></div>
            <div class="row"><span>🟡 Phase B (L2):</span> <span class="val-bold">{{ node[17] }}V | {{ node[18] }}A | {{ node[19] }}Ω</span></div>
            <div class="row"><span>🔵 Phase C (L3):</span> <span class="val-bold">{{ node[20] }}V | {{ node[21] }}A | {{ node[22] }}Ω</span></div>
            <div class="row"><span>🟢 กระแสไฟรั่วลงดิน:</span> <span class="val-bold" style="color:#00ff66;">{{ node[9] }} mA</span></div>

            <div class="section-title">⚡ สถานะโหลดกระแสพ่วงแอมป์รายลูกเซอร์กิตย่อย (Branch Breakers)</div>
            <div class="cb-grid">
                {% for i in range(1, 7) %}
                {% set cb_val = node[22+i]|float %}
                <div class="cb-box {% if cb_val >= 20.0 %}cb-full{% elif cb_val > 0.1 %}cb-active{% else %}cb-vacant{% endif %}">
                    <b>ลูกย่อยที่ {{ i }}</b><br>
                    {% if cb_val >= 20.0 %}
                        ⚠️ โหลดเต็มพิกัด!<br><b style="color:#ff3333;">{{ cb_val }} A</b><br>🛑 ห้ามพ่วงเพิ่มเด็ดขาด
                    {% elif cb_val > 0.1 %}
                        🟢 ใช้งานปกติ<br><span style="color:#00ff66;">{{ cb_val }} A</span>
                    {% else %}
                        ⚫ ช่องว่าง (VACANT)<br><span style="color:#8b949e;">0.0 A</span>
                    {% endif %}
                </div>
                {% endfor %}
            </div>

            <div class="ai-box">
                <b style="color:#58a6ff;"><i class="fa-solid fa-brain"></i> AI วิเคราะห์กลยุทธ์ลดต้นทุนพลังงานและการใช้ไฟ (ENERGY REPORT)</b><br>

