#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宠物喂食器服务器测试脚本
"""

import requests
import json
import time
import random

# 服务器配置
SERVER_URL = "http://127.0.0.1:80"
DEVICE_ID = None
PASSWORD = None

def test_heartbeat_new_device():
    """测试新设备心跳包"""
    global DEVICE_ID, PASSWORD
    
    print("=" * 50)
    print("测试新设备心跳包")
    print("=" * 50)
    
    data = {
        "device_id": "",
        "device_type": "pet_feeder",
        "firmware_version": "1.0.0"
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/device/heartbeat", json=data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if result.get("need_device_id"):
                DEVICE_ID = result.get("device_id")
                PASSWORD = result.get("password")
                print(f"✓ 新设备注册成功")
                print(f"  设备ID: {DEVICE_ID}")
                print(f"  密码: {PASSWORD}")
                return True
        else:
            print(f"✗ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    return False

def test_heartbeat_existing_device():
    """测试已注册设备心跳包"""
    if not DEVICE_ID:
        print("✗ 没有设备ID，跳过测试")
        return False
    
    print("=" * 50)
    print("测试已注册设备心跳包")
    print("=" * 50)
    
    data = {
        "device_id": DEVICE_ID,
        "device_type": "pet_feeder",
        "firmware_version": "1.0.0"
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/device/heartbeat", json=data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            if not result.get("need_device_id"):
                print("✓ 已注册设备心跳包成功")
                return True
        else:
            print(f"✗ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    return False

def test_upload_grain_level():
    """测试粮桶重量上传"""
    if not DEVICE_ID:
        print("✗ 没有设备ID，跳过测试")
        return False
    
    print("=" * 50)
    print("测试粮桶重量上传")
    print("=" * 50)
    
    grain_weight = random.uniform(100, 1000)
    data = {
        "grain_level": grain_weight
    }
    
    headers = {
        "X-Device-ID": DEVICE_ID
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/upload_grain_level", json=data, headers=headers)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print(f"✓ 粮桶重量上传成功: {grain_weight}g")
            return True
        else:
            print(f"✗ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    return False

def test_add_feeding_plan():
    """测试添加喂食计划"""
    if not DEVICE_ID:
        print("✗ 没有设备ID，跳过测试")
        return False
    
    print("=" * 50)
    print("测试添加喂食计划")
    print("=" * 50)
    
    data = {
        "device_id": DEVICE_ID,
        "day_of_week": 1,  # 星期一
        "hour": 8,
        "minute": 0,
        "feeding_amount": 50.0
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/add_feeding_plan", json=data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("✓ 喂食计划添加成功")
            return True
        else:
            print(f"✗ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    return False

def test_manual_feeding():
    """测试手动喂食"""
    if not DEVICE_ID:
        print("✗ 没有设备ID，跳过测试")
        return False
    
    print("=" * 50)
    print("测试手动喂食")
    print("=" * 50)
    
    data = {
        "device_id": DEVICE_ID,
        "hour": 14,
        "minute": 30,
        "feeding_amount": 30.0
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/manual_feeding", json=data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("✓ 手动喂食指令发送成功")
            return True
        else:
            print(f"✗ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    return False

def test_add_feeding_record():
    """测试添加喂食记录"""
    if not DEVICE_ID:
        print("✗ 没有设备ID，跳过测试")
        return False
    
    print("=" * 50)
    print("测试添加喂食记录")
    print("=" * 50)
    
    data = {
        "device_id": DEVICE_ID,
        "day_of_week": 1,
        "hour": 8,
        "minute": 0,
        "feeding_amount": 50.0,
        "actual_amount": 48.5,
        "status": "success"
    }
    
    try:
        response = requests.post(f"{SERVER_URL}/add_feeding_record", json=data)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
            print("✓ 喂食记录添加成功")
            return True
        else:
            print(f"✗ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    
    return False

def test_api_endpoints():
    """测试API端点"""
    if not DEVICE_ID:
        print("✗ 没有设备ID，跳过测试")
        return False
    
    print("=" * 50)
    print("测试API端点")
    print("=" * 50)
    
    # 测试获取设备列表
    try:
        response = requests.get(f"{SERVER_URL}/api/devices")
        print(f"获取设备列表 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"设备数量: {result.get('total_devices', 0)}")
        else:
            print(f"✗ 获取设备列表失败: {response.text}")
    except Exception as e:
        print(f"✗ 获取设备列表失败: {e}")
    
    # 测试获取喂食计划
    try:
        response = requests.get(f"{SERVER_URL}/api/feeding_plans/{DEVICE_ID}")
        print(f"获取喂食计划 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"计划数量: {len(result.get('plans', []))}")
        else:
            print(f"✗ 获取喂食计划失败: {response.text}")
    except Exception as e:
        print(f"✗ 获取喂食计划失败: {e}")
    
    # 测试获取喂食记录
    try:
        response = requests.get(f"{SERVER_URL}/api/feeding_records/{DEVICE_ID}")
        print(f"获取喂食记录 - 状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"记录数量: {len(result.get('records', []))}")
        else:
            print(f"✗ 获取喂食记录失败: {response.text}")
    except Exception as e:
        print(f"✗ 获取喂食记录失败: {e}")

def test_web_interface():
    """测试Web界面"""
    print("=" * 50)
    print("测试Web界面")
    print("=" * 50)
    
    try:
        # 测试主页
        response = requests.get(f"{SERVER_URL}/")
        print(f"主页 - 状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 主页访问成功")
        else:
            print(f"✗ 主页访问失败: {response.text}")
    except Exception as e:
        print(f"✗ 主页访问失败: {e}")
    
    try:
        # 测试登录页面
        response = requests.get(f"{SERVER_URL}/login")
        print(f"登录页面 - 状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 登录页面访问成功")
        else:
            print(f"✗ 登录页面访问失败: {response.text}")
    except Exception as e:
        print(f"✗ 登录页面访问失败: {e}")
    
    try:
        # 测试设备管理页面
        response = requests.get(f"{SERVER_URL}/devices")
        print(f"设备管理页面 - 状态码: {response.status_code}")
        if response.status_code == 200:
            print("✓ 设备管理页面访问成功")
        else:
            print(f"✗ 设备管理页面访问失败: {response.text}")
    except Exception as e:
        print(f"✗ 设备管理页面访问失败: {e}")

def main():
    """主测试函数"""
    print("宠物喂食器服务器测试")
    print("=" * 60)
    
    # 检查服务器是否运行
    try:
        response = requests.get(f"{SERVER_URL}/login", timeout=5)
        if response.status_code != 200:
            print("✗ 服务器未运行或无法访问")
            print("请先启动服务器: python pet_feeder_server.py")
            return
    except Exception as e:
        print("✗ 无法连接到服务器")
        print("请确保服务器正在运行: python pet_feeder_server.py")
        return
    
    print("✓ 服务器连接正常")
    print()
    
    # 执行测试
    tests = [
        ("新设备心跳包", test_heartbeat_new_device),
        ("已注册设备心跳包", test_heartbeat_existing_device),
        ("粮桶重量上传", test_upload_grain_level),
        ("添加喂食计划", test_add_feeding_plan),
        ("手动喂食", test_manual_feeding),
        ("添加喂食记录", test_add_feeding_record),
        ("API端点", test_api_endpoints),
        ("Web界面", test_web_interface),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n正在测试: {test_name}")
        try:
            if test_func():
                passed += 1
            time.sleep(1)  # 避免请求过快
        except Exception as e:
            print(f"✗ 测试异常: {e}")
    
    # 测试结果
    print("\n" + "=" * 60)
    print("测试结果")
    print("=" * 60)
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"失败测试: {total - passed}")
    print(f"成功率: {passed/total*100:.1f}%")
    
    if DEVICE_ID:
        print(f"\n测试设备信息:")
        print(f"设备ID: {DEVICE_ID}")
        print(f"密码: {PASSWORD}")
        print(f"Web界面登录地址: {SERVER_URL}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    main() 