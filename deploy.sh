#!/bin/bash
# 超星抢座云端版 - 一键部署脚本
# 在腾讯云Ubuntu服务器上执行
set -e

echo "========================================="
echo "  超星抢座云端版 - 一键部署"
echo "========================================="

# 1. 安装Python和依赖
echo "[1/6] 安装Python环境..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv git > /dev/null

# 2. 克隆仓库
echo "[2/6] 拉取代码..."
cd /home/ubuntu
if [ -d "ChaoXingReserveSeat" ]; then
    cd ChaoXingReserveSeat && git pull
else
    git clone https://github.com/fxgfxg200639/ChaoXingReserveSeat.git
    cd ChaoXingReserveSeat
fi

# 3. 安装Python依赖
echo "[3/6] 安装Python依赖..."
pip3 install flask requests cryptography opencv-python-headless pillow numpy --break-system-packages -q 2>/dev/null || pip3 install flask requests cryptography opencv-python-headless pillow numpy -q

# 4. 初始化配置
echo "[4/6] 初始化配置..."
if [ ! -f admin_config.json ]; then
    echo "首次运行，自动导入账号配置..."
fi

# 5. 启动服务
echo "[5/6] 启动Flask服务..."
pkill -f "python3 app.py" 2>/dev/null || true
sleep 1
nohup python3 app.py > /home/ubuntu/app.log 2>&1 &
sleep 2

# 6. 验证
echo "[6/6] 验证服务..."
if curl -s http://localhost:5002/ > /dev/null; then
    echo ""
    echo "========================================="
    echo "  ✅ 部署成功！"
    echo "  手机浏览器打开: http://124.223.173.154:5002"
    echo "========================================="
else
    echo "❌ 启动失败，查看日志: cat /home/ubuntu/app.log"
fi
