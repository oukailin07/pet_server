#!/bin/bash

echo "========================================"
echo "宠物喂食器服务器 - Ubuntu安装脚本"
echo "========================================"

# 更新系统包
echo "正在更新系统包..."
sudo apt update

# 安装Python3和pip
echo "正在安装Python3和pip..."
sudo apt install -y python3 python3-pip python3-venv

# 检查Python版本
python3 --version

# 创建虚拟环境（推荐）
echo "正在创建Python虚拟环境..."
python3 -m venv pet_server_env

# 激活虚拟环境
echo "正在激活虚拟环境..."
source pet_server_env/bin/activate

# 升级pip
echo "正在升级pip..."
pip install --upgrade pip

# 安装项目依赖
echo "正在安装项目依赖..."
pip install -r requirements.txt

# 安装额外的系统依赖（如果需要）
echo "正在安装系统依赖..."
sudo apt install -y sqlite3

echo "========================================"
echo "安装完成！"
echo "========================================"
echo "启动服务器请运行: ./start_ubuntu.sh"
echo "或者手动启动: python3 pet_feeder_server.py" 