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
import websockets
import asyncio
from sqlalchemy import text, or_, func
import math

app = Flask(__name__)
app.secret_key = 'pet_feeder_secret_key_2024'

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pet_feeder.db?timeout=30'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 设置WAL模式提升并发能力
with app.app_context():
    db.session.execute(text('PRAGMA journal_mode=WAL;'))
    db.session.commit()

# 设备信息存储
devices = {}
connected_devices = {}
pending_sync_frontends = {}  # device_id -> frontend websocket connection
ws_loop = None

# 数据库模型
class AdminUser(db.Model):
    """管理员用户表"""
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), default='admin')  # admin, super_admin
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

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
    is_confirmed = db.Column(db.Boolean, default=False)  # 新增：设备确认后为True
    is_pending_delete = db.Column(db.Boolean, default=False)  # 新增：标记为待删除

class ManualFeeding(db.Model):
    """手动喂食记录表"""
    __tablename__ = 'manual_feedings'
    
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(20), db.ForeignKey('devices.device_id'), nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    feeding_amount = db.Column(db.Float, nullable=False)
    is_confirmed = db.Column(db.Boolean, default=False)  # 新增：设备确认收到指令
    is_executed = db.Column(db.Boolean, default=False)   # 设备实际执行
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime, nullable=True)
    is_pending_delete = db.Column(db.Boolean, default=False)  # 新增：标记为待删除

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
        print("原始请求体：", request.get_data(as_text=True))
        print("Content-Type：", request.content_type)
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        device_id = data.get('device_id')
        day_of_week = data.get('day_of_week')
        hour = data.get('hour')
        minute = data.get('minute')
        feeding_amount = data.get('feeding_amount')
        print(f"[{datetime.now()}] 收到喂食计划请求:")
        print(f"  设备ID: {device_id}")
        print(f"  星期: {day_of_week}")
        print(f"  时间: {hour}:{minute}")
        print(f"  分量: {feeding_amount}g")
        if not all([device_id, day_of_week, hour, minute, feeding_amount]):
            return jsonify({"error": "Missing required fields"}), 400
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            return jsonify({"error": "Device not found"}), 404
        day_of_week = int(day_of_week)
        hour = int(hour)
        minute = int(minute)
        feeding_amount = float(feeding_amount)
        feeding_plan = FeedingPlan(
            device_id=device_id,
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            feeding_amount=feeding_amount,
            is_confirmed=False  # 新增：等待设备确认
        )
        db.session.add(feeding_plan)
        db.session.commit()
        print(f"为设备 {device_id} 添加喂食计划: 星期{day_of_week} {hour:02d}:{minute:02d} {feeding_amount}g")
        response = {"status": "success", "message": "Feeding plan added"}
        print("喂食计划响应内容：", response)
        # 推送到设备
        ws = connected_devices.get(device_id)
        if ws and ws_loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps(data)),
                    ws_loop
                )
                print(f"已通过WebSocket下发到 {device_id}: {data}")
            except Exception as e:
                print(f"WebSocket下发失败: {e}")
        else:
            print(f"设备 {device_id} 未连接WebSocket，无法下发")
        return jsonify(response), 200
    except Exception as e:
        print(f"添加喂食计划时出错: {e}")
        return jsonify({"error": str(e)}), 500

# 获取喂食计划
@app.route('/get_feeding_plans', methods=['GET'])
def get_feeding_plans():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400
    # 只返回已确认且未标记为待删除的计划
    feeding_plans = FeedingPlan.query.filter_by(
        device_id=device_id, 
        is_active=True, 
        is_confirmed=True,
        is_pending_delete=False
    ).all()
    feeding_plan_list = []
    for plan in feeding_plans:
        feeding_plan_list.append({
            "device_id": plan.device_id,
            "day_of_week": plan.day_of_week,
            "hour": plan.hour,
            "minute": plan.minute,
            "feeding_amount": plan.feeding_amount,
            "created_at": plan.created_at
        })
    return jsonify({"feeding_plans": feeding_plan_list})

# 手动喂食
@app.route('/manual_feeding', methods=['POST'])
def manual_feeding():
    """手动喂食"""
    try:
        print("原始请求体：", request.get_data(as_text=True))
        print("Content-Type：", request.content_type)
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        device_id = data.get('device_id')
        hour = data.get('hour')
        minute = data.get('minute')
        feeding_amount = data.get('feeding_amount')
        print(f"[{datetime.now()}] 收到手动喂食请求:")
        print(f"  设备ID: {device_id}")
        print(f"  时间: {hour}:{minute}")
        print(f"  分量: {feeding_amount}g")
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
        # 检查是否已存在同一时间、同一分量、未执行的手动喂食
        manual_feeding = ManualFeeding.query.filter_by(
            device_id=device_id,
            hour=hour,
            minute=minute,
            feeding_amount=feeding_amount,
            is_executed=False
        ).first()
        if manual_feeding:
            response = {"status": "success", "message": "Manual feeding already exists"}
            print(f"手动喂食已存在: {device_id} {hour:02d}:{minute:02d} {feeding_amount}g")
            # 不再推送WebSocket，避免设备端重复收到
            return jsonify(response), 200
        # 否则才新建并推送
        manual_feeding = ManualFeeding(
            device_id=device_id,
            hour=hour,
            minute=minute,
            feeding_amount=feeding_amount
        )
        db.session.add(manual_feeding)
        db.session.commit()
        # 只在新建时推送
        ws = connected_devices.get(device_id)
        if ws and ws_loop:
            try:
                asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps(data)),
                    ws_loop
                )
                print(f"已通过WebSocket下发手动喂食到 {device_id}: {data}")
            except Exception as e:
                print(f"WebSocket下发手动喂食失败: {e}")
        else:
            print(f"设备 {device_id} 未连接WebSocket，无法下发手动喂食")
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
        print("收到POST /，请求头：", dict(request.headers))
        return redirect(url_for('index'))
    # 管理员支持通过?device_id=xxx切换设备视图
    if 'admin_user' in session and request.args.get('device_id'):
        device_id = request.args.get('device_id')
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            flash('设备不存在', 'error')
            return redirect(url_for('admin_devices'))
    else:
        if 'device_id' not in session:
            return redirect(url_for('login'))
        device_id = session['device_id']
        device = Device.query.filter_by(device_id=device_id).first()
        if not device:
            session.pop('device_id', None)
            return redirect(url_for('login'))
    beijing = pytz.timezone('Asia/Shanghai')
    last_seen_local = device.last_seen.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_seen else None
    last_grain_update_local = device.last_grain_update.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_grain_update else None
    feeding_plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True, is_pending_delete=False).all()
    manual_feedings = ManualFeeding.query.filter_by(device_id=device_id, is_executed=False, is_pending_delete=False).all()
    recent_manual_feedings = ManualFeeding.query.filter_by(device_id=device_id, is_pending_delete=False).order_by(ManualFeeding.created_at.desc()).limit(10).all()
    recent_records = FeedingRecord.query.filter_by(device_id=device_id).order_by(FeedingRecord.created_at.desc()).limit(10).all()
    # 预处理时间，转换为北京时间
    for record in recent_records:
        record.created_at_local = record.created_at.replace(tzinfo=pytz.utc).astimezone(beijing)
    for m in recent_manual_feedings:
        if m.executed_at:
            m.executed_at_local = m.executed_at.replace(tzinfo=pytz.utc).astimezone(beijing)
    # 合并喂食计划
    merged_plans = {}
    for plan in feeding_plans:
        key = f"{plan.day_of_week}-{plan.hour}-{plan.minute}"
        merged_plans[key] = merged_plans.get(key, 0) + plan.feeding_amount
    # 合并手动喂食
    merged_manuals = {}
    for m in recent_manual_feedings:
        # 只有已确认但未执行的才显示在待执行列表中
        if m.is_confirmed and not m.is_executed:
            key = f"{m.hour}-{m.minute}-0"  # 0表示待执行
            merged_manuals[key] = merged_manuals.get(key, 0) + m.feeding_amount
        # 已执行的显示在已执行列表中
        elif m.is_executed:
            key = f"{m.hour}-{m.minute}-1"  # 1表示已执行
            merged_manuals[key] = merged_manuals.get(key, 0) + m.feeding_amount
    return render_template('index.html', 
                         device=device, 
                         feeding_plans=feeding_plans,
                         manual_feedings=manual_feedings,
                         recent_manual_feedings=recent_manual_feedings,
                         recent_records=recent_records,
                         last_seen_local=last_seen_local,
                         last_grain_update_local=last_grain_update_local,
                         merged_plans=merged_plans,
                         merged_manuals=merged_manuals)

