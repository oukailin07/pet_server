# 宠物喂食器服务器

## 功能概述

这是一个完整的宠物喂食器服务器端解决方案，包含设备管理、数据库操作、Web界面等功能。

## 主要功能

### 1. 设备管理
- **自动设备ID分配**: 新设备连接时自动分配ESP-xxx格式的设备ID
- **密码管理**: 默认密码123456，支持密码验证
- **设备状态监控**: 实时监控设备在线状态
- **心跳包处理**: 处理设备心跳包，更新设备状态

### 2. 数据库管理
- **设备信息表**: 存储设备基本信息
- **喂食计划表**: 管理定时喂食计划
- **手动喂食表**: 记录手动喂食指令
- **喂食记录表**: 存储喂食执行记录

### 3. Web界面
- **登录系统**: 设备ID和密码验证
- **设备状态**: 显示设备在线情况、粮桶重量等
- **喂食计划管理**: 添加、查看、删除喂食计划
- **手动喂食**: 发送手动喂食指令
- **喂食记录**: 查看历史喂食记录
- **设备管理**: 管理员查看所有设备

## 文件结构

```
pet_feeder_server/
├── pet_feeder_server.py      # 主服务器文件
├── start_server.py           # 启动脚本
├── requirements.txt          # Python依赖
├── README_SERVER.md          # 说明文档
├── templates/                # HTML模板
│   ├── login.html           # 登录页面
│   ├── index.html           # 主页
│   └── devices.html         # 设备管理页面
├── static/                   # 静态文件
├── logs/                     # 日志文件
└── pet_feeder.db            # SQLite数据库
```

## 安装和运行

### 1. 环境要求
- Python 3.7+
- pip包管理器

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 启动服务器
```bash
# 方法1: 使用启动脚本
python start_server.py

# 方法2: 直接运行
python pet_feeder_server.py
```

### 4. 访问Web界面
- 服务器地址: http://127.0.0.1:80
- 首次访问需要输入设备ID和密码

## API接口

### 1. 设备心跳包
```
POST /device/heartbeat
Content-Type: application/json

{
    "device_id": "设备ID或空字符串",
    "device_type": "pet_feeder",
    "firmware_version": "1.0.0"
}
```

**响应格式:**
```json
{
    "need_device_id": true,
    "device_id": "ESP-001",
    "password": "123456",
    "message": "Device registered successfully"
}
```

### 2. 粮桶重量上传
```
POST /upload_grain_level
Content-Type: application/json

{
    "grain_level": 500.5
}
```

### 3. 添加喂食计划
```
POST /add_feeding_plan
Content-Type: application/json

{
    "device_id": "ESP-001",
    "day_of_week": 1,
    "hour": 8,
    "minute": 0,
    "feeding_amount": 50.0
}
```

### 4. 手动喂食
```
POST /manual_feeding
Content-Type: application/json

{
    "device_id": "ESP-001",
    "hour": 14,
    "minute": 30,
    "feeding_amount": 30.0
}
```

### 5. 添加喂食记录
```
POST /add_feeding_record
Content-Type: application/json

{
    "device_id": "ESP-001",
    "day_of_week": 1,
    "hour": 8,
    "minute": 0,
    "feeding_amount": 50.0,
    "actual_amount": 48.5,
    "status": "success"
}
```

## 数据库结构

