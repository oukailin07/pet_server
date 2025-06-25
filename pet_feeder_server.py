#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
宠物喂食器服务器
功能：
1. 设备心跳包处理
2. 设备ID和密码管理
3. 数据库操作
4. Web界面
5. 喂食计划管理
6. 手动喂食记录
7. 设备状态监控
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import sqlite3
import os
import json
import uuid
import hashlib
import threading
import time
from werkzeug.security import generate_password_hash, check_password_hash
import pytz  # 新增

app = Flask(__name__)
app.secret_key = 'pet_feeder_secret_key_2024'

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pet_feeder.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 设备信息存储
devices = {}

# 数据库模型
class Device(db.Model):
    """设备信息表"""
    __tablename__ = 'devices'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    device_type = db.Column(db.String(50), default='pet_feeder')
    firmware_version = db.Column(db.String(20), default='1.0.0')
    first_seen = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=False)
    heartbeat_count = db.Column(db.Integer, default=0)
    grain_weight = db.Column(db.Float, default=0.0)  # 粮桶重量
    last_grain_update = db.Column(db.DateTime, default=datetime.utcnow)

class FeedingPlan(db.Model):
    """喂食计划表"""
    __tablename__ = 'feeding_plans'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), db.ForeignKey('devices.device_id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 1-7 (周一到周日)
    hour = db.Column(db.Integer, nullable=False)  # 0-23
    minute = db.Column(db.Integer, nullable=False)  # 0-59
    feeding_amount = db.Column(db.Float, nullable=False)  # 喂食量(克)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ManualFeeding(db.Model):
    """手动喂食记录表"""
    __tablename__ = 'manual_feedings'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), db.ForeignKey('devices.device_id'), nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    feeding_amount = db.Column(db.Float, nullable=False)
    is_executed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime, nullable=True)