# 权限检查装饰器
def admin_required(f):
    """管理员权限检查装饰器"""
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            flash('需要管理员权限', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        login_type = request.form.get('login_type', 'device')  # device 或 admin
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('login.html')
        
        if login_type == 'admin':
            # 管理员登录
            admin_user = AdminUser.query.filter_by(username=username, is_active=True).first()
            if admin_user and check_password_hash(admin_user.password, password):
                session['admin_user'] = admin_user.username
                session['admin_role'] = admin_user.role
                # 更新最后登录时间
                admin_user.last_login = datetime.utcnow()
                db.session.commit()
                return redirect(url_for('admin_dashboard'))
            else:
                flash('管理员用户名或密码错误', 'error')
        else:
            # 设备登录
            device = Device.query.filter_by(device_id=username).first()
            if device and check_password_hash(device.password, password):
                session['device_id'] = username
                return redirect(url_for('index'))
            else:
                flash('设备ID或密码错误', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """登出"""
    session.pop('device_id', None)
    session.pop('admin_user', None)
    session.pop('admin_role', None)
    return redirect(url_for('login'))

@app.route('/devices')
def list_devices():
    """设备列表（管理员页面）"""
    devices = Device.query.all()
    return render_template('devices.html', devices=devices)

@app.route('/admin')
@admin_required
def admin_dashboard():
    """管理员仪表板"""
    # 获取所有设备
    devices = Device.query.all()
    
    # 统计信息
    total_devices = len(devices)
    online_devices = len([d for d in devices if d.is_online])
    offline_devices = total_devices - online_devices
    
    # 获取最近的喂食记录
    recent_records = FeedingRecord.query.order_by(FeedingRecord.created_at.desc()).limit(20).all()
    
    # 获取最近的手动喂食
    recent_manuals = ManualFeeding.query.order_by(ManualFeeding.created_at.desc()).limit(20).all()
    
    # 转换为北京时间
    beijing = pytz.timezone('Asia/Shanghai')
    for device in devices:
        device.last_seen_local = device.last_seen.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_seen else None
        device.last_grain_update_local = device.last_grain_update.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_grain_update else None
    
    for record in recent_records:
        record.created_at_local = record.created_at.replace(tzinfo=pytz.utc).astimezone(beijing)
    
    for manual in recent_manuals:
        if manual.executed_at:
            manual.executed_at_local = manual.executed_at.replace(tzinfo=pytz.utc).astimezone(beijing)
    
    return render_template('admin_dashboard.html',
                         devices=devices,
                         total_devices=total_devices,
                         online_devices=online_devices,
                         offline_devices=offline_devices,
                         recent_records=recent_records,
                         recent_manuals=recent_manuals)

@app.route('/admin/devices')
@admin_required
def admin_devices():
    """管理员设备管理页面"""
    devices = Device.query.all()
    beijing = pytz.timezone('Asia/Shanghai')
    
    for device in devices:
        device.last_seen_local = device.last_seen.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_seen else None
        device.last_grain_update_local = device.last_grain_update.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_grain_update else None
        # 检查设备是否在线
        device.is_online_now = (datetime.utcnow() - device.last_seen).total_seconds() < 300 if device.last_seen else False
    
    return render_template('admin_devices.html', devices=devices)

@app.route('/admin/device/<device_id>')
@admin_required
def admin_device_detail(device_id):
    """管理员查看单个设备详情"""
    device = Device.query.filter_by(device_id=device_id).first()
    if not device:
        flash('设备不存在', 'error')
        return redirect(url_for('admin_devices'))
    
    # 获取设备的喂食计划
    feeding_plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True, is_pending_delete=False).all()
    
    # 获取设备的手动喂食记录
    manual_feedings = ManualFeeding.query.filter_by(device_id=device_id, is_pending_delete=False).order_by(ManualFeeding.created_at.desc()).limit(50).all()
    
    # 获取设备的喂食记录
    feeding_records = FeedingRecord.query.filter_by(device_id=device_id).order_by(FeedingRecord.created_at.desc()).limit(50).all()
    
    # 转换为北京时间
    beijing = pytz.timezone('Asia/Shanghai')
    device.last_seen_local = device.last_seen.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_seen else None
    device.last_grain_update_local = device.last_grain_update.replace(tzinfo=pytz.utc).astimezone(beijing) if device.last_grain_update else None
    
    for record in feeding_records:
        record.created_at_local = record.created_at.replace(tzinfo=pytz.utc).astimezone(beijing)
    
    for manual in manual_feedings:
        if manual.executed_at:
            manual.executed_at_local = manual.executed_at.replace(tzinfo=pytz.utc).astimezone(beijing)
    
    return render_template('admin_device_detail.html',
                         device=device,
                         feeding_plans=feeding_plans,
                         manual_feedings=manual_feedings,
                         feeding_records=feeding_records)

@app.route('/api/devices')
def api_devices():
    """API: 获取所有设备"""
    devices = Device.query.all()
    device_list = []
    beijing = pytz.timezone('Asia/Shanghai')
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
            'last_grain_update': device.last_grain_update.replace(tzinfo=pytz.utc).astimezone(beijing).strftime('%Y-%m-%d %H:%M:%S') if device.last_grain_update else None
        }
        device_list.append(device_info)
    return jsonify({
        "total_devices": len(device_list),
        "devices": device_list
    })

