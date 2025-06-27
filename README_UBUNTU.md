# 宠物喂食器服务器 - Ubuntu部署指南

## 项目简介

这是一个基于Flask的宠物喂食器服务器，提供以下功能：
- 设备心跳包处理
- 设备ID和密码管理
- 数据库操作
- Web界面
- 喂食计划管理
- 手动喂食记录
- 设备状态监控
- WebSocket实时通信

## 系统要求

- Ubuntu 18.04 或更高版本
- Python 3.7+
- 至少 512MB 内存
- 至少 1GB 磁盘空间

## 快速安装

### 方法一：使用安装脚本（推荐）

1. 克隆或下载项目到Ubuntu服务器
2. 给安装脚本执行权限：
   ```bash
   chmod +x install_ubuntu.sh
   ```
3. 运行安装脚本：
   ```bash
   ./install_ubuntu.sh
   ```

### 方法二：手动安装

1. 更新系统包：
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv sqlite3
   ```

2. 创建虚拟环境：
   ```bash
   python3 -m venv pet_server_env
   source pet_server_env/bin/activate
   ```

3. 安装依赖：
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## 启动服务器

### 方法一：使用启动脚本

```bash
chmod +x start_ubuntu.sh
./start_ubuntu.sh
```

### 方法二：手动启动

```bash
# 激活虚拟环境（如果使用）
source pet_server_env/bin/activate

# 启动服务器
python3 pet_feeder_server.py
```

### 方法三：作为系统服务运行

1. 安装systemd服务：
   ```bash
   chmod +x systemd_service.sh
   ./systemd_service.sh
   ```

2. 启动服务：
   ```bash
   sudo systemctl start pet-feeder-server
   ```

3. 查看服务状态：
   ```bash
   sudo systemctl status pet-feeder-server
   ```

4. 查看日志：
   ```bash
   sudo journalctl -u pet-feeder-server -f
   ```

## 访问服务

- Web界面：http://服务器IP:80
- WebSocket：ws://服务器IP:8765

## 端口说明

- **80端口**：HTTP Web界面
- **8765端口**：WebSocket通信

## 防火墙配置

如果启用了防火墙，需要开放相应端口：

```bash
sudo ufw allow 80
sudo ufw allow 8765
```

## 数据库

项目使用SQLite数据库，数据库文件位于：
- `instance/pet_feeder.db`：主数据库
- `instance/feeding_system.db`：喂食系统数据库

## 目录结构

```
pet_server/
├── pet_feeder_server.py    # 主服务器文件
├── requirements.txt        # Python依赖
├── install_ubuntu.sh      # Ubuntu安装脚本
├── start_ubuntu.sh        # Ubuntu启动脚本
├── systemd_service.sh     # Systemd服务安装脚本
├── templates/             # HTML模板
├── static/                # 静态文件
├── instance/              # 数据库文件
└── logs/                  # 日志文件
```

## 故障排除

### 1. 端口被占用

如果80端口被占用，可以修改 `pet_feeder_server.py` 中的端口号：

```python
app.run(host="0.0.0.0", port=8080)  # 改为8080或其他端口
```

### 2. 权限问题

确保脚本有执行权限：
```bash
chmod +x *.sh
chmod +x pet_feeder_server.py
```

### 3. 依赖安装失败

手动安装依赖：
```bash
pip3 install Flask==2.3.3 Flask-SQLAlchemy==3.0.5 Werkzeug==2.3.7 SQLAlchemy==2.0.21 websockets==11.0.3 pytz==2023.3
```

### 4. 数据库问题

如果数据库损坏，可以删除数据库文件重新创建：
```bash
rm -f instance/*.db*
```

## 维护命令

### 数据库维护

```bash
# 进入Python环境
source pet_server_env/bin/activate

# 运行数据库维护命令
python3 -c "
from pet_feeder_server import app, db
with app.app_context():
    db.create_all()
    print('数据库表创建完成')
"
```

### 日志查看

```bash
# 如果作为服务运行
sudo journalctl -u pet-feeder-server -f

# 如果直接运行
tail -f logs/server.log
```

## 安全建议

1. 修改默认密码
2. 配置防火墙
3. 使用HTTPS（生产环境）
4. 定期备份数据库
5. 监控服务器资源使用

## 联系支持

如有问题，请检查：
1. 系统日志
2. 应用日志
3. 网络连接
4. 端口占用情况 