class FeedingRecord(db.Model):
    """喂食记录表"""
    __tablename__ = 'feeding_records'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), db.ForeignKey('devices.device_id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    feeding_amount = db.Column(db.Float, nullable=False)
    actual_amount = db.Column(db.Float, nullable=True)  # 实际喂食量
    status = db.Column(db.String(20), default='success')  # success, failed, partial
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# 设备ID生成器
def generate_device_id():
    """生成唯一的设备ID"""
    # 查找当前最大设备ID
    max_device = Device.query.order_by(Device.device_id.desc()).first()
    if max_device:
        # 提取数字部分
        try:
            current_num = int(max_device.device_id.split('-')[1])
            new_num = current_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    return f"ESP-{new_num:03d}"

# 心跳包处理
@app.route('/device/heartbeat', methods=['POST'])
def device_heartbeat():
    """处理设备心跳包"""
    try:
        # 先打印原始请求体和Content-Type，便于排查ESP32端请求体问题
        print("原始请求体：", request.get_data(as_text=True))
        print("Content-Type：", request.content_type)
        data = request.get_json(silent=True)
        if not data:
            print("收到空请求体或无效JSON，直接返回400")
            return jsonify({"error": "Invalid JSON data"}), 400
        device_id = data.get('device_id', '')
        device_type = data.get('device_type', 'pet_feeder')
        firmware_version = data.get('firmware_version', '1.0.0')
        print(f"[{datetime.now()}] 收到心跳包:")
        print(f"  设备ID: {device_id if device_id else 'NULL'}")
        print(f"  设备类型: {device_type}")
        print(f"  固件版本: {firmware_version}")
        # 检查设备是否已注册
        if not device_id or device_id not in [d.device_id for d in Device.query.all()]:
            # 新设备，分配设备ID和密码
            new_device_id = generate_device_id()
            new_password = "123456"  # 默认密码
            # 创建新设备记录
            new_device = Device(
                device_id=new_device_id,
                password=generate_password_hash(new_password),
                device_type=device_type,
                firmware_version=firmware_version,
                first_seen=datetime.utcnow(),
                last_seen=datetime.utcnow(),
                is_online=True,
                heartbeat_count=1
            )
            db.session.add(new_device)
            db.session.commit()
            print(f"  分配新设备ID: {new_device_id}")
            print(f"  分配密码: {new_password}")
            response = {
                "need_device_id": True,
                "device_id": new_device_id,
                "password": new_password,
                "message": "Device registered successfully"
            }
            print("心跳包响应内容：", response)
            return jsonify(response), 200
        else:
            # 已注册设备，更新最后心跳时间
            device = Device.query.filter_by(device_id=device_id).first()
            if device:
                device.last_seen = datetime.utcnow()
                device.heartbeat_count += 1
                device.is_online = True
                db.session.commit()
                print(f"  设备已注册，心跳计数: {device.heartbeat_count}")
                response = {
                    "need_device_id": False,
                    "status": "success",
                    "message": "Heartbeat received",
                    "heartbeat_count": device.heartbeat_count
                }
                print("心跳包响应内容：", response)
                return jsonify(response), 200
            else:
                return jsonify({"error": "Device not found"}), 404
    except Exception as e:
        print(f"处理心跳包时出错: {e}")
        return jsonify({"error": str(e)}), 500

# 粮桶重量上传
@app.route('/upload_grain_level', methods=['POST'])
def upload_grain_level():
    """上传粮桶重量"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        grain_weight = data.get('grain_level', 0.0)
        
        # 这里需要设备ID，可以从请求头或参数中获取
        device_id = request.headers.get('X-Device-ID') or data.get('device_id')
        
        if device_id:
            device = Device.query.filter_by(device_id=device_id).first()
            if device:
                device.grain_weight = grain_weight
                device.last_grain_update = datetime.utcnow()
                db.session.commit()
                
                print(f"设备 {device_id} 粮桶重量更新: {grain_weight}g")
                
                return jsonify({"status": "success", "message": "Grain weight updated"}), 200
        
        return jsonify({"error": "Device ID required"}), 400
        
    except Exception as e:
        print(f"上传粮桶重量时出错: {e}")
        return jsonify({"error": str(e)}), 500

# 添加喂食计划
@app.route('/add_feeding_plan', methods=['POST'])
def add_feeding_plan():
    """添加喂食计划"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        device_id = data.get('device_id')
        day_of_week = data.get('day_of_week')
        hour = data.get('hour')
        minute = data.get('minute')
        feeding_amount = data.get('feeding_amount')
        if not all([device_id, day_of_week, hour, minute, feeding_amount]):
            return jsonify({"error": "Missing required fields"}), 400
        # 检查设备是否存在
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"error": "Device not found"}), 404
        # 类型转换
        day_of_week = int(day_of_week)
        hour = int(hour)
        minute = int(minute)
        feeding_amount = float(feeding_amount)
        # 创建喂食计划
        feeding_plan = FeedingPlan(
            device_id=device_id,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            feeding_amount=feeding_amount
        )
        db.session.add(feeding_plan)
        db.session.commit()
        print(f"为设备 {device_id} 添加喂食计划: 星期{day_of_week} {hour:02d}:{minute:02d} {feeding_amount}g")
        return jsonify({"status": "success", "message": "Feeding plan added"}), 200
    except Exception as e:
        print(f"添加喂食计划时出错: {e}")
        return jsonify({"error": str(e)}), 500