@app.route('/api/feeding_plans/<device_id>')
def api_feeding_plans(device_id):
    """API: 获取设备的喂食计划"""
    plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True, is_pending_delete=False).all()
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
    """API: 获取设备的喂食记录，合并计划和手动，支持period参数（24h/week/month/halfyear）"""
    from datetime import datetime, timedelta
    period = request.args.get('period', '24h')
    now = datetime.utcnow()
    if period == '24h':
        since = now - timedelta(hours=24)
    elif period == 'week':
        since = now - timedelta(days=7)
    elif period == 'month':
        since = now - timedelta(days=30)
    elif period == 'halfyear':
        since = now - timedelta(days=183)
    else:
        since = now - timedelta(hours=24)
    # 计划喂食记录
    plan_records = FeedingRecord.query.filter_by(device_id=device_id).filter(FeedingRecord.created_at >= since).all()
    # 手动喂食记录（只要已执行的，executed_at或created_at有一个在周期内就返回）
    manual_records = ManualFeeding.query.filter_by(device_id=device_id, is_executed=True).filter(
        or_(ManualFeeding.executed_at >= since, ManualFeeding.created_at >= since)
    ).all()
    # 合并
    merged = []
    for r in plan_records:
        merged.append({
            'id': r.id,
            'day_of_week': r.day_of_week,
            'hour': r.hour,
            'minute': r.minute,
            'feeding_amount': r.feeding_amount,
            'actual_amount': r.actual_amount,
            'status': r.status,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'plan'
        })
    for m in manual_records:
        merged.append({
            'id': m.id,
            'day_of_week': None,
            'hour': m.hour,
            'minute': m.minute,
            'feeding_amount': m.feeding_amount,
            'actual_amount': m.feeding_amount,
            'status': 'success' if m.is_executed else '',
            'created_at': m.executed_at.strftime('%Y-%m-%d %H:%M:%S') if m.executed_at else m.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'manual'
        })
    # 按时间排序
    merged.sort(key=lambda x: x['created_at'])
    return jsonify({"records": merged})

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
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    # 支持批量删除
    merged_key = data.get('merged_key')
    if merged_key:
        try:
            day_of_week, hour, minute = map(int, merged_key.split('-'))
        except Exception:
            return jsonify({"error": "Invalid merged_key format"}), 400
        
        # 查询未标记为待删除的计划
        plans = FeedingPlan.query.filter_by(
            day_of_week=day_of_week, 
            hour=hour, 
            minute=minute,
            is_pending_delete=False
        ).all()
        
        if not plans:
            return jsonify({"error": "No matching plans found"}), 404

        # 合并克数，按设备分组
        device_amounts = {}
        for plan in plans:
            device_amounts.setdefault(plan.device_id, 0)
            device_amounts[plan.device_id] += plan.feeding_amount

        # 标记为待删除，不直接删除
        for plan in plans:
            plan.is_pending_delete = True
        db.session.commit()

        # 下发合并后的删除消息
        for device_id, total_amount in device_amounts.items():
            ws = connected_devices.get(device_id)
            if ws and ws_loop:
                try:
                    msg = {
                        "type": "delete_feeding_plan",
                        "day_of_week": day_of_week,
                        "hour": hour,
                        "minute": minute,
                        "feeding_amount": total_amount
                    }
                    asyncio.run_coroutine_threadsafe(
                        ws.send(json.dumps(msg)),
                        ws_loop
                    )
                    print(f"已通过WebSocket通知设备 {device_id} 删除喂食计划: {msg}")
                except Exception as e:
                    print(f"WebSocket下发删除喂食计划失败: {e}")
            else:
                print(f"设备 {device_id} 未连接WebSocket，无法下发删除喂食计划")

        return jsonify({"status": "success", "message": "Feeding plans marked for deletion"}), 200

    # 兼容原有单条删除
    plan_id = data.get('id')
    if not plan_id:
        return jsonify({"error": "Missing plan id"}), 400
    
    plan = FeedingPlan.query.filter_by(id=plan_id, is_pending_delete=False).first()
    if not plan:
        return jsonify({"error": "Feeding plan not found"}), 404
    
    # 标记为待删除
    plan.is_pending_delete = True
    db.session.commit()
    
    # 推送删除消息到设备
    ws = connected_devices.get(plan.device_id)
    if ws and ws_loop:
        try:
            msg = {
                "type": "delete_feeding_plan",
                "day_of_week": plan.day_of_week,
                "hour": plan.hour,
                "minute": plan.minute,
                "feeding_amount": plan.feeding_amount
            }
            asyncio.run_coroutine_threadsafe(
                ws.send(json.dumps(msg)),
                ws_loop
            )
            print(f"已通过WebSocket通知设备 {plan.device_id} 删除喂食计划: {msg}")
        except Exception as e:
            print(f"WebSocket下发删除喂食计划失败: {e}")
    else:
        print(f"设备 {plan.device_id} 未连接WebSocket，无法下发删除喂食计划")
    
    return jsonify({"status": "success", "message": "Feeding plan marked for deletion"}), 200

