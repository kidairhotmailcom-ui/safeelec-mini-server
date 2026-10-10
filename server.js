const express = require('express');
const mysql = require('mysql2/promise');
const nodemailer = require('nodemailer');
const ExcelJS = require('exceljs');
const cron = require('node-cron');
const { format } = require('date-fns');
const fs = require('fs');
const path = require('path');  

const app = express();

// === ตั้งค่าให้ระบบอ่านไฟล์สาธารณะ (Static Files) ===
app.use(express.static(__dirname));
app.use('/static', express.static(path.join(__dirname, 'static')));
app.use(express.json());
const port = process.env.PORT || 3000;

// === ตั้งค่าฐานข้อมูล ===
const db = mysql.createPool({
  host: 'localhost',
  user: 'root',
  password: '',
  database: 'device_system'
});

// === ตั้งค่าส่งเมล ===
const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: 'your-email@gmail.com',
    pass: 'your-app-password'
  }
});

// เพิ่มลูกค้า
app.post('/api/customers', async (req, res) => {
  try {
    const { customer_id, name, email, phone } = req.body;
    await db.query(
      'INSERT INTO customers VALUES (?, ?, ?, ?)',
      [customer_id, name, email, phone]
    );
    res.json({ok:true, message:'เพิ่มลูกค้าสำเร็จ'});
  } catch (e) { res.json({ok:false, error:e.message}); }
});

// เพิ่มอุปกรณ์
app.post('/api/devices', async (req, res) => {
  try {
    const { device_id, device_name, type, customer_id, serial_number } = req.body;
    await db.query(
      'INSERT INTO devices (device_id, device_name, type, customer_id, serial_number) VALUES (?,?,?,?,?)',
      [device_id, device_name, type, customer_id, serial_number]
    );
    res.json({ok:true, message:'เพิ่มอุปกรณ์สำเร็จ'});
  } catch (e) { res.json({ok:false, error:e.message}); }
});

// รับข้อมูลจาก ESP32
app.post('/api/esp/upload', async (req, res) => {
  try {
    const { device_id, temperature, humidity, voltage, current } = req.body;
    let status = 'normal';
    if (temperature > 40 || voltage < 200) status = 'warning';
    if (temperature > 50 || voltage < 190) status = 'critical';

    await db.query(
      'INSERT INTO esp_readings (device_id, temperature, humidity, voltage, current, status) VALUES (?,?,?,?,?,?)',
      [device_id, temperature, humidity, voltage, current, status]
    );
    res.json({ok:true, status});
  } catch (e) { res.json({ok:false, error:e.message}); }
});

// สร้างรายงาน Excel + ส่งเมล
app.post('/api/reports/generate-excel', async (req, res) => {
  try {
    const { customer_id, device_id, start_date, end_date, send_email } = req.body;
    const report_id = `RPT${Date.now()}`;

    const [readings] = await db.query(
      'SELECT * FROM esp_readings WHERE device_id=? AND recorded_at BETWEEN ? AND ?',
      [device_id, start_date, end_date+' 23:59:59']
    );
    const [cust] = await db.query('SELECT * FROM customers WHERE customer_id=?', [customer_id]);
    if (!cust.length) return res.json({ok:false, message:'ไม่พบลูกค้า'});

    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet('ข้อมูล');
    ws.columns = [
      {header:'เวลา', key:'time', width:20},
      {header:'อุณหภูมิ', key:'temp', width:12},
      {header:'ความชื้น', key:'hum', width:12},
      {header:'แรงดัน', key:'volt', width:12},
      {header:'กระแส', key:'amp', width:12},
      {header:'สถานะ', key:'st', width:12}
    ];
    readings.forEach(r => ws.addRow({
      time: format(new Date(r.recorded_at), 'yyyy-MM-dd HH:mm'),
      temp: r.temperature, hum: r.humidity, volt: r.voltage, amp: r.current, st: r.status
    }));

    fs.mkdirSync('./reports', {recursive:true});
    const filePath = `./reports/${report_id}.xlsx`;
    await wb.xlsx.writeFile(filePath);

    await db.query(
      'INSERT INTO reports (report_id, customer_id, device_id, start_date, end_date, file_path) VALUES (?,?,?,?,?,?)',
      [report_id, customer_id, device_id, start_date, end_date, filePath]
    );

    if (send_email) {
      await transporter.sendMail({
        to: cust.email,
        subject: `รายงาน ${report_id}`,
        text: 'แนบรายงานข้อมูลอุปกรณ์ไฟฟ้า',
        attachments: [{path: filePath}]
      });
      await db.query('UPDATE reports SET sent_at=NOW() WHERE report_id=?', [report_id]);
    }

    res.json({ok:true, report_id});
  } catch (e) { res.json({ok:false, error:e.message}); }
});

