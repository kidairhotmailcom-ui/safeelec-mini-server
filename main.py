# ==================== ตรวจสอบเข้าสู่ระบบ ====================
@app.route("/do_login", methods=["POST"])
def do_login():
    user = request.form.get("user", "").strip()
    pwd = request.form.get("pwd", "")
    
    if not user or not pwd:
        return redirect("/login?err=กรุณากรอกชื่อผู้ใช้และรหัสผ่าน")
    
    if user in USER_DB and USER_DB[user]["password"] == pwd:
        session["username"] = user
        session["cust_id"] = USER_DB[user]["customer_id"]
        return redirect("/dashboard")
    else:
        return redirect("/login?err=ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

# ==================== หน้าแดชบอร์ด ====================
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/login")
    
    username = session.get("username")
    user_info = USER_DB.get(username, {})
    
    return render_template_string("""
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — SAFE-ELEC</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans Thai", sans-serif; }
    body { background: #0F172A; color: #F1F5F9; min-height: 100vh; }
    header { background: #1E293B; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
    .logo { font-size: 20px; font-weight: 600; color: #22D3EE; }
    .user-info { display: flex; gap: 16px; align-items: center; }
    .user-name { color: #CBD5E1; }
    .btn { padding: 8px 16px; border-radius: 8px; text-decoration: none; font-size: 14px; border: none; cursor: pointer; }
    .btn-logout { background: #EF4444; color: white; }
    .btn-logout:hover { background: #DC2626; }
    .container { max-width: 1200px; margin: 32px auto; padding: 0 24px; }
    h1 { font-size: 24px; margin-bottom: 24px; color: #F8FAFC; }
    .card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 32px; }
    .card { background: #1E293B; border-radius: 12px; padding: 24px; border: 1px solid #334155; }
    .card h3 { font-size: 15px; color: #94A3B8; margin-bottom: 12px; }
    .card .value { font-size: 36px; font-weight: 700; color: #F1F5F9; }
    .btn-excel { display: inline-block; background: #16A34A; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 600; transition: background .2s; }
    .btn-excel:hover { background: #15803D; }
</style>
</head>
<body>
    <header>
        <div class="logo">⚡ SAFE-ELEC</div>
        <div class="user-info">
            <span class="user-name">👤 {{ user_info.name }}</span>
            <a href="/logout" class="btn btn-logout">ออกจากระบบ</a>
        </div>
    </header>
    <div class="container">
        <h1>📊 ภาพรวมระบบ</h1>
        <div class="card-grid">
            <div class="card">
                <h3>อุปกรณ์ทั้งหมด</h3>
                <div class="value">{{ devices|length }}</div>
            </div>
            <div class="card">
                <h3>✅ ออนไลน์</h3>
                <div class="value">{{ online_count }}</div>
            </div>
            <div class="card">
                <h3>⚠️ มีแจ้งเตือน</h3>
                <div class="value">{{ alert_count }}</div>
            </div>
        </div>
        <a href="/api/report-excel" class="btn-excel">📥 ดาวน์โหลดรายงาน Excel</a>
    </div>
</body>
</html>
    """,
    user_info=user_info,
    devices=devices,
    online_count=sum(1 for d in devices if d["is_online"]),
    alert_count=sum(1 for d in devices if d["alert_level"] != "normal")
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def index():
    return redirect("/dashboard" if "username" in session else "/login")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