@app.route('/delete_manual_feeding', methods=['POST'])
def delete_manual_feeding():
    try:
        # 增加日志，便于排查
        print('收到删除手动喂食请求，headers:', dict(request.headers))
        print('收到删除手动喂食请求，body:', request.get_data(as_text=True))
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        data = request.get_json()
        print('解析后的JSON:', data)
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        # 支持批量删除（merged_key格式）
        merged_key = data.get('merged_key')
        if merged_key:
            try:
                hour, minute, status = map(int, merged_key.split('-'))
            except Exception:
                return jsonify({"error": "Invalid merged_key format"}), 400
            
            # 查询未标记为待删除的手动喂食记录
            manuals = ManualFeeding.query.filter_by(
                hour=hour,
                minute=minute,
                is_pending_delete=False
            ).all()
            
            if not manuals:
                return jsonify({"error": "No matching manual feedings found"}), 404
            
            # 按设备分组
            device_amounts = {}
            for manual in manuals:
                device_amounts.setdefault(manual.device_id, 0)
                device_amounts[manual.device_id] += manual.feeding_amount
            
            # 标记为待删除
            for manual in manuals:
                manual.is_pending_delete = True
            db.session.commit()
            
            # 下发删除消息到各设备
            for device_id, total_amount in device_amounts.items():
                ws = connected_devices.get(device_id)
                if ws and ws_loop:
                    try:
                        msg = {
                            "type": "delete_manual_feeding",
                            "hour": hour,
                            "minute": minute,
                            "feeding_amount": total_amount
                        }
                        asyncio.run_coroutine_threadsafe(
                            ws.send(json.dumps(msg)),
                            ws_loop
                        )
                        print(f"已通过WebSocket通知设备 {device_id} 删除手动喂食: {msg}")
                    except Exception as e:
                        print(f"WebSocket下发删除手动喂食失败: {e}")
                else:
                    print(f"设备 {device_id} 未连接WebSocket，无法下发删除手动喂食")
            
            return jsonify({"status": "success", "message": "Manual feedings marked for deletion"}), 200
        
        # 兼容原有单条删除（id格式）
        manual_id = data.get('id')
        if not manual_id:
            return jsonify({"error": "Missing manual id or merged_key"}), 400
        
        # 先查找是否已在删除中
        manual_pending = ManualFeeding.query.filter_by(id=manual_id, is_pending_delete=True).first()
        if manual_pending:
            return jsonify({"error": "Manual feeding already pending delete"}), 409
        
        manual = ManualFeeding.query.filter_by(id=manual_id, is_pending_delete=False).first()
        if not manual:
            return jsonify({"error": "Manual feeding not found"}), 404
        
        device_id = manual.device_id
        
        # 标记为待删除，不直接删除
        manual.is_pending_delete = True
        db.session.commit()
        
        # 构造详细删除信息（不包含id）
        manual_info = {
            "hour": manual.hour,
            "minute": manual.minute,
            "feeding_amount": manual.feeding_amount
        }
        
        response = {"status": "success", "message": "Manual feeding marked for deletion"}
        
        # --- WebSocket下发删除通知 ---
        ws = connected_devices.get(device_id)
        if ws and ws_loop:
            try:
                msg = {"type": "delete_manual_feeding", **manual_info}
                asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps(msg)),
                    ws_loop
                )
                print(f"已通过WebSocket通知设备 {device_id} 删除手动喂食: {msg}")
            except Exception as e:
                print(f"WebSocket下发删除手动喂食失败: {e}")
        else:
            print(f"设备 {device_id} 未连接WebSocket，无法下发删除手动喂食")
        
        return jsonify(response), 200
    except Exception as e:
        import traceback
        print('删除手动喂食异常:', e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/manual_feedings')
def api_manual_feedings():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400
    manuals = ManualFeeding.query.filter_by(device_id=device_id, is_pending_delete=False).order_by(ManualFeeding.created_at.desc()).limit(20).all()
    manual_list = []
    for m in manuals:
        manual_list.append({
            "id": m.id,
            "hour": m.hour,
            "minute": m.minute,
            "feeding_amount": m.feeding_amount,
            "is_executed": m.is_executed
        })
    return jsonify({"manual_feedings": manual_list})

# 设备离线检测任务
def check_device_online():
    """定期同步设备 is_online 字段，以 WebSocket 连接为准"""
    while True:
        try:
            with app.app_context():
                devices = Device.query.all()
                for device in devices:
                    device.is_online = device.device_id in connected_devices
                db.session.commit()
        except Exception as e:
            print(f"同步设备在线状态时出错: {e}")
        time.sleep(10)  # 每10秒同步一次

# 创建数据库表
def create_tables():
    """创建数据库表"""
    with app.app_context():
        db.create_all()
        print("数据库表创建完成")

# WebSocket服务
async def ws_handler(websocket):
    device_id = None
    is_device = False  # 标记是否为设备端
    try:
        # 新建连接时打印ID和客户端IP
        peer = websocket.remote_address[0] if hasattr(websocket, 'remote_address') and websocket.remote_address else 'unknown'
        print(f"新的WebSocket连接建立，等待注册消息... websocket id={id(websocket)} peer={peer}")
        register_msg = await websocket.recv()
        print(f"收到注册消息: {register_msg} websocket id={id(websocket)} peer={peer}")
        data = json.loads(register_msg)
        print(f"解析后的注册数据: {data} websocket id={id(websocket)} peer={peer}")
        
        # 检查是否是前端发送的sync_request
        if data.get('type') == 'sync_request':
            print(f"检测到前端直接发送的sync_request websocket id={id(websocket)} peer={peer}")
            # 前端直接发送sync_request，不需要注册，不写connected_devices
            target_device_id = data.get('device_id')
            print(f"前端请求同步设备: {target_device_id}")
            
            # 记录前端连接，等待同步结果
            pending_sync_frontends[target_device_id] = websocket
            print(f"记录前端连接等待同步结果: device_id={target_device_id}, websocket id={id(websocket)}")
            
            ws_device = connected_devices.get(target_device_id)
            if ws_device:
                try:
                    sync_msg = json.dumps({'type': 'sync_request'})
                    print(f"准备发送sync_request消息: {sync_msg}")
                    await ws_device.send(sync_msg)
                    print(f"已转发sync_request到设备 {target_device_id}")
                    await websocket.send(json.dumps({
                        'type': 'sync_request_sent',
                        'device_id': target_device_id,
                        'message': '同步请求已发送到设备'
                    }))
                except Exception as e:
                    print(f"发送sync_request到设备 {target_device_id} 失败: {e}")
                    # 清理前端连接记录
                    if target_device_id in pending_sync_frontends:
                        del pending_sync_frontends[target_device_id]
                    await websocket.send(json.dumps({
                        'type': 'sync_request_failed',
                        'device_id': target_device_id,
                        'error': str(e)
                    }))
            else:
                print(f"设备 {target_device_id} 未连接")
                # 清理前端连接记录
                if target_device_id in pending_sync_frontends:
                    del pending_sync_frontends[target_device_id]
                await websocket.send(json.dumps({
                    'type': 'sync_request_failed',
                    'device_id': target_device_id,
                    'error': '设备未连接'
                }))
            # 不要return，让前端连接保持，能收到后续sync_result
        # 设备端注册流程
        elif data.get("type") == "register" and data.get("device_id"):
            device_id = data["device_id"]
            is_device = True
            connected_devices[device_id] = websocket
            print(f"设备 {device_id} 注册，当前在线设备: {list(connected_devices.keys())}")
            with app.app_context():
                Device.query.filter_by(device_id=device_id).update({"is_online": True, "last_seen": datetime.utcnow()})
                db.session.commit()
            await websocket.send(json.dumps({"status": "registered"}))
            print(f"设备 {device_id} 已连接 WebSocket")
        # 新设备注册分配流程
        elif not data.get("device_id") or data.get("type") == "register":
            print("执行新设备注册流程")
            with app.app_context():
                new_device_id = generate_device_id()
                new_password = "123456"  # 默认密码
                new_device = Device(
                    device_id=new_device_id,
                    password=generate_password_hash(new_password),
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    is_online=True,
                    heartbeat_count=1
                )
                db.session.add(new_device)
                db.session.commit()
                await websocket.send(json.dumps({
                    "type": "register_result",
                    "device_id": new_device_id,
                    "password": new_password,
                    "message": "Device registered successfully"
                }))
                device_id = new_device_id
                is_device = True
                connected_devices[device_id] = websocket
                print(f"WebSocket分配新设备ID: {new_device_id}，当前在线设备: {list(connected_devices.keys())}")
        else:
            device_id = data.get("device_id")
            print(f"现有设备连接: {device_id}")
            is_device = True
            connected_devices[device_id] = websocket
            print(f"将设备 {device_id} 添加到连接列表，当前在线设备: {list(connected_devices.keys())}")
            with app.app_context():
                Device.query.filter_by(device_id=device_id).update({"is_online": True, "last_seen": datetime.utcnow()})
                db.session.commit()
            await websocket.send(json.dumps({"status": "registered"}))
            print(f"设备 {device_id} 已连接 WebSocket")
        
        # 保持连接
        while True:
            try:
                print(f"等待设备 {device_id} 的消息... websocket id={id(websocket)} peer={peer}")
                msg = await websocket.recv()
                print(f"收到设备 {device_id} 消息: {msg} websocket id={id(websocket)} peer={peer}")
                try:
                    msg_data = json.loads(msg)
                    print(f"解析后的消息类型: {msg_data.get('type')} websocket id={id(websocket)} peer={peer}")
                    
                    # 新增：前端同步请求（设备端转发）
                    if msg_data.get('type') == 'sync_request':
                        print(f"收到sync_request，设备ID: {msg_data.get('device_id')}")
                        print(f"当前连接的设备: {list(connected_devices.keys())}")
                        # 转发给目标设备
                        target_device_id = msg_data.get('device_id')
                        ws_device = connected_devices.get(target_device_id)
                        print(f"目标设备WebSocket: {ws_device is not None}")
                        print(f"目标设备ID: {target_device_id}")
                        print(f"当前WebSocket连接数: {len(connected_devices)}")
                        if ws_device:
                            # 转发sync_request到设备
                            try:
                                sync_msg = json.dumps({'type': 'sync_request'})
                                print(f"准备发送sync_request消息: {sync_msg}")
                                await ws_device.send(sync_msg)
                                print(f"已转发sync_request到设备 {target_device_id}")
                            except Exception as e:
                                print(f"发送sync_request到设备 {target_device_id} 失败: {e}")
                        else:
                            print(f"未找到目标设备WebSocket，设备 {target_device_id} 未连接")
                            print(f"当前已连接的设备: {list(connected_devices.keys())}")
                    # 新增：设备上报同步结果
                    elif msg_data.get('type') == 'sync_result':
                        # 设备上报所有数据，后端核对并更新数据库
                        with app.app_context():
                            sync_device_id = msg_data.get('device_id')
                            print(f"收到设备 {sync_device_id} 同步数据上报 websocket id={id(websocket)} peer={peer}")
                            
                            # 1. 更新粮桶重量
                            grain_weight = msg_data.get('grain_weight')
                            if grain_weight is not None:
                                device = Device.query.filter_by(device_id=sync_device_id).first()
                                if device:
                                    device.grain_weight = float(grain_weight)
                                    device.last_grain_update = datetime.utcnow()
                                    print(f"更新设备 {sync_device_id} 粮桶重量: {grain_weight}g")
                            
                            # 2. 核对并更新喂食计划
                            device_plans = msg_data.get('feeding_plans', [])
                            if device_plans:
                                # 获取数据库中的计划
                                db_plans = FeedingPlan.query.filter_by(
                                    device_id=sync_device_id, 
                                    is_active=True, 
                                    is_pending_delete=False
                                ).all()
                                
                                # 将数据库计划转换为字典，便于比较
                                db_plans_dict = {}
                                for plan in db_plans:
                                    key = f"{plan.day_of_week}-{plan.hour}-{plan.minute}"
                                    db_plans_dict[key] = plan.feeding_amount
                                
                                # 将设备计划转换为字典
                                device_plans_dict = {}
                                for plan in device_plans:
                                    key = f"{plan.get('day_of_week')}-{plan.get('hour')}-{plan.get('minute')}"
                                    device_plans_dict[key] = plan.get('feeding_amount', 0)
                                
                                # 以设备数据为准，更新数据库
                                for key, amount in device_plans_dict.items():
                                    day, hour, minute = map(int, key.split('-'))
                                    # 查找或创建计划
                                    plan = FeedingPlan.query.filter_by(
                                        device_id=sync_device_id,
                                        day_of_week=day,
                                        hour=hour,
                                        minute=minute,
                                        is_pending_delete=False
                                    ).first()
                                    
                                    if plan:
                                        # 更新现有计划
                                        if plan.feeding_amount != amount:
                                            plan.feeding_amount = amount
                                            plan.is_confirmed = True
                                            print(f"更新喂食计划: {day}-{hour:02d}:{minute:02d} {amount}g")
                                    else:
                                        # 创建新计划
                                        new_plan = FeedingPlan(
                                            device_id=sync_device_id,
                                            day_of_week=day,
                                            hour=hour,
                                            minute=minute,
                                            feeding_amount=amount,
                                            is_confirmed=True
                                        )
                                        db.session.add(new_plan)
                                        print(f"新增喂食计划: {day}-{hour:02d}:{minute:02d} {amount}g")
                                
                                # 删除设备中没有但数据库存在的计划
                                for key in db_plans_dict:
                                    if key not in device_plans_dict:
                                        day, hour, minute = map(int, key.split('-'))
                                        plan = FeedingPlan.query.filter_by(
                                            device_id=sync_device_id,
                                            day_of_week=day,
                                            hour=hour,
                                            minute=minute,
                                            is_pending_delete=False
                                        ).first()
                                        if plan:
                                            db.session.delete(plan)
                                            print(f"删除喂食计划: {day}-{hour:02d}:{minute:02d}")
                            
                            # 3. 核对并更新手动喂食
                            device_manuals = msg_data.get('manual_feedings', [])
                            if device_manuals:
                                # 获取数据库中的手动喂食
                                db_manuals = ManualFeeding.query.filter_by(
                                    device_id=sync_device_id,
                                    is_pending_delete=False
                                ).all()
                                # 将数据库手动喂食转换为字典，key用统一格式
                                db_manuals_dict = {}
                                for manual in db_manuals:
                                    key = f"{manual.hour}-{manual.minute}-{float(manual.feeding_amount):.2f}"
                                    db_manuals_dict[key] = {
                                        'is_confirmed': manual.is_confirmed,
                                        'is_executed': manual.is_executed,
                                        'executed_at': manual.executed_at
                                    }
                                    print(f"[DB现有] hour={manual.hour}, minute={manual.minute}, amount={manual.feeding_amount}, is_confirmed={manual.is_confirmed}, is_executed={manual.is_executed}")
                                # 以设备数据为准，更新数据库
                                for manual_data in device_manuals:
                                    hour = manual_data.get('hour')
                                    minute = manual_data.get('minute')
                                    amount = manual_data.get('feeding_amount')
                                    is_confirmed = manual_data.get('is_confirmed', False)
                                    is_executed = manual_data.get('is_executed', False)
                                    executed_at = manual_data.get('executed_at')
                                    key = f"{hour}-{minute}-{float(amount):.2f}"
                                    # 查找或创建手动喂食记录
                                    manual = ManualFeeding.query.filter_by(
                                        device_id=sync_device_id,
                                        hour=hour,
                                        minute=minute,
                                        feeding_amount=amount,
                                        is_pending_delete=False
                                    ).filter(func.round(ManualFeeding.feeding_amount, 2) == round(float(amount), 2)).first()
                                    if manual:
                                        # 更新现有记录
                                        updated = False
                                        if manual.is_confirmed != is_confirmed:
                                            manual.is_confirmed = is_confirmed
                                            updated = True
                                        if manual.is_executed != is_executed:
                                            manual.is_executed = is_executed
                                            updated = True
                                        if executed_at and not manual.executed_at:
                                            manual.executed_at = datetime.utcfromtimestamp(executed_at)
                                            updated = True
                                        if updated:
                                            print(f"[更新] hour={hour}, minute={minute}, amount={amount}, is_confirmed={is_confirmed}, is_executed={is_executed}")
                                    else:
                                        # 创建新记录
                                        new_manual = ManualFeeding(
                                            device_id=sync_device_id,
                                            hour=hour,
                                            minute=minute,
                                            feeding_amount=amount,
                                            is_confirmed=is_confirmed,
                                            is_executed=is_executed
                                        )
                                        if executed_at:
                                            new_manual.executed_at = datetime.utcfromtimestamp(executed_at)
                                        db.session.add(new_manual)
                                        print(f"[新增] hour={hour}, minute={minute}, amount={amount}, is_confirmed={is_confirmed}, is_executed={is_executed}")
                                # 删除设备中没有但数据库存在的手动喂食
                                device_manuals_keys = set()
                                for manual_data in device_manuals:
                                    key = f"{manual_data.get('hour')}-{manual_data.get('minute')}-{float(manual_data.get('feeding_amount')):.2f}"
                                    device_manuals_keys.add(key)
                                for key in db_manuals_dict:
                                    if key not in device_manuals_keys:
                                        hour, minute, amount = key.split('-')
                                        manual = ManualFeeding.query.filter_by(
                                            device_id=sync_device_id,
                                            hour=int(hour),
                                            minute=int(minute),
                                            feeding_amount=float(amount),
                                            is_pending_delete=False
                                        ).filter(func.round(ManualFeeding.feeding_amount, 2) == round(float(amount), 2)).first()
                                        if manual:
                                            db.session.delete(manual)
                                            print(f"[删除] hour={hour}, minute={minute}, amount={amount}, is_confirmed={manual.is_confirmed}, is_executed={manual.is_executed}")
                            
                            # 提交所有更改
                            db.session.commit()
                            print(f"设备 {sync_device_id} 数据同步完成 websocket id={id(websocket)} peer={peer}")
                        
                        # 推送sync_result到前端
                        frontend_ws = pending_sync_frontends.get(sync_device_id)
                        if frontend_ws:
                            try:
                                await frontend_ws.send(json.dumps({
                                    'type': 'sync_result',
                                    'device_id': sync_device_id,
                                    'message': '同步完成'
                                }))
                                print(f"已推送sync_result到前端 websocket id={id(frontend_ws)} peer={frontend_ws.remote_address[0] if hasattr(frontend_ws, 'remote_address') and frontend_ws.remote_address else 'unknown'}")
                            except Exception as e:
                                print(f"推送sync_result到前端失败: {e} websocket id={id(frontend_ws)}")
                            finally:
                                # 清理前端连接记录
                                if sync_device_id in pending_sync_frontends:
                                    del pending_sync_frontends[sync_device_id]
                                    print(f"已清理前端连接记录: device_id={sync_device_id}")
                        else:
                            print(f"未找到等待同步的前端连接 device_id={sync_device_id}")
                            print(f"当前等待同步的前端连接: {list(pending_sync_frontends.keys())}")
                        print(f"设备 {sync_device_id} 同步数据已上报并通知前端 websocket id={id(websocket)} peer={peer}")
                    # 设备端确认喂食计划
                    elif msg_data.get('type') == 'confirm_feeding_plan':
                        with app.app_context():
                            plan = FeedingPlan.query.filter_by(
                                device_id=msg_data.get('device_id'),
                                day_of_week=msg_data.get('day_of_week'),
                                hour=msg_data.get('hour'),
                                minute=msg_data.get('minute'),
                                feeding_amount=msg_data.get('feeding_amount'),
                                is_confirmed=False
                            ).first()
                            if plan:
                                plan.is_confirmed = True
                                db.session.commit()
                                print(f"设备确认喂食计划: {msg_data}")
                    # 设备端确认手动喂食
                    elif msg_data.get('type') == 'confirm_manual_feeding':
                        with app.app_context():
                            manual = ManualFeeding.query.filter_by(
                                device_id=msg_data.get('device_id'),
                                hour=msg_data.get('hour'),
                                minute=msg_data.get('minute'),
                                feeding_amount=msg_data.get('feeding_amount'),
                                is_confirmed=False,
                                is_executed=False
                            ).order_by(ManualFeeding.created_at.asc()).first()
                            if manual:
                                manual.is_confirmed = True
                                db.session.commit()
                                print(f"已标记手动喂食为待执行: {msg_data}")
                            else:
                                print(f"未找到待确认的手动喂食记录: {msg_data}")
                    elif msg_data.get('type') == 'manual_feeding':
                        # 设备实际执行了手动喂食，标记为已执行
                        with app.app_context():
                            manual = ManualFeeding.query.filter_by(
                                device_id=msg_data.get('device_id'),
                                hour=msg_data.get('hour'),
                                minute=msg_data.get('minute'),
                                feeding_amount=msg_data.get('feeding_amount'),
                                is_executed=False
                            ).order_by(ManualFeeding.created_at.asc()).first()
                            if manual:
                                manual.is_executed = True
                                manual.executed_at = datetime.utcfromtimestamp(msg_data.get('timestamp', datetime.utcnow().timestamp()))
                                db.session.commit()
                                print(f"设备已执行手动喂食: {msg_data}")
                            else:
                                print(f"未找到未执行的手动喂食记录: {msg_data}")
                    elif msg_data.get('type') == 'feeding_record':
                        try:
                            with app.app_context():
                                import os
                                print('数据库文件:', db.engine.url)
                                db_path = db.engine.url.database
                                if db_path:
                                    print('数据库绝对路径:', os.path.abspath(db_path))
                                else:
                                    print('数据库路径为空')
                                record = FeedingRecord(
                                    device_id=msg_data.get('device_id'),
                                    day_of_week=int(msg_data.get('day_of_week')),
                                    hour=int(msg_data.get('hour')),
                                    minute=int(msg_data.get('minute')),
                                    feeding_amount=float(msg_data.get('feeding_amount')),
                                    actual_amount=float(msg_data.get('feeding_amount')),
                                    status='success',
                                    created_at=datetime.utcfromtimestamp(msg_data.get('timestamp', datetime.utcnow().timestamp()))
                                )
                                db.session.add(record)
                                db.session.commit()
                                print(f"已保存喂食记录到数据库: {msg_data}")
                                # 立即查询最新一条
                                latest = FeedingRecord.query.filter_by(device_id=msg_data.get('device_id')).order_by(FeedingRecord.created_at.desc()).first()
                                print('最新一条FeedingRecord:', latest.day_of_week, latest.hour, latest.minute, latest.feeding_amount, latest.created_at) if latest else print('未查到最新记录')
                        except Exception as e:
                            import traceback
                            print(f"保存喂食记录时出错: {e}")
                            traceback.print_exc()
                    # 设备端确认删除喂食计划
                    elif msg_data.get('type') == 'confirm_delete_feeding_plan':
                        with app.app_context():
                            plans = FeedingPlan.query.filter_by(
                                device_id=msg_data.get('device_id'),
                                day_of_week=msg_data.get('day_of_week'),
                                hour=msg_data.get('hour'),
                                minute=msg_data.get('minute'),
                                feeding_amount=msg_data.get('feeding_amount'),
                                is_pending_delete=True
                            ).all()
                            if plans:
                                for plan in plans:
                                    db.session.delete(plan)
                                db.session.commit()
                                print(f"设备确认删除喂食计划，已从数据库删除: {msg_data}")
                            else:
                                print(f"未找到待删除的喂食计划: {msg_data}")
                    # 设备端确认删除手动喂食
                    elif msg_data.get('type') == 'confirm_delete_manual_feeding':
                        with app.app_context():
                            manual = ManualFeeding.query.filter_by(
                                device_id=msg_data.get('device_id'),
                                hour=msg_data.get('hour'),
                                minute=msg_data.get('minute'),
                                feeding_amount=msg_data.get('feeding_amount'),
                                is_pending_delete=True
                            ).order_by(ManualFeeding.created_at.asc()).first()
                            if manual:
                                db.session.delete(manual)
                                db.session.commit()
                                print(f"设备确认删除手动喂食，已从数据库删除: {msg_data}")
                            else:
                                print(f"未找到待删除的手动喂食记录: {msg_data}")
                    # 新增：设备WebSocket上报粮桶重量
                    elif msg_data.get('type') == 'grain_weight':
                        with app.app_context():
                            device_id = msg_data.get('device_id')
                            grain_weight = msg_data.get('grain_weight')
                            # 校验grain_weight合法性
                            if (device_id and grain_weight is not None and
                                isinstance(grain_weight, (int, float)) and
                                not math.isinf(grain_weight) and not math.isnan(grain_weight)):
                                device = Device.query.filter_by(device_id=device_id).first()
                                if device:
                                    device.grain_weight = float(grain_weight)
                                    device.last_grain_update = datetime.utcnow()
                                    db.session.commit()
                                    print(f"设备 {device_id} WebSocket上报粮桶重量: {grain_weight}g")
                                    # 可选：推送到前端
                                    for ws_client in list(connected_devices.values()):
                                        try:
                                            await ws_client.send(json.dumps({
                                                'type': 'grain_weight_update',
                                                'device_id': device_id,
                                                'grain_weight': grain_weight,
                                                'update_time': datetime.utcnow().isoformat()
                                            }))
                                        except Exception as e:
                                            print(f"推送粮桶重量到前端失败: {e}")
                            else:
                                print(f"收到非法grain_weight数值: {grain_weight}，已忽略。device_id={device_id}")
                    else:
                        print(f"未知消息类型: {msg_data.get('type')} websocket id={id(websocket)} peer={peer}")
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}, 原始消息: {msg} websocket id={id(websocket)} peer={peer}")
                except Exception as e:
                    print(f"处理设备消息时出错: {e} websocket id={id(websocket)} peer={peer}")
                    import traceback
                    traceback.print_exc()
            except websockets.exceptions.ConnectionClosed as e:
                print(f"WebSocket连接已关闭: {e} websocket id={id(websocket)} peer={peer}")
                break
            except Exception as e:
                print(f"WebSocket消息接收出错: {e} websocket id={id(websocket)} peer={peer}")
                import traceback
                traceback.print_exc()
                break
    except Exception as e:
        print(f"设备 {device_id} 断开: {e} websocket id={id(websocket)} peer={peer}")
    finally:
        # 只删除自己对应的设备连接
        if is_device and device_id and device_id in connected_devices and connected_devices[device_id] == websocket:
            del connected_devices[device_id]
            print(f"设备 {device_id} 断开，当前在线设备: {list(connected_devices.keys())}")
        
        # 清理前端连接记录（如果是前端连接断开）
        if not is_device and device_id and device_id in pending_sync_frontends and pending_sync_frontends[device_id] == websocket:
            del pending_sync_frontends[device_id]
            print(f"前端连接断开，已清理同步等待记录: device_id={device_id}")
        
        # 清理所有指向当前websocket的前端连接记录
        keys_to_remove = []
        for key, ws in pending_sync_frontends.items():
            if ws == websocket:
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del pending_sync_frontends[key]
            print(f"清理断开的前端连接记录: device_id={key}")
        
        with app.app_context():
            if device_id:
                Device.query.filter_by(device_id=device_id).update({"is_online": False})
                db.session.commit()

