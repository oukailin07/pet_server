# 版本管理功能使用说明

## 概述

宠物喂食器系统现已支持完整的版本管理功能，包括固件版本管理、OTA升级、版本回滚等。

## 功能特性

### 1. 版本信息管理
- 固件版本管理（主版本号、次版本号、补丁版本号、构建号）
- 协议版本管理
- 硬件版本管理
- 版本兼容性检查
- 版本历史记录

### 2. OTA升级功能
- 自动版本检查
- 手动强制升级
- 升级进度监控
- 升级状态上报
- 升级失败处理

### 3. 版本回滚功能
- 版本回滚请求
- 回滚历史记录
- 回滚原因记录

## 数据库结构

### 新增表结构

#### 1. firmware_versions 表
```sql
CREATE TABLE firmware_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_string VARCHAR(32) UNIQUE NOT NULL,  -- 版本字符串，如 "v1.0.0"
    major INTEGER NOT NULL,                       -- 主版本号
    minor INTEGER NOT NULL,                       -- 次版本号
    patch INTEGER NOT NULL,                       -- 补丁版本号
    build INTEGER DEFAULT 0,                      -- 构建号
    suffix VARCHAR(16) DEFAULT 'stable',          -- 版本后缀
    build_date VARCHAR(20),                       -- 构建日期
    build_time VARCHAR(20),                       -- 构建时间
    git_hash VARCHAR(16),                         -- Git提交哈希
    download_url VARCHAR(256),                    -- 下载URL
    file_size INTEGER DEFAULT 0,                  -- 文件大小
    checksum VARCHAR(64),                         -- 校验和
    is_stable BOOLEAN DEFAULT 1,                  -- 是否为稳定版本
    is_force_update BOOLEAN DEFAULT 0,            -- 是否强制更新
    min_hardware_version VARCHAR(10) DEFAULT '1.0', -- 最低硬件版本要求
    min_protocol_version VARCHAR(10) DEFAULT '1.0', -- 最低协议版本要求
    release_notes TEXT,                           -- 发布说明
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
```

#### 2. device_version_history 表
```sql
CREATE TABLE device_version_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id VARCHAR(20) NOT NULL,               -- 设备ID
    from_version VARCHAR(32),                     -- 升级前版本
    to_version VARCHAR(32) NOT NULL,              -- 升级后版本
    upgrade_type VARCHAR(20) DEFAULT 'ota',       -- 升级类型：ota, rollback, manual
    status VARCHAR(20) DEFAULT 'success',         -- 状态：success, failed, in_progress
    error_message TEXT,                           -- 错误信息
    upgrade_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    operator VARCHAR(50)                          -- 操作者
);
```

### 设备表新增字段
```sql
ALTER TABLE devices ADD COLUMN protocol_version VARCHAR(10) DEFAULT "1.0";
ALTER TABLE devices ADD COLUMN hardware_version VARCHAR(10) DEFAULT "1.0";
ALTER TABLE devices ADD COLUMN boot_count INTEGER DEFAULT 0;
ALTER TABLE devices ADD COLUMN install_time DATETIME DEFAULT CURRENT_TIMESTAMP;
```

## 使用方法

### 1. 数据库迁移

首次使用需要执行数据库迁移：

```bash
# 在服务器目录下执行
python pet_feeder_server.py add_version_management_tables
```

### 2. 添加固件版本

#### 通过命令行工具
```bash
python pet_feeder_server.py add_firmware_version
```

#### 通过Web界面
1. 登录管理员账户
2. 访问 `/admin/versions` 页面
3. 点击"添加版本"按钮
4. 填写版本信息

#### 通过API
```bash
curl -X POST http://localhost/api/firmware_versions \
  -H "Content-Type: application/json" \
  -d '{
    "version_string": "v1.0.1",
    "major": 1,
    "minor": 0,
    "patch": 1,
    "build": 0,
    "suffix": "stable",
    "download_url": "http://example.com/firmware/v1.0.1.bin",
    "file_size": 1048576,
    "checksum": "sha256:abc123...",
    "is_stable": true,
    "is_force_update": false,
    "release_notes": "修复了喂食器卡顿问题"
  }'
```

