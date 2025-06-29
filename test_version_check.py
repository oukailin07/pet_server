#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json

def test_version_api():
    """测试版本API"""
    base_url = "http://localhost"
    
    # 测试获取版本列表（需要登录）
    print("测试版本API...")
    
    # 创建会话
    session = requests.Session()
    
    # 先登录（这里用设备用户登录）
    login_data = {
        'username': 'ESP-001',  # 假设的设备ID
        'password': '123456',   # 默认密码
        'login_type': 'device'
    }
    
    try:
        # 登录
        login_response = session.post(f"{base_url}/login", data=login_data)
        print(f"登录状态码: {login_response.status_code}")
        
        if login_response.status_code == 200:
            print("登录成功")
            
            # 测试获取版本列表
            versions_response = session.get(f"{base_url}/api/firmware_versions")
            print(f"版本API状态码: {versions_response.status_code}")
            
            if versions_response.status_code == 200:
                versions_data = versions_response.json()
                print(f"版本数据: {json.dumps(versions_data, indent=2, ensure_ascii=False)}")
            else:
                print(f"版本API失败: {versions_response.text}")
        else:
            print("登录失败")
            
    except Exception as e:
        print(f"测试出错: {e}")

if __name__ == "__main__":
    test_version_api() 