# 启动WebSocket服务器线程
def start_ws_server():
    global ws_loop
    ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(ws_loop)

    async def ws_main():
        print("WebSocket服务器已启动，监听端口8765")
        async with websockets.serve(ws_handler, "0.0.0.0", 8765):
            await asyncio.Future()  # run forever

    ws_loop.run_until_complete(ws_main())

@app.route('/feeding_chart')
def feeding_chart():
    if 'device_id' not in session:
        return redirect(url_for('login'))
    device_id = session['device_id']
    return render_template('feeding_chart.html', device_id=device_id)

@app.cli.command('import_manual_to_record')
def import_manual_to_record():
    """将已执行的手动喂食批量导入 FeedingRecord 表（更宽松的去重）"""
    with app.app_context():
        count = 0
        manuals = ManualFeeding.query.filter_by(is_executed=True).all()
        for m in manuals:
            # 只要同设备、小时、分钟、分量、executed_at存在就不重复导入
            exists = FeedingRecord.query.filter_by(
                device_id=m.device_id,
                hour=m.hour,
                minute=m.minute,
                feeding_amount=m.feeding_amount,
                created_at=m.executed_at or m.created_at
            ).first()
            if not exists:
                record = FeedingRecord(
                    device_id=m.device_id,
                    day_of_week=0,  # 手动无星期
                    hour=m.hour,
                    minute=m.minute,
                    feeding_amount=m.feeding_amount,
                    actual_amount=m.feeding_amount,
                    status='success',
                    created_at=m.executed_at or m.created_at
                )
                db.session.add(record)
                count += 1
        db.session.commit()
        print(f'已导入 {count} 条手动喂食记录到 FeedingRecord 表')