# 手动喂食
@app.route('/manual_feeding', methods=['POST'])
def manual_feeding():
    """手动喂食"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        device_id = data.get('device_id')
        hour = data.get('hour')
        minute = data.get('minute')
        feeding_amount = data.get('feeding_amount')
        if not all([device_id, hour, minute, feeding_amount]):
            return jsonify({"error": "Missing required fields"}), 400
        # 检查设备是否存在
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"error": "Device not found"}), 404
        # 类型转换
        hour = int(hour)
        minute = int(minute)
        feeding_amount = float(feeding_amount)
        # 创建手动喂食记录
        manual_feeding = ManualFeeding(
            device_id=device_id,
            hour=hour,
            minute=minute,
            feeding_amount=feeding_amount
        )
        db.session.add(manual_feeding)
        db.session.commit()
        print(f"为设备 {device_id} 添加手动喂食: {hour:02d}:{minute:02d} {feeding_amount}g")
        return jsonify({"status": "success", "message": "Manual feeding added"}), 200
    except Exception as e:
        print(f"添加手动喂食时出错: {e}")
        return jsonify({"error": str(e)}), 500

# 添加喂食记录
@app.route('/add_feeding_record', methods=['POST'])
def add_feeding_record():
    """添加喂食记录"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        device_id = data.get('device_id')
        day_of_week = data.get('day_of_week')
        hour = data.get('hour')
        minute = data.get('minute')
        feeding_amount = data.get('feeding_amount')
        actual_amount = data.get('actual_amount', feeding_amount)
        status = data.get('status', 'success')
        
        if not all([device_id, day_of_week, hour, minute, feeding_amount]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # 检查设备是否存在
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"error": "Device not found"}), 404
        
        # 创建喂食记录
        feeding_record = FeedingRecord(
            device_id=device_id,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            feeding_amount=feeding_amount,
            actual_amount=actual_amount,
            status=status
        )
        
        db.session.add(feeding_record)
        db.session.commit()
        
        print(f"为设备 {device_id} 添加喂食记录: 星期{day_of_week} {hour:02d}:{minute:02d} {feeding_amount}g")
        
        return jsonify({"status": "success", "message": "Feeding record added"}), 200
        
    except Exception as e:
        print(f"添加喂食记录时出错: {e}")
        return jsonify({"error": str(e)}), 500

