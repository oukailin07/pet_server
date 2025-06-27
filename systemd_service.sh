#!/bin/bash

echo "========================================"
echo "宠物喂食器服务器 - Systemd服务安装"
echo "========================================"

# 获取当前目录的绝对路径
CURRENT_DIR=$(pwd)
SERVICE_NAME="pet-feeder-server"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "当前目录: $CURRENT_DIR"

# 创建systemd服务文件
sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Pet Feeder Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/pet_server_env/bin/python $CURRENT_DIR/pet_feeder_server.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=$CURRENT_DIR

[Install]
WantedBy=multi-user.target
EOF

echo "服务文件已创建: $SERVICE_FILE"

# 重新加载systemd配置
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable $SERVICE_NAME

echo "========================================"
echo "服务安装完成！"
echo "========================================"
echo "启动服务: sudo systemctl start $SERVICE_NAME"
echo "停止服务: sudo systemctl stop $SERVICE_NAME"
echo "查看状态: sudo systemctl status $SERVICE_NAME"
echo "查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo "========================================" 