@app.cli.command('fix_feeding_record_time')
def fix_feeding_record_time():
    """将 feeding_records 表所有 created_at 字段批量修正为当前时间"""
    from datetime import datetime
    with app.app_context():
        now = datetime.utcnow()
        records = FeedingRecord.query.all()
        for r in records:
            r.created_at = now
        db.session.commit()
        print(f'已将 {len(records)} 条 feeding_records 的 created_at 字段修正为 {now}')

@app.cli.command('add_manual_confirmed_field')
def add_manual_confirmed_field():
    """为 manual_feedings 表添加 is_confirmed 字段"""
    with app.app_context():
        try:
            # 添加 is_confirmed 字段
            db.session.execute(text('ALTER TABLE manual_feedings ADD COLUMN is_confirmed BOOLEAN DEFAULT FALSE'))
            db.session.commit()
            print('已为 manual_feedings 表添加 is_confirmed 字段')
            
            # 将现有的已执行记录标记为已确认
            ManualFeeding.query.filter_by(is_executed=True).update({'is_confirmed': True})
            db.session.commit()
            print('已将现有已执行的手动喂食记录标记为已确认')
            
        except Exception as e:
            print(f'添加字段时出错: {e}')
            db.session.rollback()

@app.cli.command('add_pending_delete_fields')
def add_pending_delete_fields():
    """为 feeding_plans 和 manual_feedings 表添加 is_pending_delete 字段"""
    with app.app_context():
        try:
            # 添加 feeding_plans 表的 is_pending_delete 字段
            db.session.execute(text('ALTER TABLE feeding_plans ADD COLUMN is_pending_delete BOOLEAN DEFAULT FALSE'))
            print('已为 feeding_plans 表添加 is_pending_delete 字段')
            
            # 添加 manual_feedings 表的 is_pending_delete 字段
            db.session.execute(text('ALTER TABLE manual_feedings ADD COLUMN is_pending_delete BOOLEAN DEFAULT FALSE'))
            print('已为 manual_feedings 表添加 is_pending_delete 字段')
            
            db.session.commit()
            print('所有字段添加完成')
            
        except Exception as e:
            print(f'添加字段时出错: {e}')
            db.session.rollback()