// ส่งรายงานอัตโนมัติ ทุกวันที่ 1 เดือนละครั้ง
cron.schedule('0 9 1 * *', async () => {
  console.log('เริ่มส่งรายงานประจำเดือน...');
  const [devices] = await db.query('SELECT DISTINCT device_id, customer_id FROM devices');
  const end = new Date();
  const start = new Date(end.getFullYear(), end.getMonth()-1, 1);
  const startStr = format(start, 'yyyy-MM-dd');
  const endStr = format(end, 'yyyy-MM-dd');
  
  for (const d of devices) {
    await fetch(`http://localhost:${port}/api/reports/generate-excel`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        customer_id: d.customer_id,
        device_id: d.device_id,
        start_date: startStr,
        end_date: endStr,
        send_email: true
      })
    });
  }
  console.log('ส่งรายงานเสร็จแล้ว');
});

// === หน้าแรกแบบปุ่มกดเข้าสู่ระบบ ดีไซน์สไตล์ Cyber-Tech ===
app.get('/', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PNS - เพชรนาคา ซิสเต็มเวิร์ก</title>
  <link rel="preconnect" href="https://googleapis.com">
  <link rel="preconnect" href="https://gstatic.com" crossorigin>
  <link href="https://googleapis.com/css2?family=Chakra+Petch:wght@300;400;600;700&family=Sarabun:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: radial-gradient(circle at top right, #0a2540 0%, #020c1b 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      font-family: 'Sarabun', sans-serif;
      color: #e6f1ff;
      overflow-x: hidden;
      position: relative;
    }
    body::before {
      content: ''; position: absolute; width: 500px; height: 500px;
      background: rgba(0, 98, 255, 0.15); border-radius: 50%;
      filter: blur(80px); top: 10%; left: 10%; z-index: 0;
    }
    .box {
      background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
      padding: 50px 40px; border-radius: 28px; text-align: center; max-width: 500px; width: 100%;
      border: 1px solid rgba(255, 255, 255, 0.08); box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
      position: relative; z-index: 1; transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .box:hover { transform: translateY(-5px); border-color: rgba(0, 98, 255, 0.3); box-shadow: 0 25px 60px rgba(0, 98, 255, 0.15); }
    .logo-container { background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 20px; display: inline-block; margin-bottom: 25px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2); }
    .logo { max-width: 140px; height: auto; display: block; }
    h1 { font-family: 'Chakra Petch', sans-serif; color: #ffffff; font-size: 1.6rem; font-weight: 700; margin-bottom: 6px; letter-spacing: 0.5px; }
    .en { font-family: 'Chakra Petch', sans-serif; color: #00d2ff; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 24px; }
    .divider { height: 2px; width: 60px; background: linear-gradient(90deg, #0062ff, #00d2ff); margin: 0 auto 24px; border-radius: 2px; }
    p { color: #a0aec0; font-size: 1.1rem; line-height: 1.6; margin-bottom: 35px; font-weight: 300; }
    .btn {
      display: flex; align-items: center; justify-content: center; gap: 10px;
      background: linear-gradient(135deg, #0062ff 0%, #004bd4 100%); color: white;
      padding: 16px 32px; font-size: 18px; border-radius: 14px; text-decoration: none;
      font-weight: 600; letter-spacing: 0.5px; transition: all 0.25s ease;
      box-shadow: 0 4px 15px rgba(0, 98, 255, 0.3); border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .btn:hover { background: linear-gradient(135deg, #1a75ff 0%, #0056f5 100%); transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 98, 255, 0.5); }
    .btn:active { transform: translateY(1px); }
    .btn-icon { font-size: 20px; }
  </style>
</head>
<body>
  <div class="box">
    <div class="logo-container">
      <img src="/865611D1-AE49-4F4F-9460-CA01F09BDD8E.png" alt="PNS เพชรนาคา ซิสเต็มเวิร์ค" class="logo">
    </div>
    <h1>บริษัท เพชรนาคา ซิสเต็มเวิร์ก จำกัด</h1>
    <p class="en">Petchnaka System Work Co.,Ltd.</p>
    <div class="divider"></div>
    <p>ระบบตรวจสอบและเฝ้าดูอุปกรณ์ไฟฟ้า<br><span style="font-size: 0.95rem; color: #718096;">Electrical Device Monitoring System</span></p>
    <a href="/login" class="btn">
      <span class="btn-icon">🔐</span> เข้าสู่ระบบ SAFE-ELEC
    </a>
  </div>
</body>
</html>
  `);
});

// === หน้าล็อกอินหลัก (Login Page) ที่ได้รับการฝังโลโก้ไว้ที่ยอดบนสุดตามรูปที่ส่งมา ===
app.get('/login', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>เข้าสู่ระบบ — SAFE-ELEC</title>
  <link rel="preconnect" href="https://googleapis.com">
  <link rel="preconnect" href="https://gstatic.com" crossorigin>
  <link href="https://googleapis.com/css2?family=Chakra+Petch:wght@600;700&family=Sarabun:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #0d1624;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      font-family: 'Sarabun', sans-serif;
    }
    .login-box {
      background: #192231;
      padding: 40px 30px;
      border-radius: 20px;
      max-width: 420px;
      width: 100%;