### 1. devices表
```sql
CREATE TABLE devices (
    id INTEGER PRIMARY KEY,
    device_id VARCHAR(20) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    device_type VARCHAR(50) DEFAULT 'pet_feeder',
    firmware_version VARCHAR(20) DEFAULT '1.0.0',
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_online BOOLEAN DEFAULT FALSE,
    heartbeat_count INTEGER DEFAULT 0,
    grain_weight FLOAT DEFAULT 0.0,
    last_grain_update DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2. feeding_plans表
```sql
CREATE TABLE feeding_plans (
    id INTEGER PRIMARY KEY,
    device_id VARCHAR(20) REFERENCES devices(device_id),
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    feeding_amount FLOAT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3. manual_feedings表
```sql
CREATE TABLE manual_feedings (
    id INTEGER PRIMARY KEY,
    device_id VARCHAR(20) REFERENCES devices(device_id),
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    feeding_amount FLOAT NOT NULL,
    is_executed BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    executed_at DATETIME
);
```

### 4. feeding_records表
```sql
CREATE TABLE feeding_records (
    id INTEGER PRIMARY KEY,
    device_id VARCHAR(20) REFERENCES devices(device_id),
    day_of_week INTEGER NOT NULL,
    hour INTEGER NOT NULL,
    minute INTEGER NOT NULL,
    feeding_amount FLOAT NOT NULL,
    actual_amount FLOAT,
    status VARCHAR(20) DEFAULT 'success',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Web界面功能

### 1. 登录页面
- 设备ID和密码验证
- 美观的登录界面
- 错误提示功能

### 2. 主页功能
- **设备状态卡片**: 显示在线状态、粮桶重量、喂食计划数量、心跳次数
- **操作按钮**: 添加喂食计划、手动喂食、刷新数据、导出数据
- **喂食计划列表**: 显示当前活跃的喂食计划
- **手动喂食列表**: 显示待执行的手动喂食
- **喂食记录**: 显示最近的喂食记录

### 3. 设备管理页面
- **统计信息**: 总设备数、在线设备数、离线设备数、总心跳数
- **设备列表**: 详细的设备信息表格
- **操作功能**: 查看详情、查看计划、查看记录、删除设备

## 使用流程

### 1. 设备首次连接
1. ESP32设备启动并连接WiFi
2. 发送心跳包（device_id为空）
3. 服务器分配设备ID（ESP-001）和密码（123456）
4. 设备保存ID和密码到NVS

### 2. 设备正常使用
1. 设备定期发送心跳包（每5分钟）
2. 服务器更新设备状态
3. 设备上传粮桶重量
4. 设备执行喂食计划
5. 设备上报喂食记录

### 3. Web界面使用
1. 访问 http://127.0.0.1:80
2. 输入设备ID和密码登录
3. 查看设备状态和喂食记录
4. 添加或修改喂食计划
5. 发送手动喂食指令

## 配置说明

### 1. 服务器配置
```python
# 服务器地址和端口
app.run(host='127.0.0.1', port=80, debug=False)

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pet_feeder.db'
```

### 2. 设备ID生成规则
```python
def generate_device_id():
    # 格式: ESP-001, ESP-002, ...
    max_device = Device.query.order_by(Device.device_id.desc()).first()
    if max_device:
        current_num = int(max_device.device_id.split('-')[1])
        new_num = current_num + 1
    else:
        new_num = 1
    return f"ESP-{new_num:03d}"
```

### 3. 默认密码
- 新设备默认密码: 123456
- 密码使用Werkzeug的hash函数加密存储

## 故障排除

### 1. 服务器启动失败
- 检查端口80是否被占用
- 检查Python版本是否兼容
- 检查依赖是否正确安装

### 2. 数据库问题
- 检查数据库文件权限
- 删除数据库文件重新创建
- 检查SQLite版本

### 3. 设备连接问题
- 检查网络连接
- 检查服务器地址和端口
- 检查防火墙设置

### 4. Web界面问题
- 检查浏览器兼容性
- 清除浏览器缓存
- 检查JavaScript是否启用

## 扩展功能

### 1. 用户管理
- 添加用户注册功能
- 实现用户权限管理
- 支持多用户设备共享

### 2. 数据导出
- 支持CSV格式导出
- 支持Excel格式导出
- 支持数据备份和恢复

### 3. 通知功能
- 邮件通知
- 短信通知
- 微信推送

### 4. 数据分析
- 喂食统计图表
- 设备使用分析
- 异常检测

## 安全考虑

1. **密码安全**: 使用hash函数加密存储密码
2. **会话管理**: 使用Flask session管理用户登录状态
3. **输入验证**: 对所有用户输入进行验证
4. **SQL注入防护**: 使用SQLAlchemy ORM防止SQL注入
5. **XSS防护**: 使用Jinja2模板引擎自动转义

## 性能优化

1. **数据库索引**: 为常用查询字段添加索引
2. **连接池**: 使用数据库连接池
3. **缓存**: 添加Redis缓存支持
4. **异步处理**: 使用Celery处理异步任务
5. **负载均衡**: 支持多实例部署 