@app.cli.command('create_admin')
def create_admin():
    """创建管理员账户"""
    with app.app_context():
        try:
            # 确保表存在
            db.create_all()
            
            username = input('请输入管理员用户名: ')
            password = input('请输入管理员密码: ')
            email = input('请输入邮箱(可选): ') or None
            role = input('请输入角色(admin/super_admin, 默认admin): ') or 'admin'
            
            # 检查用户名是否已存在
            existing_admin = AdminUser.query.filter_by(username=username).first()
            if existing_admin:
                print(f'用户名 {username} 已存在')
                return
            
            # 创建管理员账户
            admin_user = AdminUser(
                username=username,
                password=generate_password_hash(password),
                email=email,
                role=role
            )
            
            db.session.add(admin_user)
            db.session.commit()
            
            print(f'管理员账户 {username} 创建成功')
            print(f'角色: {role}')
            print(f'请使用此账户登录管理员界面')
            
        except Exception as e:
            print(f'创建管理员账户时出错: {e}')
            db.session.rollback()

@app.cli.command('list_admins')
def list_admins():
    """列出所有管理员账户"""
    with app.app_context():
        try:
            admins = AdminUser.query.all()
            if not admins:
                print('没有找到管理员账户')
                return
            
            print('管理员账户列表:')
            print('-' * 60)
            for admin in admins:
                print(f'ID: {admin.id}')
                print(f'用户名: {admin.username}')
                print(f'邮箱: {admin.email or "无"}')
                print(f'角色: {admin.role}')
                print(f'状态: {"激活" if admin.is_active else "禁用"}')
                print(f'创建时间: {admin.created_at}')
                print(f'最后登录: {admin.last_login or "从未登录"}')
                print('-' * 60)
                
        except Exception as e:
            print(f'列出管理员账户时出错: {e}')

