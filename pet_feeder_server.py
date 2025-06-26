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
from sqlalchemy import text, or_

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
ws_loop = None

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
    is_confirmed = db.Column(db.Boolean, default=False)  # 新增：设备确认后为True

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
    # 只返回已确认的计划
    feeding_plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True, is_confirmed=True).all()
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
        response = {"status": "success", "message": "Manual feeding added"}
        print("手动喂食响应内容：", response)
        # --- WebSocket下发 ---
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
        return jsonify(response), 200
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
    feeding_plans = FeedingPlan.query.filter_by(device_id=device_id, is_active=True).all()
    manual_feedings = ManualFeeding.query.filter_by(device_id=device_id, is_executed=False).all()
    recent_manual_feedings = ManualFeeding.query.filter_by(device_id=device_id).order_by(ManualFeeding.created_at.desc()).limit(10).all()
    recent_records = FeedingRecord.query.filter_by(device_id=device_id).order_by(FeedingRecord.created_at.desc()).limit(10).all()
    # 合并喂食计划
    merged_plans = {}
    for plan in feeding_plans:
        key = f"{plan.day_of_week}-{plan.hour}-{plan.minute}"
        merged_plans[key] = merged_plans.get(key, 0) + plan.feeding_amount
    # 合并手动喂食
    merged_manuals = {}
    for m in recent_manual_feedings:
        key = f"{m.hour}-{m.minute}-{1 if m.is_executed else 0}"
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
        plans = FeedingPlan.query.filter_by(day_of_week=day_of_week, hour=hour, minute=minute).all()
        if not plans:
            return jsonify({"error": "No matching plans found"}), 404

        # 合并克数，按设备分组
        device_amounts = {}
        for plan in plans:
            device_amounts.setdefault(plan.device_id, 0)
            device_amounts[plan.device_id] += plan.feeding_amount

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

        # 删除所有计划
        for plan in plans:
            db.session.delete(plan)
        db.session.commit()
        return jsonify({"status": "success", "message": "Feeding plans deleted"}), 200

    # 兼容原有单条删除
    plan_id = data.get('id')
    if not plan_id:
        return jsonify({"error": "Missing plan id"}), 400
    plan = FeedingPlan.query.filter_by(id=plan_id).first()
    if not plan:
        return jsonify({"error": "Feeding plan not found"}), 404
    db.session.delete(plan)
    db.session.commit()
    return jsonify({"status": "success", "message": "Feeding plan deleted"}), 200

@app.route('/delete_manual_feeding', methods=['POST'])
def delete_manual_feeding():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        manual_id = data.get('id')
        if not manual_id:
            return jsonify({"error": "Missing manual id"}), 400
        manual = ManualFeeding.query.filter_by(id=manual_id).first()
        if not manual:
            return jsonify({"error": "Manual feeding not found"}), 404
        device_id = manual.device_id
        # 构造详细删除信息（不包含id）
        manual_info = {
            "hour": manual.hour,
            "minute": manual.minute,
            "feeding_amount": manual.feeding_amount
        }
        db.session.delete(manual)
        db.session.commit()
        response = {"status": "success", "message": "Manual feeding deleted"}
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
        return jsonify({"error": str(e)}), 500

@app.route('/api/manual_feedings')
def api_manual_feedings():
    device_id = request.args.get('device_id')
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400
    manuals = ManualFeeding.query.filter_by(device_id=device_id).order_by(ManualFeeding.created_at.desc()).limit(20).all()
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
    try:
        register_msg = await websocket.recv()
        data = json.loads(register_msg)
        # 新注册流程：如果没有 device_id 或 type: register，则分配
        if not data.get("device_id") or data.get("type") == "register":
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
                # 通过 WebSocket 返回分配结果
                await websocket.send(json.dumps({
                    "type": "register_result",
                    "device_id": new_device_id,
                    "password": new_password,
                    "message": "Device registered successfully"
                }))
                device_id = new_device_id
                print(f"WebSocket分配新设备ID: {new_device_id} 密码: {new_password}")
        else:
            device_id = data.get("device_id")
            with app.app_context():
                Device.query.filter_by(device_id=device_id).update({"is_online": True, "last_seen": datetime.utcnow()})
                db.session.commit()
            await websocket.send(json.dumps({"status": "registered"}))
            print(f"设备 {device_id} 已连接 WebSocket")
        connected_devices[device_id] = websocket
        # 保持连接
        while True:
            msg = await websocket.recv()
            print(f"收到设备 {device_id} 消息: {msg}")
            try:
                msg_data = json.loads(msg)
                # 设备端确认喂食计划
                if msg_data.get('type') == 'confirm_feeding_plan':
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
                            is_executed=False
                        ).order_by(ManualFeeding.created_at.asc()).first()
                        if manual:
                            manual.is_executed = True
                            manual.executed_at = datetime.utcfromtimestamp(msg_data.get('timestamp', datetime.utcnow().timestamp()))
                            db.session.commit()
                            print(f"设备确认手动喂食: {msg_data}")
                elif msg_data.get('type') == 'feeding_record':
                    # 保存到数据库
                    with app.app_context():
                        record = FeedingRecord(
                            device_id=msg_data.get('device_id'),
                            day_of_week=msg_data.get('day_of_week'),
                            hour=msg_data.get('hour'),
                            minute=msg_data.get('minute'),
                            feeding_amount=msg_data.get('feeding_amount'),
                            actual_amount=msg_data.get('feeding_amount'),
                            status='success',
                            created_at=datetime.utcfromtimestamp(msg_data.get('timestamp', datetime.utcnow().timestamp()))
                        )
                        db.session.add(record)
                        db.session.commit()
                        print(f"已保存喂食记录到数据库: {msg_data}")
                elif msg_data.get('type') == 'manual_feeding':
                    # 保存手动喂食到数据库（如有未执行的同时间同分量记录则只更新最早一条为已执行）
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
                            print(f"已更新手动喂食为已执行: {msg_data}")
                        else:
                            manual = ManualFeeding(
                                device_id=msg_data.get('device_id'),
                                hour=msg_data.get('hour'),
                                minute=msg_data.get('minute'),
                                feeding_amount=msg_data.get('feeding_amount'),
                                is_executed=True,
                                executed_at=datetime.utcfromtimestamp(msg_data.get('timestamp', datetime.utcnow().timestamp())),
                                created_at=datetime.utcfromtimestamp(msg_data.get('timestamp', datetime.utcnow().timestamp()))
                            )
                            db.session.add(manual)
                            db.session.commit()
                            print(f"已保存手动喂食到数据库: {msg_data}")
            except Exception as e:
                print(f"处理设备消息时出错: {e}")
    except Exception as e:
        print(f"设备 {device_id} 断开: {e}")
    finally:
        if device_id in connected_devices:
            del connected_devices[device_id]
        with app.app_context():
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