# Web界面路由
@app.route('/', methods=['GET', 'POST'])
def index():
    """主页"""
    if request.method == 'POST':
        if request.headers.get('Host', '').startswith('hub5p.sandai.net'):
            return '', 404
        # 如果收到POST请求，直接重定向到GET，防止405
        print("收到POST /，请求头：", dict(request.headers))
        return redirect(url_for('index'))
    if 'device_id' not in session:
        return redirect(url_for('login'))
    device_id = session['device_id']
    device = Device.query.filter_by(device_id=device_id).first()
    if not device:
        session.pop('device_id', None)
        return redirect(url_for('login'))
    # 新增：转换为北京时间
    beijing = pytz.timezone('Asia/Shanghai')
    last_seen_local = device.last_seen.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_seen else None
    # 获取设备统计信息
    feeding_plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True).all()
    manual_feedings = ManualFeeding.query.filter_by(device_id=device_id, is_executed=False).all()
    recent_records = FeedingRecord.query.filter_by(device_id=device_id).order_by(FeedingRecord.created_at.desc()).limit(10).all()
    return render_template('index.html', 
                         device=device, 
                         feeding_plans=feeding_plans,
                         manual_feedings=manual_feedings,
                         recent_records=recent_records,
                         last_seen_local=last_seen_local)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        password = request.form.get('password')
        
        if not device_id or not password:
            flash('请输入设备ID和密码', 'error')
            return render_template('login.html')
        
        device = Device.query.filter_by(device_id=device_id).first()
        
        if device and check_password_hash(device.password, password):
            session['device_id'] = device_id
            return redirect(url_for('index'))
        else:
            flash('设备ID或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """登出"""
    session.pop('device_id', None)
    return redirect(url_for('login'))

@app.route('/devices')
def list_devices():
    """设备列表（管理员页面）"""
    devices = Device.query.all()
    return render_template('devices.html', devices=devices)

@app.route('/api/devices')
def api_devices():
    """API: 获取所有设备"""
    devices = Device.query.all()
    device_list = []
    
    for device in devices:
        # 检查设备是否在线（5分钟内有心跳）
        is_online = (datetime.utcnow() - device.last_seen).total_seconds() < 300
        
        device_info = {
            'device_id': device.device_id,
            'device_type': device.device_type,
            'firmware_version': device.firmware_version,
            'heartbeat_count': device.heartbeat_count,
            'first_seen': device.first_seen.strftime('%Y-%m-%d %H:%M:%S'),
            'last_seen': device.last_seen.strftime('%Y-%m-%d %H:%M:%S'),
            'is_online': is_online,
            'grain_weight': device.grain_weight,
            'last_grain_update': device.last_grain_update.strftime('%Y-%m-%d %H:%M:%S') if device.last_grain_update else None
        }
        device_list.append(device_info)
    
    return jsonify({
        "total_devices": len(device_list),
        "devices": device_list
    })

@app.route('/api/feeding_plans/<device_id>')
def api_feeding_plans(device_id):
    """API: 获取设备的喂食计划"""
    plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True).all()
    plan_list = []
    
    for plan in plans:
        plan_info = {
            'id': plan.id,
            'day_of_week': plan.day_of_week,
            'hour': plan.hour,
            'minute': plan.minute,
            'feeding_amount': plan.feeding_amount,
            'created_at': plan.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        plan_list.append(plan_info)
    
    return jsonify({"plans": plan_list})

@app.route('/api/feeding_records/<device_id>')
def api_feeding_records(device_id):
    """API: 获取设备的喂食记录"""
    records = FeedingRecord.query.filter_by(device_id=device_id).order_by(FeedingRecord.created_at.desc()).limit(50).all()
    record_list = []
    
    for record in records:
        record_info = {
            'id': record.id,
            'day_of_week': record.day_of_week,
            'hour': record.hour,
            'minute': record.minute,
            'feeding_amount': record.feeding_amount,
            'actual_amount': record.actual_amount,
            'status': record.status,
            'created_at': record.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }
        record_list.append(record_info)
    
    return jsonify({"records": record_list})

@app.route('/edit_feeding_plan', methods=['POST'])
def edit_feeding_plan():
    """编辑喂食计划"""
    try:
        data = request.get_json()
        print("收到编辑请求：", data)
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        plan_id = data.get('id')
        day_of_week = data.get('day_of_week')
        hour = data.get('hour')
        minute = data.get('minute')
        feeding_amount = data.get('feeding_amount')
        required_fields = [plan_id, day_of_week, hour, minute, feeding_amount]
        if any(x is None or str(x).strip() == '' for x in required_fields):
            return jsonify({"error": "Missing required fields"}), 400
        # 类型转换
        plan_id = int(plan_id)
        day_of_week = int(day_of_week)
        hour = int(hour)
        minute = int(minute)
        feeding_amount = float(feeding_amount)
        plan = FeedingPlan.query.filter_by(id=plan_id).first()
        if not plan:
            return jsonify({"error": "Feeding plan not found"}), 404
        plan.day_of_week = day_of_week
        plan.hour = hour
        plan.minute = minute
        plan.feeding_amount = feeding_amount
        db.session.commit()
        return jsonify({"status": "success", "message": "Feeding plan updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_feeding_plan', methods=['POST'])
def delete_feeding_plan():
    """删除喂食计划"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        plan_id = data.get('id')
        if not plan_id:
            return jsonify({"error": "Missing plan id"}), 400
        plan = FeedingPlan.query.filter_by(id=plan_id).first()
        if not plan:
            return jsonify({"error": "Feeding plan not found"}), 404
        db.session.delete(plan)
        db.session.commit()
        return jsonify({"status": "success", "message": "Feeding plan deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 设备离线检测任务
def check_device_offline():
    """检查设备离线状态"""
    while True:
        try:
            with app.app_context():
                devices = Device.query.all()
                current_time = datetime.utcnow()
                for device in devices:
                    # 如果5分钟内有心跳，认为在线
                    if (current_time - device.last_seen).total_seconds() > 300:
                        if device.is_online:
                            device.is_online = False
                            print(f"设备 {device.device_id} 离线")
                    else:
                        if not device.is_online:
                            device.is_online = True
                            print(f"设备 {device.device_id} 上线")
                db.session.commit()  # <-- 放到这里
        except Exception as e:
            print(f"检查设备离线状态时出错: {e}")
        time.sleep(60)  # 每分钟检查一次

# 创建数据库表
def create_tables():
    """创建数据库表"""
    with app.app_context():
        db.create_all()
        print("数据库表创建完成")

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=check_device_offline, daemon=True)
    t.start()
    print("设备离线检测任务已启动")
    app.run(host="0.0.0.0", port=80) 