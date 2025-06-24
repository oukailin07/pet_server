from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

app = Flask(__name__)

# 设置数据库路径
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///feeding_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 定义粮桶余粮数据模型
class GrainLevel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grain_level = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 默认当前时间

# 定义喂食计划数据模型
class FeedingPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    feeding_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 默认当前时间

# 定义手动喂食记录数据模型
class ManualFeeding(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    feeding_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 默认当前时间

# 定义设备状态数据模型（设备心跳）
class DeviceStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False, unique=True)
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# 定义喂食记录数据模型
class FeedingRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.String(50), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    hour = db.Column(db.Integer, nullable=False)
    minute = db.Column(db.Integer, nullable=False)
    feeding_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # 默认当前时间
# 初始化数据库
with app.app_context():
    db.create_all()

# 上传粮桶余粮的接口
@app.route('/upload_grain_level', methods=['POST'])
def upload_grain_level():
    json_data = request.get_json()
    if 'grain_level' not in json_data:
        return jsonify({"error": "grain_level is required"}), 400
    
    try:
        grain_level = float(json_data['grain_level'])
        created_at = datetime.utcnow()  # 获取当前时间
        # 保存粮桶余粮到数据库
        new_grain_level = GrainLevel(grain_level=grain_level, created_at=created_at)
        db.session.add(new_grain_level)
        db.session.commit()

        return jsonify({"status": "success", "grain_level": grain_level, "created_at": created_at})
    except ValueError:
        return jsonify({"error": "Invalid grain level value"}), 400

# 获取粮桶余粮的接口
@app.route('/get_grain_level', methods=['GET'])
def get_grain_level():
    grain_level_entry = GrainLevel.query.order_by(GrainLevel.id.desc()).first()
    if grain_level_entry:
        return jsonify({"grain_level": grain_level_entry.grain_level, "created_at": grain_level_entry.created_at})
    return jsonify({"error": "No grain level data available"}), 404

# 获取喂食计划的接口
@app.route('/get_feeding_plans', methods=['GET'])
def get_feeding_plans():
    feeding_plans = FeedingPlan.query.all()
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

# 添加喂食计划的接口
@app.route('/add_feeding_plan', methods=['POST'])
def add_feeding_plan():
    json_data = request.get_json()

    # 检查数据是否包含所有必需的字段
    required_fields = ['device_id', 'day_of_week', 'hour', 'minute', 'feeding_amount']
    for field in required_fields:
        if field not in json_data:
            return jsonify({"error": f"{field} is required"}), 400
    
    created_at = datetime.utcnow()  # 获取当前时间
    feeding_plan = FeedingPlan(
        device_id=json_data['device_id'],
        day_of_week=json_data['day_of_week'],
        hour=json_data['hour'],
        minute=json_data['minute'],
        feeding_amount=json_data['feeding_amount'],
        created_at=created_at  # 添加创建时间
    )
    db.session.add(feeding_plan)
    db.session.commit()

    return jsonify({"status": "success", "feeding_plan": json_data, "created_at": created_at})

# 手动喂食记录的接口
@app.route('/manual_feeding', methods=['POST'])
def manual_feeding():
    json_data = request.get_json()

    # 检查数据是否包含所有必需的字段
    required_fields = ['device_id', 'hour', 'minute', 'feeding_amount']
    for field in required_fields:
        if field not in json_data:
            return jsonify({"error": f"{field} is required"}), 400
    
    created_at = datetime.utcnow()  # 获取当前时间
    manual_feed = ManualFeeding(
        device_id=json_data['device_id'],
        hour=json_data['hour'],
        minute=json_data['minute'],
        feeding_amount=json_data['feeding_amount'],
        created_at=created_at  # 添加创建时间
    )
    db.session.add(manual_feed)
    db.session.commit()

    return jsonify({"status": "success", "manual_feed": json_data, "created_at": created_at})

# 设备心跳接口
@app.route('/device/heartbeat', methods=['POST'])
def device_heartbeat():
    json_data = request.get_json()
    device_id = json_data.get('device_id')
    
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400
    
    # 更新设备的 last_seen 时间
    device = DeviceStatus.query.filter_by(device_id=device_id).first()
    if device:
        device.last_seen = datetime.utcnow()
    else:
        device = DeviceStatus(device_id=device_id, last_seen=datetime.utcnow())
        db.session.add(device)
    
    db.session.commit()

    return jsonify({"status": "success", "device_id": device_id})

# 查询设备状态接口
@app.route('/device/status', methods=['GET'])
def device_status():
    device_id = request.args.get('device_id')
    
    if not device_id:
        return jsonify({"error": "device_id is required"}), 400
    
    # 获取设备的状态
    device = DeviceStatus.query.filter_by(device_id=device_id).first()
    
    if not device:
        return jsonify({"error": "Device not found"}), 404
    
    # 判断设备是否在线（例如，最后一次更新时间超过 5 分钟则视为离线）
    offline_threshold = timedelta(minutes=5)  # 5 分钟
    if datetime.utcnow() - device.last_seen > offline_threshold:
        return jsonify({"device_id": device_id, "status": "offline", "last_seen": device.last_seen})
    
    return jsonify({"device_id": device_id, "status": "online", "last_seen": device.last_seen})

# 添加喂食记录的接口
@app.route('/add_feeding_record', methods=['POST'])
def add_feeding_record():
    json_data = request.get_json()

    # 检查数据是否包含所有必需的字段
    required_fields = ['device_id', 'day_of_week', 'hour', 'minute', 'feeding_amount']
    for field in required_fields:
        if field not in json_data:
            return jsonify({"error": f"{field} is required"}), 400
    
    created_at = datetime.utcnow()  # 获取当前时间
    feeding_record = FeedingRecord(
        device_id=json_data['device_id'],
        day_of_week=json_data['day_of_week'],
        hour=json_data['hour'],
        minute=json_data['minute'],
        feeding_amount=json_data['feeding_amount'],
        created_at=created_at  # 添加创建时间
    )
    db.session.add(feeding_record)
    db.session.commit()

    return jsonify({"status": "success", "feeding_record": json_data, "created_at": created_at})

# 主页
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
