#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宠物喂食器服务器配置文件
"""

import os

# 服务器配置
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 80
DEBUG_MODE = False

# 数据库配置
DATABASE_URI = "sqlite:///pet_feeder.db"

# 安全配置
SECRET_KEY = "pet_feeder_secret_key_2024"
SESSION_TIMEOUT = 3600  # 会话超时时间（秒）

# 设备配置
DEFAULT_DEVICE_TYPE = "pet_feeder"
DEFAULT_FIRMWARE_VERSION = "1.0.0"
DEFAULT_PASSWORD = "123456"
DEVICE_ID_PREFIX = "ESP"
DEVICE_ID_FORMAT = "{prefix}-{number:03d}"

# 心跳配置
HEARTBEAT_TIMEOUT = 300  # 心跳超时时间（秒）
OFFLINE_CHECK_INTERVAL = 60  # 离线检测间隔（秒）

# 喂食配置
MAX_FEEDING_AMOUNT = 1000.0  # 最大喂食量（克）
MIN_FEEDING_AMOUNT = 1.0     # 最小喂食量（克）

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "logs/pet_feeder.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Web界面配置
PAGE_SIZE = 20  # 分页大小
MAX_RECORDS = 1000  # 最大记录数

# 文件路径配置
TEMPLATES_DIR = "templates"
STATIC_DIR = "static"
LOGS_DIR = "logs"

# 创建必要的目录
def create_directories():
    """创建必要的目录"""
    directories = [TEMPLATES_DIR, STATIC_DIR, LOGS_DIR]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)

# 数据库表名
TABLE_NAMES = {
    "devices": "devices",
    "feeding_plans": "feeding_plans", 
    "manual_feedings": "manual_feedings",
    "feeding_records": "feeding_records"
}

# API响应格式
API_RESPONSE_FORMAT = {
    "success": {
        "status": "success",
        "message": "操作成功"
    },
    "error": {
        "status": "error",
        "message": "操作失败"
    }
}

# 设备状态
DEVICE_STATUS = {
    "online": "online",
    "offline": "offline"
}

# 喂食状态
FEEDING_STATUS = {
    "success": "success",
    "failed": "failed", 
    "partial": "partial"
}

# 星期映射
WEEKDAY_MAP = {
    1: "星期一",
    2: "星期二", 
    3: "星期三",
    4: "星期四",
    5: "星期五",
    6: "星期六",
    7: "星期日"
}

# 时间格式
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
TIME_ONLY_FORMAT = "%H:%M"

# 错误消息
ERROR_MESSAGES = {
    "device_not_found": "设备不存在",
    "invalid_device_id": "无效的设备ID",
    "invalid_password": "密码错误",
    "missing_fields": "缺少必要字段",
    "invalid_amount": "无效的喂食量",
    "invalid_time": "无效的时间",
    "server_error": "服务器内部错误"
}

# 成功消息
SUCCESS_MESSAGES = {
    "device_registered": "设备注册成功",
    "heartbeat_received": "心跳包接收成功",
    "plan_added": "喂食计划添加成功",
    "manual_feeding_added": "手动喂食指令添加成功",
    "record_added": "喂食记录添加成功",
    "grain_updated": "粮桶重量更新成功"
} 