### 3. 查看版本列表

#### 通过命令行工具
```bash
python pet_feeder_server.py list_firmware_versions
```

#### 通过Web界面
访问 `/admin/versions` 页面

#### 通过API
```bash
curl http://localhost/api/firmware_versions
```

### 4. 强制设备升级

#### 通过API
```bash
curl -X POST http://localhost/api/devices/ESP-001/force_update \
  -H "Content-Type: application/json" \
  -d '{
    "target_version": "v1.0.1"
  }'
```

### 5. 设备版本回滚

#### 通过API
```bash
curl -X POST http://localhost/api/devices/ESP-001/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "target_version": "v1.0.0",
    "reason": "新版本存在兼容性问题"
  }'
```

### 6. 查看设备版本历史

#### 通过API
```bash
curl http://localhost/api/devices/ESP-001/version_history
```

## WebSocket消息协议

### 设备端发送的消息

#### 1. 版本检查请求
```json
{
  "type": "version_check",
  "device_id": "ESP-001",
  "firmware_version": "v1.0.0",
  "protocol_version": "1.0",
  "hardware_version": "1.0"
}
```

#### 2. OTA状态上报
```json
{
  "type": "ota_status",
  "device_id": "ESP-001",
  "status": "downloading",
  "progress": 50,
  "error_code": 0,
  "error_message": "",
  "target_version": "v1.0.1"
}
```

#### 3. 版本回滚请求
```json
{
  "type": "rollback_request",
  "device_id": "ESP-001",
  "target_version": "v1.0.0",
  "reason": "新版本不稳定"
}
```

### 服务器端发送的消息

#### 1. 版本检查响应
```json
{
  "type": "version_check_result",
  "device_id": "ESP-001",
  "has_update": true,
  "latest_version": "v1.0.1",
  "download_url": "http://example.com/firmware/v1.0.1.bin",
  "force_update": false,
  "file_size": 1048576,
  "checksum": "sha256:abc123...",
  "release_notes": "修复了喂食器卡顿问题",
  "is_compatible": true
}
```

#### 2. OTA升级指令
```json
{
  "type": "ota_update",
  "url": "http://example.com/firmware/v1.0.1.bin",
  "version": "v1.0.1",
  "checksum": "sha256:abc123...",
  "force": false
}
```

#### 3. 版本回滚响应
```json
{
  "type": "rollback_result",
  "device_id": "ESP-001",
  "target_version": "v1.0.0",
  "success": true,
  "download_url": "http://example.com/firmware/v1.0.0.bin",
  "checksum": "sha256:def456..."
}
```

## 版本兼容性检查

系统会自动检查以下兼容性：

1. **硬件版本兼容性**：目标固件的最低硬件版本要求
2. **协议版本兼容性**：目标固件的最低协议版本要求
3. **版本号兼容性**：主版本号变更可能表示不兼容

## 注意事项

1. **版本号格式**：建议使用语义化版本号（如 v1.0.0）
2. **强制更新**：谨慎使用强制更新功能，可能导致设备不稳定
3. **回滚操作**：回滚前确保目标版本稳定可靠
4. **网络安全**：确保固件下载URL的安全性
5. **备份策略**：重要版本建议保留备份

## 故障排除

### 常见问题

1. **版本检查失败**
   - 检查设备网络连接
   - 确认服务器版本管理功能正常
   - 查看服务器日志

2. **OTA升级失败**
   - 检查固件文件完整性
   - 确认设备存储空间充足
   - 查看设备端错误日志

3. **版本回滚失败**
   - 确认目标版本存在
   - 检查设备兼容性
   - 查看回滚历史记录

### 日志查看

服务器日志会记录所有版本相关操作，包括：
- 版本检查请求
- OTA升级状态
- 版本回滚操作
- 错误信息

设备端日志会记录：
- 版本检查结果
- OTA升级进度
- 升级成功/失败状态 