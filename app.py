#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超星抢座签到一体化 - 云端完整版
两个守护线程：自动抢座 + 自动签到
"""
import os, sys, json, time, threading, subprocess, logging, re
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify, render_template_string

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log_lines = []
def add_log(msg, tag=""):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {tag} {msg}".strip()
    log_lines.append(line)
    if len(log_lines) > 500: log_lines.pop(0)
    logging.info(msg)

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
LOG_FILE = os.path.join(BASE_DIR, "reserve_log.json")

DEFAULT_CONFIG = {
    "global": {
        "auto_reserve_enabled": True,
        "auto_reserve_time": "21:50",
        "max_attempt": 20,
        "auto_checkin_enabled": True,
        "auto_query_times": "07:30",
    },
    "accounts": []
}

ROOMS = {
    "二楼考研自习室": "6487",
    "四楼借阅室": "8343",
    "三楼借阅室": "8365",
    "一楼借阅室": "8366",
    "二楼大楼梯旁": "5761",
    "二楼边廊圆桌": "5763",
    "三楼公共区圆桌": "8244",
    "三楼前台折叠椅": "9060",
}

WEEKS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE,'r',encoding='utf-8') as f: return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE,'w',encoding='utf-8') as f: json.dump(cfg,f,ensure_ascii=False,indent=2)

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE,'r',encoding='utf-8') as f: return json.load(f)
    return []

def save_log(log):
    with open(LOG_FILE,'w',encoding='utf-8') as f: json.dump(log,f,ensure_ascii=False,indent=2)

# ========== 前端 ==========
INDEX_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>超星抢座控制台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,"PingFang SC",sans-serif;background:#f5f6fa;padding:12px;color:#333;padding-bottom:40px}
h1{font-size:20px;text-align:center;margin-bottom:8px;font-weight:600}
.card{background:#fff;border-radius:12px;padding:16px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.card h2{font-size:15px;margin-bottom:12px;color:#2c3e50;display:flex;justify-content:space-between;align-items:center}
.btn{padding:10px 16px;border:none;border-radius:8px;font-size:14px;cursor:pointer}
.btn-blue{background:#3498db;color:#fff}.btn-green{background:#2ecc71;color:#fff}
.btn-red{background:#e74c3c;color:#fff}.btn-gray{background:#95a5a6;color:#fff}
.btn-orange{background:#f39c12;color:#fff}
.btn-sm{padding:6px 12px;font-size:12px}
.btn-block{display:block;width:100%}
.btn-row{display:flex;gap:6px;margin-top:8px}
.btn-row .btn{flex:1}
input,select{width:100%;padding:10px;border:1px solid #ddd;border-radius:8px;font-size:14px;margin-top:4px}
label{font-size:13px;color:#666;display:block;margin-top:8px}
.log-box{background:#1e1e1e;color:#0f0;padding:12px;border-radius:8px;font-size:11px;max-height:280px;overflow-y:auto;font-family:"Courier New",monospace;line-height:1.5}
.log-item{padding:10px 0;border-bottom:1px solid #ecf0f1;font-size:13px}
.log-time{color:#888;font-size:11px}
.ok{color:#27ae60;font-weight:bold}.fail{color:#e74c3c;font-weight:bold}
.status{text-align:center;font-size:13px;padding:8px;border-radius:8px;margin-bottom:12px}
.status.on{background:#d5f5e3;color:#27ae60}.status.off{background:#fadbd8;color:#e74c3c}
.account-card{background:#f8f9fa;border-radius:10px;padding:12px;margin-bottom:10px;border-left:4px solid #3498db}
.account-card .head{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.account-card .name{font-weight:bold;font-size:15px}
.account-card .info{font-size:12px;color:#666;line-height:1.8}
.account-card .room{color:#2c3e50;font-weight:500}
.session-row{display:flex;gap:6px;align-items:center;margin-top:4px}
.session-row input{flex:1}
.toggle{display:flex;align-items:center;gap:6px;margin-top:8px;font-size:14px}
.modal-bg{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.5);z-index:99}
.modal{background:#fff;margin:20px;border-radius:12px;padding:16px;max-height:85vh;overflow-y:auto}
.modal h3{margin-bottom:12px;font-size:16px}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;margin-left:6px}
.badge-ok{background:#d5f5e3;color:#27ae60}.badge-wait{background:#fef9e7;color:#f39c12}
</style>
</head>
<body>
<h1>🎓 超星抢座控制台</h1>
<div id="status" class="status on">✅ 服务运行中</div>

<div class="card">
<h2>⚡ 快速操作</h2>
<div class="btn-row">
<button class="btn btn-blue" onclick="reserveNow()">🚀 立即抢座</button>
<button class="btn btn-green" onclick="checkinNow()">✅ 立即签到</button>
</div>
<div class="btn-row">
<button class="btn btn-gray" onclick="queryNow()">🔍 查询预约</button>
<button class="btn btn-red" onclick="restartNow()">🔄 重启服务</button>
</div>
</div>

<div class="card">
<h2>👥 账号管理 <button class="btn btn-orange btn-sm" onclick="showAdd()">+ 添加账号</button></h2>
<div id="accountList">加载中...</div>
</div>

<div class="card">
<h2>⚙️ 全局设置</h2>
<div class="toggle"><input type="checkbox" id="g_autoReserve" checked> 自动抢座</div>
<label>抢座触发时间（HH:MM）</label><input type="time" id="g_reserveTime" value="21:50">
<label>抢座尝试次数</label><input type="number" id="g_maxAttempt" value="20" min="1" max="100">
<div class="toggle"><input type="checkbox" id="g_autoCheckin" checked> 自动签到</div>
<label>每日查询预约时间</label><input type="time" id="g_queryTime" value="07:30">
<button class="btn btn-blue btn-block" style="margin-top:12px" onclick="saveGlobal()">保存全局设置</button>
</div>

<div class="card">
<h2>📋 预约日志（已抢到待签到）</h2>
<div id="reserveLog">暂无记录</div>
<button class="btn btn-red btn-sm" style="margin-top:10px" onclick="clearLog()">🗑️ 清除预约日志</button>
</div>

<div class="card">
<h2>🖥️ 运行日志</h2>
<div class="log-box" id="logBox">加载中...</div>
</div>

<div class="modal-bg" id="accModal">
<div class="modal">
<h3 id="modalTitle">添加账号</h3>
<input type="hidden" id="f_idx">
<label>账号昵称（如：账号1）</label><input type="text" id="f_name" placeholder="账号1">
<label>手机号</label><input type="text" id="f_username" placeholder="手机号">
<label>密码</label><input type="text" id="f_password" placeholder="超星密码">
<label>教室</label>
<select id="f_room">
{% for n,r in rooms.items() %}<option value="{{r}}">{{n}}</option>{% endfor %}
</select>
<label>座位号（多个用英文逗号分隔，如 082,076）</label>
<input type="text" id="f_seat" placeholder="082">
<div class="toggle"><input type="checkbox" id="f_autoReserve" checked> 自动抢座</div>
<div class="toggle"><input type="checkbox" id="f_autoCheckin" checked> 自动签到</div>
<label>预约时段 <button class="btn btn-sm btn-orange" onclick="addSession()">+ 加一段</button> <button class="btn btn-sm btn-green" onclick="setFullDay()">⚡ 一键8:30-22:00分两段</button></label>
<div id="sessionsBox"></div>
<div class="btn-row" style="margin-top:12px">
<button class="btn btn-blue" onclick="saveAccount()">保存账号</button>
<button class="btn btn-gray" onclick="closeModal()">取消</button>
</div>
</div>
</div>

<script>
let roomNames = {};
{% for n,r in rooms.items() %}roomNames["{{r}}"]="{{n}}";{% endfor %}
let sessions = [];

function loadAll(){
  fetch('/api/config').then(r=>r.json()).then(d=>{
    document.getElementById('g_autoReserve').checked = d.global.auto_reserve_enabled;
    document.getElementById('g_reserveTime').value = d.global.auto_reserve_time;
    document.getElementById('g_maxAttempt').value = d.global.max_attempt;
    document.getElementById('g_autoCheckin').checked = d.global.auto_checkin_enabled;
    document.getElementById('g_queryTime').value = d.global.auto_query_times;
    renderAccounts(d.accounts);
  });
}
function renderAccounts(accs){
  const box = document.getElementById('accountList');
  if(!accs.length){box.innerHTML='<p style="color:#999;text-align:center">暂无账号</p>';return}
  box.innerHTML = accs.map((a,i)=>{
    const rooms = roomNames[a.roomid]||a.roomid;
    const seats = (a.seatid||[]).join(', ');
    const s = (a.sessions||[]).map(x=>x.start+'~'+x.end).join(' / ') || '未设置';
    const ar = a.auto_reserve!==false?'✅自动抢':'⏸️手动';
    const ac = a.auto_checkin!==false?'✅自动签':'⏸️手动';
    return `<div class="account-card">
      <div class="head">
        <span class="name">${a.name||'账号'+(i+1)}</span>
        <span style="font-size:12px;color:#888">${a.username}</span>
      </div>
      <div class="info">
        <span class="room">🏠 ${rooms}</span><br>
        🪑 座位:${seats} | 🕐 ${s}<br>
        ${ar} | ${ac}
      </div>
      <div class="btn-row" style="margin-top:8px">
        <button class="btn btn-blue btn-sm" onclick='reserveOne(${i})'>立即抢座</button>
        <button class="btn btn-green btn-sm" onclick='checkinOne(${i})'>立即签到</button>
        <button class="btn btn-gray btn-sm" onclick='queryOne(${i})'>手动查询</button>
      </div>
      <div class="btn-row">
        <button class="btn btn-gray btn-sm" onclick='editAcc(${i})'>编辑</button>
        <button class="btn btn-red btn-sm" onclick='delAcc(${i})'>删除</button>
      </div>
    </div>`;
  }).join('');
}
function loadLogs(){
  fetch('/api/logs').then(r=>r.json()).then(d=>{
    const lb = document.getElementById('logBox');
    lb.innerHTML = d.logs.map(l=>{
      let cls = 'color:#0f0';
      if(l.includes('ERROR')||l.includes('❌')) cls='color:#f44';
      else if(l.includes('SUCCESS')||l.includes('✅')) cls='color:#0f0;font-weight:bold';
      return `<div style="${cls}">${l}</div>`;
    }).join('');
    lb.scrollTop = lb.scrollHeight;
  });
}
function loadReserveLog(){
  fetch('/api/reserve_log').then(r=>r.json()).then(d=>{
    const box = document.getElementById('reserveLog');
    if(!d.log.length){box.innerHTML='<p style="color:#999;text-align:center">暂无</p>';return}
    box.innerHTML = d.log.slice().reverse().map(e=>{
      const st = e.checked_in?'<span class="badge badge-ok">✅已签到 '+e.checkin_time+'</span>':'<span class="badge badge-wait">⏳待签到</span>';
      return `<div class="log-item">
        <div style="font-weight:500">${e.date} ${e.start}~${e.end}</div>
        <div style="font-size:12px;color:#666;margin-top:4px">
          🏠 ${roomNames[e.roomid]||e.roomid} | 🪑 ${e.seatid}号 | ${e.username}<br>
          ${st}
        </div>
      </div>`;
    }).join('');
  });
}

function reserveNow(){if(!confirm('确定所有账号都抢座？'))return;fetch('/api/reserve_now',{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.msg);loadLogs()})}
function checkinNow(){fetch('/api/checkin_now',{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.msg);loadLogs()})}
function reserveOne(idx){if(!confirm('确定这个账号抢座？'))return;fetch('/api/reserve_one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx})}).then(r=>r.json()).then(d=>{alert(d.msg);loadLogs()})}
function checkinOne(idx){fetch('/api/checkin_one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx})}).then(r=>r.json()).then(d=>{alert(d.msg);loadLogs()})}
function queryOne(idx){fetch('/api/query_one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx})}).then(r=>r.json()).then(d=>{alert(d.msg);loadLogs()})}
function queryNow(){fetch('/api/query_now',{method:'POST'}).then(r=>r.json()).then(d=>{alert(d.msg);loadLogs()})}
function restartNow(){if(!confirm('重启服务？'))return;fetch('/api/restart',{method:'POST'})}
function clearLog(){if(!confirm('清空预约日志？'))return;fetch('/api/clear_log',{method:'POST'}).then(()=>loadReserveLog())}

function addSession(start='08:30',end='15:30'){
  sessions.push({start,end}); renderSessions();
}
function renderSessions(){
  const box = document.getElementById('sessionsBox');
  box.innerHTML = sessions.map((s,i)=>`
    <div class="session-row">
      <input type="time" value="${s.start}" onchange="sessions[${i}].start=this.value">
      <span>至</span>
      <input type="time" value="${s.end}" onchange="sessions[${i}].end=this.value">
      <button class="btn btn-red btn-sm" onclick="sessions.splice(${i},1);renderSessions()">×</button>
    </div>
  `).join('');
}
function setFullDay(){sessions=[{start:'08:30',end:'15:30'},{start:'15:30',end:'22:00'}];renderSessions()}

function showAdd(){
  document.getElementById('modalTitle').innerText='添加账号';
  document.getElementById('f_idx').value='';
  document.getElementById('f_name').value='';
  document.getElementById('f_username').value='';
  document.getElementById('f_password').value='';
  document.getElementById('f_room').value='6487';
  document.getElementById('f_seat').value='082';
  document.getElementById('f_autoReserve').checked=true;
  document.getElementById('f_autoCheckin').checked=true;
  sessions=[{start:'08:30',end:'15:30'},{start:'15:30',end:'22:00'}];
  renderSessions();
  document.getElementById('accModal').style.display='block';
}
function closeModal(){document.getElementById('accModal').style.display='none'}

function saveAccount(){
  const data={
    name:document.getElementById('f_name').value,
    username:document.getElementById('f_username').value,
    password:document.getElementById('f_password').value,
    roomid:document.getElementById('f_room').value,
    seatid:document.getElementById('f_seat').value.split(',').map(s=>s.trim()),
    auto_reserve:document.getElementById('f_autoReserve').checked,
    auto_checkin:document.getElementById('f_autoCheckin').checked,
    sessions:sessions
  };
  const idx=document.getElementById('f_idx').value;
  fetch('/api/save_account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:idx,data:data})}).then(r=>r.json()).then(d=>{
    alert(d.msg);closeModal();loadAll();
  });
}
function editAcc(i){
  fetch('/api/config').then(r=>r.json()).then(d=>{
    const a=d.accounts[i];
    document.getElementById('modalTitle').innerText='编辑账号';
    document.getElementById('f_idx').value=i;
    document.getElementById('f_name').value=a.name||'';
    document.getElementById('f_username').value=a.username;
    document.getElementById('f_password').value=a.password;
    document.getElementById('f_room').value=a.roomid;
    document.getElementById('f_seat').value=(a.seatid||[]).join(',');
    document.getElementById('f_autoReserve').checked=a.auto_reserve!==false;
    document.getElementById('f_autoCheckin').checked=a.auto_checkin!==false;
    sessions=a.sessions||[];
    renderSessions();
    document.getElementById('accModal').style.display='block';
  });
}
function delAcc(i){if(!confirm('删除这个账号？'))return;fetch('/api/del_account',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({idx:i})}).then(()=>loadAll())}

function saveGlobal(){
  const data={
    auto_reserve_enabled:document.getElementById('g_autoReserve').checked,
    auto_reserve_time:document.getElementById('g_reserveTime').value,
    max_attempt:parseInt(document.getElementById('g_maxAttempt').value),
    auto_checkin_enabled:document.getElementById('g_autoCheckin').checked,
    auto_query_times:document.getElementById('g_queryTime').value
  };
  fetch('/api/save_global',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}).then(r=>r.json()).then(d=>alert(d.msg));
}

loadAll();
loadLogs();
loadReserveLog();
setInterval(loadLogs, 2000);
setInterval(loadReserveLog, 3000);
</script>
</body>
</html>'''

@app.route('/')
def index(): return render_template_string(INDEX_HTML, rooms=ROOMS)

@app.route('/api/status')
def status():
    cfg = load_config()
    return jsonify({"auto_reserve": cfg['global']['auto_reserve_enabled'],
                    "auto_checkin": cfg['global']['auto_checkin_enabled']})

@app.route('/api/config')
def get_config(): return jsonify(load_config())

@app.route('/api/save_config', methods=['POST'])
def save_config_api():
    save_config(request.json); add_log("配置已更新","CONFIG"); return jsonify({"success":True})

@app.route('/api/logs')
def get_logs(): return jsonify({"logs": log_lines[-150:]})

@app.route('/api/reserve_log')
def get_reserve_log(): return jsonify({"log": load_log()})

@app.route('/api/reserve_now', methods=['POST'])
def reserve_now():
    threading.Thread(target=do_reserve_all, args=(None,), daemon=True).start()
    return jsonify({"success":True,"msg":"抢座已触发，看日志"})

@app.route('/api/reserve_one', methods=['POST'])
def reserve_one():
    idx = request.json.get('idx', 0)
    threading.Thread(target=do_reserve_all, args=(idx,), daemon=True).start()
    return jsonify({"success":True,"msg":"抢座已触发，看日志"})

@app.route('/api/checkin_now', methods=['POST'])
def checkin_now():
    threading.Thread(target=do_checkin_all, daemon=True).start()
    return jsonify({"success":True,"msg":"签到已触发，看日志"})

@app.route('/api/checkin_one', methods=['POST'])
def checkin_one():
    idx = request.json.get('idx', 0)
    threading.Thread(target=do_checkin_one, args=(idx,), daemon=True).start()
    return jsonify({"success":True,"msg":"签到已触发，看日志"})

@app.route('/api/query_now', methods=['POST'])
def query_now():
    threading.Thread(target=do_query_all, daemon=True).start()
    return jsonify({"success":True,"msg":"查询已触发，看日志"})

@app.route('/api/query_one', methods=['POST'])
def query_one():
    idx = request.json.get('idx', 0)
    threading.Thread(target=do_query_one, args=(idx,), daemon=True).start()
    return jsonify({"success":True,"msg":"查询已触发，看日志"})

@app.route('/api/clear_log', methods=['POST'])
def clear_log():
    save_log([])
    return jsonify({"success":True,"msg":"预约日志已清空"})

@app.route('/api/restart', methods=['POST'])
def restart():
    def _r():
        time.sleep(1)
        subprocess.Popen([sys.executable, os.path.join(BASE_DIR,'app.py')],
                        cwd=BASE_DIR, stdout=open(os.path.join(BASE_DIR,'app.log'),'a'),
                        stderr=subprocess.STDOUT)
        os._exit(0)
    threading.Thread(target=_r, daemon=True).start()
    return jsonify({"success":True,"msg":"重启中..."})

# ========== 业务逻辑 ==========

def build_users_from_config(only_idx=None):
    """把admin_config转换成main.py需要的users格式"""
    cfg = load_config()
    users = []
    for i, acc in enumerate(cfg['accounts']):
        if only_idx is not None and i != only_idx:
            continue
        for sess in acc.get('sessions', []):
            users.append({
                "username": acc['username'],
                "password": acc['password'],
                "time": [sess['start'], sess['end']],
                "roomid": str(acc['roomid']),
                "seatid": acc.get('seatid', ['082']),
                "daysofweek": WEEKS,
            })
    return users

def do_reserve_all(only_idx=None):
    """执行抢座，直接调用main.py的main函数，抢到后写入日志"""
    cfg = load_config()
    users = build_users_from_config(only_idx)
    if not users:
        add_log("⚠️ 没有配置账号，跳过","RESERVE")
        return
    who = "单个账号" if only_idx is not None else "所有账号"
    add_log(f"🚀 开始抢座流程（{who}），共{len(users)}个时段","RESERVE")
    try:
        sys.path.insert(0, BASE_DIR)
        from main import main as do_reserve
        do_reserve(users, action=False)
        # 抢完后把记录写入待签到日志（去重）
        today = date.today().isoformat()
        rlog = load_log()
        for u in users:
            for seat in u['seatid']:
                exists = any(e.get('date')==today and e.get('username')==u['username'] 
                            and e.get('seatid')==seat and e.get('start')==u['time'][0])
                if not exists:
                    rlog.append({"date":today,"start":u['time'][0],"end":u['time'][1],
                                "username":u['username'],"seatid":seat,"roomid":u['roomid'],
                                "checked_in":False,"source":"auto"})
        save_log(rlog)
        add_log("✅ 抢座流程结束，已更新待签到日志","RESERVE")
    except Exception as e:
        add_log(f"❌ 抢座异常: {e}","ERROR")

def do_checkin_detailed(username, password, roomid, seatid):
    """带详细日志的签到函数"""
    sys.path.insert(0, BASE_DIR)
    from utils.reserve import reserve
    
    add_log(f"  🔐 正在登录超星...","CHECKIN")
    s = reserve(sleep_time=0.2, max_attempt=3, enable_slider=True)
    s.get_login_status()
    ok, msg = s.login(username, password)
    if not ok:
        add_log(f"  ❌ 登录失败: {msg}","CHECKIN")
        return False, msg
    add_log(f"  ✅ 登录成功","CHECKIN")
    
    add_log(f"  🪑 正在获取座位信息（{seatid}号）...","CHECKIN")
    add_log(f"  📍 正在上报位置...","CHECKIN")
    location_url = 'https://office.chaoxing.com/data/apps/seat/reportlocation'
    loc_data = {'lng': '119.23559140410926', 'lat': '34.656767879153406'}
    r = s.requests.post(location_url, data=loc_data, timeout=10)
    add_log(f"  📍 位置上报: {r.text[:100]}","CHECKIN")
    
    add_log(f"  📝 正在提交签到...","CHECKIN")
    checkin_url = 'https://office.chaoxing.com/data/apps/seat/checkin'
    checkin_data = {
        'roomId': str(roomid),
        'seatNum': seatid.zfill(3),
        'day': date.today().isoformat()
    }
    r = s.requests.post(checkin_url, data=checkin_data, timeout=10)
    result = r.json()
    add_log(f"  📝 签到接口返回: {r.status_code} {r.text[:150]}","CHECKIN")
    
    if result.get('success'):
        add_log(f"  ✅ 签到完成: {username} {seatid}号","SUCCESS")
        return True, "签到成功"
    else:
        msg = result.get('msg', '未知错误')
        add_log(f"  ❌ 签到失败: {msg}","ERROR")
        return False, msg

def do_checkin_one(idx):
    """对指定账号执行签到"""
    cfg = load_config()
    if idx >= len(cfg['accounts']): return
    acc = cfg['accounts'][idx]
    username = acc['username']
    seats = acc.get('seatid', ['082'])
    if isinstance(seats, str): seats = [seats]
    
    add_log(f"✅ 开始签到流程: {username}","CHECKIN")
    for seat in seats:
        try:
            ok, msg = do_checkin_detailed(username, acc['password'], acc['roomid'], seat)
            if ok:
                today = date.today().isoformat()
                rlog = load_log()
                for e in rlog:
                    if e.get('date')==today and e.get('username')==username and e.get('seatid')==seat:
                        e['checked_in'] = True
                        e['checkin_time'] = datetime.now().strftime('%H:%M:%S')
                save_log(rlog)
        except Exception as e:
            add_log(f"  ❌ 签到异常: {e}","ERROR")

def do_checkin_all():
    """扫描待签到日志，到时间自动签到"""
    cfg = load_config()
    if not cfg['global'].get('auto_checkin_enabled', True):
        return
    sys.path.insert(0, BASE_DIR)
    from main import do_checkin_one as do_checkin
    today = date.today().isoformat()
    rlog = load_log()
    now = datetime.now()
    changed = False
    for entry in rlog:
        if entry.get('date') != today: continue
        if entry.get('checked_in'): continue
        start = entry.get('start','08:30')
        try:
            sh, sm = map(int, start.split(':'))
        except: continue
        target = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
        early = target - timedelta(minutes=10)
        late = target + timedelta(minutes=10)
        if not (early <= now <= late): continue
        username = entry['username']
        acc = next((a for a in cfg['accounts'] if a['username']==username), None)
        if not acc: continue
        if not acc.get('auto_checkin', True): continue
        add_log(f"⏰ 到签到窗口: {username} {entry['seatid']}号","CHECKIN")
        try:
            ok, msg = do_checkin_detailed(username, acc['password'], entry['roomid'], entry['seatid'])
            if ok:
                entry['checked_in'] = True
                entry['checkin_time'] = now.strftime('%H:%M:%S')
                changed = True
        except Exception as e:
            add_log(f"  ❌ 签到异常: {e}","ERROR")
    if changed:
        save_log(rlog)

def do_query_all():
    """查询今天预约并补录"""
    cfg = load_config()
    sys.path.insert(0, BASE_DIR)
    from utils.reserve import reserve
    today = date.today().isoformat()
    rlog = load_log()
    for acc in cfg['accounts']:
        username = acc['username']
        try:
            s = reserve(sleep_time=0.2, max_attempt=3)
            s.get_login_status()
            ok, msg = s.login(username, acc['password'])
            if not ok:
                add_log(f"  {username} 登录失败: {msg}","QUERY"); continue
            add_log(f"  {username} 登录成功","QUERY")
            try:
                r = s.requests.post('https://office.chaoxing.com/data/apps/seat/getusedtimes',
                                   data={'day':today,'type':'1'}, timeout=10)
                data = r.json()
                add_log(f"  查询返回: {str(data)[:200]}","QUERY")
            except Exception as e:
                add_log(f"  查询失败: {e}","QUERY")
        except Exception as e:
            add_log(f"  异常: {e}","ERROR")
    save_log(rlog)

def do_query_one(idx):
    """查询单个账号今天预约并补录"""
    cfg = load_config()
    if idx >= len(cfg['accounts']): return
    acc = cfg['accounts'][idx]
    username = acc['username']
    sys.path.insert(0, BASE_DIR)
    from utils.reserve import reserve
    today = date.today().isoformat()
    rlog = load_log()
    try:
        add_log(f"🔍 开始查询 {username}...","QUERY")
        s = reserve(sleep_time=0.2, max_attempt=3)
        s.get_login_status()
        ok, msg = s.login(username, acc['password'])
        if not ok:
            add_log(f"  ❌ {username} 登录失败: {msg}","QUERY"); return
        add_log(f"  ✅ {username} 登录成功","QUERY")
        try:
            r = s.requests.post('https://office.chaoxing.com/data/apps/seat/getusedtimes',
                               data={'day':today,'type':'1'}, timeout=10)
            data = r.json()
            add_log(f"  查询返回: {str(data)[:300]}","QUERY")
        except Exception as e:
            add_log(f"  查询失败: {e}","QUERY")
    except Exception as e:
        add_log(f"  ❌ 异常: {e}","ERROR")
    save_log(rlog)

# ========== 守护线程 ==========

def reserve_worker():
    """自动抢座守护线程，21:50触发，main函数内部会等到22:00准点"""
    today_reserved = ""
    while True:
        try:
            cfg = load_config()
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            
            if cfg['global']['auto_reserve_enabled']:
                target_time = cfg['global']['auto_reserve_time']
                th, tm = map(int, target_time.split(':'))
                target = now.replace(hour=th, minute=tm, second=0, microsecond=0)
                
                # 在触发时间±1分钟内，且今天还没跑过
                if abs((now - target).total_seconds()) < 60 and today_reserved != today:
                    today_reserved = today
                    add_log(f"⏰ 到达自动抢座时间 {target_time}，启动抢座线程","WORKER")
                    threading.Thread(target=do_reserve_all, args=(False,), daemon=True).start()
        except Exception as e:
            add_log(f"抢座线程异常: {e}","ERROR")
        time.sleep(5)

def checkin_worker():
    """自动签到守护线程，每秒扫描"""
    while True:
        try:
            cfg = load_config()
            if cfg['global']['auto_checkin_enabled']:
                now = datetime.now()
                # 每天07:30查询一次
                qt = cfg['global'].get('auto_query_times','07:30')
                qh, qm = map(int, qt.split(':'))
                today = date.today().isoformat()
                rlog = load_log()
                already_queried = any(e.get('date')==today and e.get('source')=='query' for e in rlog)
                
                if now.hour==qh and now.minute==qm and not already_queried:
                    add_log("📋 每日自动查询预约","WORKER")
                    do_query_all()
                
                # 扫描签到窗口
                do_checkin_all()
        except Exception as e:
            add_log(f"签到线程异常: {e}","ERROR")
        time.sleep(1)

if __name__ == '__main__':
    # 首次运行从旧config导入
    if not os.path.exists(CONFIG_FILE):
        old = os.path.join(BASE_DIR, "config.json")
        if os.path.exists(old):
            with open(old,'r',encoding='utf-8') as f: oldcfg = json.load(f)
            accs = []
            seen = {}
            for item in oldcfg.get('reserve', []):
                u = item['username']
                if u not in seen:
                    seen[u] = {'name':u[-4:],'username':u,'password':item['password'],
                              'roomid':str(item['roomid']),'seatid':item['seatid'],
                              'auto_reserve':True,'auto_checkin':True,'sessions':[]}
                seen[u]['sessions'].append({'start':item['time'][0],'end':item['time'][1]})
            accs = list(seen.values())
            save_config({"global":DEFAULT_CONFIG["global"],"accounts":accs})
            add_log(f"已从旧配置导入{len(accs)}个账号","INIT")
    
    # 启动守护线程
    threading.Thread(target=reserve_worker, daemon=True).start()
    threading.Thread(target=checkin_worker, daemon=True).start()
    add_log("🚀 云端控制台启动成功（自动抢座+自动签到已开启）","INIT")
    app.run(host='0.0.0.0', port=5002, debug=False)
