#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宠物喂食器服务器启动脚本
"""

import os
import sys
import subprocess
import time

def check_dependencies():
    """检查依赖是否安装"""
    try:
        import flask
        import flask_sqlalchemy
        print("✓ 依赖检查通过")
        return True
    except ImportError as e:
        print(f"✗ 缺少依赖: {e}")
        return False

def install_dependencies():
    """安装依赖"""
    print("正在安装依赖...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✓ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ 依赖安装失败: {e}")
        return False

def create_directories():
    """创建必要的目录"""
    directories = ['templates', 'static', 'logs']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ 创建目录: {directory}")

def main():
    """主函数"""
    print("=" * 50)
    print("宠物喂食器服务器启动器")
    print("=" * 50)
    
    # 创建目录
    create_directories()
    
    # 检查依赖
    if not check_dependencies():
        print("正在安装依赖...")
        if not install_dependencies():
            print("依赖安装失败，请手动安装:")
            print("pip install -r requirements.txt")
            return
    
    # 启动服务器
    print("\n启动服务器...")
    print("服务器地址: http://127.0.0.1:80")
    print("按 Ctrl+C 停止服务器")
    print("-" * 50)
    
    try:
        # 导入并启动服务器
        from pet_feeder_server import app, create_tables, start_offline_check
        
        # 创建数据库表
        create_tables()
        
        # 启动离线检测任务
        start_offline_check()
        
        # 启动Flask应用
        app.run(host='127.0.0.1', port=80, debug=False)
        
    except KeyboardInterrupt:
        print("\n服务器已停止")
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == "__main__":
    main() 