@app.route('/ota_update', methods=['POST'])
def ota_update():
    """设备OTA升级接口，普通用户可用"""
    if 'device_id' not in session:
        return jsonify({'error': '未登录，无法操作'}), 401
    device_id = session['device_id']
    data = request.get_json()
    url = data.get('url') if data else None
    if not url or not url.startswith('http'):
        return jsonify({'error': '请提供合法的固件URL'}), 400
    ws = connected_devices.get(device_id)
    if ws and ws_loop:
        try:
            msg = {
                "type": "ota_update",
                "url": url
            }
            import asyncio
            asyncio.run_coroutine_threadsafe(ws.send(json.dumps(msg)), ws_loop)
            return jsonify({'status': 'success', 'message': 'OTA升级指令已下发'}), 200
        except Exception as e:
            return jsonify({'error': f'WebSocket下发失败: {e}'}), 500
    else:
        return jsonify({'error': '设备未在线，无法下发OTA升级'}), 400

if __name__ == "__main__":
    import threading
    t = threading.Thread(target=check_device_online, daemon=True)
    t.start()
    print("设备在线状态同步任务已启动")
    # 启动WebSocket服务线程
    t = threading.Thread(target=start_ws_server, daemon=True)
    t.start()
    # 创建数据库表
    create_tables()
    # 启动Flask
    app.run(host="0.0.0.0", port=80) 