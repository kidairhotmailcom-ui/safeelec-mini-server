const express = require('express');
const mysql = require('mysql2/promise');
const nodemailer = require('nodemailer');
const ExcelJS = require('exceljs');
const cron = require('node-cron');
const { format } = require('date-fns');
const fs = require('fs');
const path = require('path');  

const app = express();
app.use('/static', express.static(path.join(__dirname, 'static')));
const port = process.env.PORT || 3000;

// === ตั้งค่าฐานข้อมูล ===
const db = mnysql.createPgitool({
  host: 'localhost',
  user: 'root',
  password: '',           // ใส่รหัสผ่าน MySQL ถ้ามี
  database: 'device_system'
});

// === ตั้งค่าส่งเมล ===
const transporter = nodemailer.createTransport({
  service: 'gmail',
  auth: {
    user: 'your-email@gmail.com',     // เปลี่ยนเป็นอีเมลจริง
    pass: 'your-app-password'        // ใส่รหัสผ่านแอป
  }
});

app.use(express.json());
app.use('/static', express.static('static'));

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
        to: cust[0].email,
        subject: `รายงาน ${report_id}`,
        text: 'แนบรายงานข้อมูลอุปกรณ์',
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
})
// === หน้าแรกแสดงโลโก้ ===
app.get('/', (req, res) => {
  res.send(`
<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PNS - เพชรนาคา ซิสเต็มเวิร์ก</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: linear-gradient(135deg, #00337A, #0052CC);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      font-family: sans-serif;
    }
    .box {
      background: white;
      padding: 40px 30px;
      border-radius: 24px;
      text-align: center;
      max-width: 480px;
      width: 100%;
      box-shadow: 0 10px 30px rgba(0,0,0,0.15);
    }
    .logo {
      max-width: 180px;
      width: 65%;
      height: auto;       /* รักษาสัดส่วน */
      display: block;  
      margin: 0 auto 20px;
    }
    h1 { color: #00337A; font-size: 1.5rem; margin-bottom: 8px; }
    .en { color: #666; font-size: 1rem; margin-bottom: 20px; }
    p { color: #444; font-size: 1.1rem; line-height: 1.6; }
  </style>
</head>
<body>
  <div class="box">
    <img src="pns-logo.png"
  alt="โลโก้ pns" class="logo">
    <h1>บริษัท เพชรนาคา ซิสเต็มเวิร์ก จำกัด</h1>
    <p class="en">PETCHNAKA SYSTEM WORK CO.,LTD.</p>
    <p>ระบบตรวจสอบและเฝ้าดูอุปกรณ์ไฟฟ้า</p>
  </div>
</body>
</html>
  `);
});

// อย่าลืมเช็คว่ามีบรรทัดนี้อยู่ท้ายสุดไฟล์นะ
app.listen(PORT, () => {
  console.log(`✅ ทำงานที่พอร์ต ${PORT}`);
});