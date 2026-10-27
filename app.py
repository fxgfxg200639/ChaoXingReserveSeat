#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超星抢座签到一体化 - 云端版
部署在腾讯云服务器，手机浏览器直接访问控制面板
"""
import os, sys, json, time, threading, subprocess, logging
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify, render_template_string

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log_lines = []
def add_log(msg, tag=""):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {tag} {msg}".strip()
    log_lines.append(line)
    if len(log_lines) > 200:
        log_lines.pop(0)
    logging.info(msg)

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "admin_config.json")
LOG_FILE = os.path.join(BASE_DIR, "reserve_log.json")

# 默认配置
DEFAULT_CONFIG = {
    "global": {
        "auto_reserve_time": "21:50",
        "auto_checkin_enabled": True,
        "fire_minutes": 0,
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

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def load_reserve_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_reserve_log(log):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

# ========== 前端页面 ==========
INDEX_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>超星抢座控制台</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, sans-serif; background:#f5f6fa; padding:12px; color:#333; }
h1 { font-size:18px; text-align:center; margin-bottom:16px; }
.card { background:#fff; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }
.card h2 { font-size:15px; margin-bottom:12px; color:#2c3e50; }
.btn { display:block; width:100%; padding:12px; border:none; border-radius:8px; font-size:15px; cursor:pointer; margin-top:8px; }
.btn-blue { background:#3498db; color:#fff; }
.btn-green { background:#2ecc71; color:#fff; }
.btn-red { background:#e74c3c; color:#fff; }
.btn-gray { background:#95a5a6; color:#fff; }
input, select { width:100%; padding:10px; border:1px solid #ddd; border-radius:8px; font-size:14px; margin-top:4px; }
label { font-size:13px; color:#666; display:block; margin-top:8px; }
.log-box { background:#1e1e1e; color:#0f0; padding:12px; border-radius:8px; font-size:11px; max-height:200px; overflow-y:auto; font-family:monospace; }
.log-item { padding:6px; border-bottom:1px solid #ecf0f1; font-size:13px; }
.ok { color:#27ae60; } .fail { color:#e74c3c; }
.status { text-align:center; font-size:13px; padding:8px; border-radius:8px; margin-bottom:12px; }
.status.on { background:#d5f5e3; color:#27ae60; }
.status.off { background:#fadbd8; color:#e74c3c; }
</style>
</head>
<body>
<h1>🎓 超星抢座控制台</h1>

<div id="status" class="status on">服务运行中</div>

<div class="card">
<h2>⚡ 快速操作</h2>
<button class="btn btn-green" onclick="reserveNow()">🚀 立即抢座</button>
<button class="btn btn-blue" onclick="checkinNow()">✅ 立即签到</button>
<button class="btn btn-gray" onclick="queryNow()">🔍 查询当前座位</button>
</div>

<div class="card">
<h2>👥 账号列表</h2>
<div id="accountList"></div>
</div>

<div class="card">
<h2>📋 预约日志</h2>
<div id="reserveLog"></div>
</div>

<div class="card">
<h2>📝 运行日志</h2>
<div class="log-box" id="logBox">加载中...</div>
</div>

<script>
function loadStatus() {
    fetch('/api/status').then(r=>r.json()).then(d=>{
        document.getElementById('status').textContent = d.auto_reserve ? '✅ 自动抢座运行中' : '⏸️ 自动抢座已停止';
        document.getElementById('status').className = d.auto_reserve ? 'status on' : 'status off';
    });
}
function loadAccounts() {
    fetch('/api/config').then(r=>r.json()).then(d=>{
        const box = document.getElementById('accountList');
        box.innerHTML = d.accounts.map((a,i)=>{
            const seats = (a.seatid||[]).join(', ');
            return `<div class="log-item">
                <b>${a.username}</b><br>
                <small>${a.roomid}室 | 座位: ${seats}</small>
            </div>`;
        }).join('') || '<p style="color:#999">暂无账号</p>';
    });
}
function loadLog() {
    fetch('/api/reserve_log').then(r=>r.json()).then(d=>{
        const box = document.getElementById('reserveLog');
        if(!d.reserve_log.length) { box.innerHTML='<p style="color:#999;text-align:center">暂无预约记录</p>'; return; }
        box.innerHTML = d.reserve_log.slice().reverse().map(e=>{
            const st = e.checked_in ? '<span class="ok">已签到</span>' : '<span class="fail">待签到</span>';
            return `<div class="log-item">
                ${e.date} ${e.start}~${e.end}<br>
                <small>${e.username} | ${e.seatid}号 | ${st}</small>
            </div>`;
        }).join('');
    });
}
function loadLogs() {
    fetch('/api/logs').then(r=>r.json()).then(d=>{
        document.getElementById('logBox').innerText = d.logs.join('\\n');
    });
}

function reserveNow() {
    if(!confirm('确定立即执行抢座？')) return;
    fetch('/api/reserve_now', {method:'POST'}).then(r=>r.json()).then(res=>{
        alert(res.msg || '已触发');
        loadLogs();
    });
}
function checkinNow() {
    fetch('/api/checkin_now', {method:'POST'}).then(r=>r.json()).then(res=>{
        alert(res.msg || '已触发');
        loadLogs();
    });
}
function queryNow() {
    fetch('/api/query_now', {method:'POST'}).then(r=>r.json()).then(res=>{
        alert(res.msg || '查询完成');
        loadLogs();
    });
}

loadStatus(); loadAccounts(); loadLog(); loadLogs();
setInterval(loadLogs, 3000);
setInterval(loadLog, 5000);
</script>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(INDEX_HTML, rooms=ROOMS)

@app.route('/api/status')
def status():
    return jsonify({"auto_reserve": True, "auto_checkin": True})

@app.route('/api/config', methods=['GET'])
def get_config():
    cfg = load_config()
    return jsonify(cfg)

@app.route('/api/logs')
def get_logs():
    return jsonify({"logs": log_lines[-80:]})

@app.route('/api/reserve_log')
def get_reserve_log():
    return jsonify({"reserve_log": load_reserve_log()})

@app.route('/api/reserve_now', methods=['POST'])
def reserve_now():
    """手动触发抢座"""
    try:
        cfg = load_config()
        add_log("🚀 手动触发抢座", "MANUAL")
        # 在后台线程跑抢座
        def run():
            try:
                sys.path.insert(0, BASE_DIR)
                from main import main as do_reserve
                users = []
                for acc in cfg.get('accounts', []):
                    users.append({
                        "username": acc["username"],
                        "password": acc["password"],
                        "time": acc.get("time", ["08:30", "22:00"]),
                        "roomid": acc["roomid"],
                        "seatid": acc.get("seatid", []),
                        "daysofweek": ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
                    })
                do_reserve(users, action=False)
                add_log("✅ 抢座执行完成", "MANUAL")
            except Exception as e:
                add_log(f"❌ 抢座失败: {e}", "ERROR")
        threading.Thread(target=run, daemon=True).start()
        return jsonify({"success": True, "msg": "抢座已触发，请看日志"})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

@app.route('/api/checkin_now', methods=['POST'])
def checkin_now():
    """手动触发签到"""
    try:
        cfg = load_config()
        add_log("✅ 手动触发签到", "MANUAL")
        def run():
            try:
                sys.path.insert(0, BASE_DIR)
                from main import do_checkin_one
                for acc in cfg.get('accounts', []):
                    seats = acc.get('seatid', ['082'])
                    for seat in seats:
                        result = do_checkin_one(acc["username"], acc["password"], acc["roomid"], seat)
                        add_log(f"签到 {acc['username']} {seat}号: {result}", "CHECKIN")
            except Exception as e:
                add_log(f"❌ 签到失败: {e}", "ERROR")
        threading.Thread(target=run, daemon=True).start()
        return jsonify({"success": True, "msg": "签到已触发，请看日志"})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

@app.route('/api/query_now', methods=['POST'])
def query_now():
    """手动查询当前座位状态"""
    try:
        cfg = load_config()
        add_log("🔍 手动查询座位", "MANUAL")
        def run():
            try:
                sys.path.insert(0, BASE_DIR)
                from utils.reserve import reserve
                MOBILE_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15'
                for acc in cfg.get('accounts', []):
                    s = reserve(sleep_time=0.2, max_attempt=3)
                    s.get_login_status()
                    ok, msg = s.login(acc["username"], acc["password"])
                    if not ok:
                        add_log(f"  {acc['username']} 登录失败: {msg}", "QUERY")
                        continue
                    uid = s.requests.cookies.get('_uid', '')
                    add_log(f"  {acc['username']} 登录成功 uid={uid}", "QUERY")
                    for seat in acc.get('seatid', []):
                        # 查座位状态
                        try:
                            s.requests.headers['User-Agent'] = MOBILE_UA
                            r = s.requests.post(
                                'https://office.chaoxing.com/data/apps/seat/reserve/info',
                                data={'id': acc['roomid'], 'seatNum': seat},
                                timeout=10
                            )
                            data = r.json()
                            sr = data.get('data', {}).get('seatReserve', {})
                            if sr:
                                add_log(f"    {seat}号 被占用: uid={sr.get('uid')}", "QUERY")
                            else:
                                add_log(f"    {seat}号 空闲", "QUERY")
                        except Exception as e:
                            add_log(f"    {seat}号 查询失败: {e}", "QUERY")
            except Exception as e:
                add_log(f"❌ 查询失败: {e}", "ERROR")
        threading.Thread(target=run, daemon=True).start()
        return jsonify({"success": True, "msg": "查询已触发，请看日志"})
    except Exception as e:
        return jsonify({"success": False, "msg": str(e)}), 500

if __name__ == '__main__':
    # 如果没有配置文件，从仓库config.json导入
    if not os.path.exists(CONFIG_FILE):
        old_config = os.path.join(BASE_DIR, "config.json")
        if os.path.exists(old_config):
            with open(old_config, 'r', encoding='utf-8') as f:
                old = json.load(f)
            accounts = []
            for item in old.get('reserve', []):
                accounts.append({
                    "username": item["username"],
                    "password": item["password"],
                    "roomid": item["roomid"],
                    "seatid": item["seatid"],
                    "time": item["time"],
                    "auto_reserve": True,
                    "auto_checkin": True,
                })
            save_config({"global": DEFAULT_CONFIG["global"], "accounts": accounts})
            add_log("已从旧配置导入账号", "INIT")
    add_log("🚀 云端控制台启动成功", "INIT")
    app.run(host='0.0.0.0', port=5002, debug=False)
