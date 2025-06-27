#!/bin/bash

echo "========================================"
echo "宠物喂食器服务器 - Ubuntu启动脚本"
echo "========================================"

# 检查虚拟环境是否存在
if [ -d "pet_server_env" ]; then
    echo "检测到虚拟环境，正在激活..."
    source pet_server_env/bin/activate
else
    echo "未检测到虚拟环境，使用系统Python..."
fi

# 检查Python版本
echo "Python版本:"
python3 --version

# 检查依赖
echo "检查依赖..."
python3 -c "import flask, flask_sqlalchemy, websockets" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "依赖未安装，正在安装..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "依赖安装失败，请手动安装: pip3 install -r requirements.txt"
        exit 1
    fi
    echo "依赖安装完成"
else
    echo "依赖检查通过"
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p templates static logs instance

# 设置权限
echo "设置文件权限..."
chmod +x pet_feeder_server.py

echo ""
echo "启动服务器..."
echo "服务器地址: http://127.0.0.1:80"
echo "WebSocket地址: ws://127.0.0.1:8765"
echo "按 Ctrl+C 停止服务器"
echo "========================================"

# 启动服务器
python3 pet_feeder_server.py 