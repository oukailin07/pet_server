#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import os

def check_database_tables():
    """检查数据库表是否存在"""
    db_path = 'instance/pet_feeder.db'
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("数据库中的表:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 检查版本管理相关表
        required_tables = ['firmware_versions', 'device_version_history']
        for table in required_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            if cursor.fetchone():
                print(f"✓ {table} 表存在")
                
                # 检查表结构
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                print(f"  {table} 表结构:")
                for col in columns:
                    print(f"    - {col[1]} ({col[2]})")
            else:
                print(f"✗ {table} 表不存在")
        
        # 检查devices表的版本相关字段
        cursor.execute("PRAGMA table_info(devices);")
        device_columns = cursor.fetchall()
        device_column_names = [col[1] for col in device_columns]
        
        version_fields = ['protocol_version', 'hardware_version', 'boot_count', 'install_time']
        for field in version_fields:
            if field in device_column_names:
                print(f"✓ devices表包含 {field} 字段")
            else:
                print(f"✗ devices表缺少 {field} 字段")
        
        conn.close()
        
    except Exception as e:
        print(f"检查数据库时出错: {e}")

if __name__ == "__main__":
    check_database_tables() 