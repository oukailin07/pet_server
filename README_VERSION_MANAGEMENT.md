# �汾������ʹ��˵��

## ����

����ιʳ��ϵͳ����֧�������İ汾�����ܣ������̼��汾����OTA�������汾�ع��ȡ�

## ��������

### 1. �汾��Ϣ����
- �̼��汾�������汾�š��ΰ汾�š������汾�š������ţ�
- Э��汾����
- Ӳ���汾����
- �汾�����Լ��
- �汾��ʷ��¼

### 2. OTA��������
- �Զ��汾���
- �ֶ�ǿ������
- �������ȼ��
- ����״̬�ϱ�
- ����ʧ�ܴ���

### 3. �汾�ع�����
- �汾�ع�����
- �ع���ʷ��¼
- �ع�ԭ���¼

## ���ݿ�ṹ

### ������ṹ

#### 1. firmware_versions ��
```sql
CREATE TABLE firmware_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_string VARCHAR(32) UNIQUE NOT NULL,  -- �汾�ַ������� "v1.0.0"
    major INTEGER NOT NULL,                       -- ���汾��
    minor INTEGER NOT NULL,                       -- �ΰ汾��
    patch INTEGER NOT NULL,                       -- �����汾��
    build INTEGER DEFAULT 0,                      -- ������
    suffix VARCHAR(16) DEFAULT 'stable',          -- �汾��׺
    build_date VARCHAR(20),                       -- ��������
    build_time VARCHAR(20),                       -- ����ʱ��
    git_hash VARCHAR(16),                         -- Git�ύ��ϣ
    download_url VARCHAR(256),                    -- ����URL
    file_size INTEGER DEFAULT 0,                  -- �ļ���С
    checksum VARCHAR(64),                         -- У���
    is_stable BOOLEAN DEFAULT 1,                  -- �Ƿ�Ϊ�ȶ��汾
    is_force_update BOOLEAN DEFAULT 0,            -- �Ƿ�ǿ�Ƹ���
    min_hardware_version VARCHAR(10) DEFAULT '1.0', -- ���Ӳ���汾Ҫ��
    min_protocol_version VARCHAR(10) DEFAULT '1.0', -- ���Э��汾Ҫ��
    release_notes TEXT,                           -- ����˵��
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);
```

#### 2. device_version_history ��
```sql
CREATE TABLE device_version_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id VARCHAR(20) NOT NULL,               -- �豸ID
    from_version VARCHAR(32),                     -- ����ǰ�汾
    to_version VARCHAR(32) NOT NULL,              -- ������汾
    upgrade_type VARCHAR(20) DEFAULT 'ota',       -- �������ͣ�ota, rollback, manual
    status VARCHAR(20) DEFAULT 'success',         -- ״̬��success, failed, in_progress
    error_message TEXT,                           -- ������Ϣ
    upgrade_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    operator VARCHAR(50)                          -- ������
);
```

### �豸�������ֶ�
```sql
ALTER TABLE devices ADD COLUMN protocol_version VARCHAR(10) DEFAULT "1.0";
ALTER TABLE devices ADD COLUMN hardware_version VARCHAR(10) DEFAULT "1.0";
ALTER TABLE devices ADD COLUMN boot_count INTEGER DEFAULT 0;
ALTER TABLE devices ADD COLUMN install_time DATETIME DEFAULT CURRENT_TIMESTAMP;
```

## ʹ�÷���

### 1. ���ݿ�Ǩ��

�״�ʹ����Ҫִ�����ݿ�Ǩ�ƣ�

```bash
# �ڷ�����Ŀ¼��ִ��
python pet_feeder_server.py add_version_management_tables
```

### 2. ��ӹ̼��汾

#### ͨ�������й���
```bash
python pet_feeder_server.py add_firmware_version
```

#### ͨ��Web����
1. ��¼����Ա�˻�
2. ���� `/admin/versions` ҳ��
3. ���"��Ӱ汾"��ť
4. ��д�汾��Ϣ

#### ͨ��API
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
    "release_notes": "�޸���ιʳ����������"
  }'
```

### 3. �鿴�汾�б�

#### ͨ�������й���
```bash
python pet_feeder_server.py list_firmware_versions
```

#### ͨ��Web����
���� `/admin/versions` ҳ��

#### ͨ��API
```bash
curl http://localhost/api/firmware_versions
```

### 4. ǿ���豸����

#### ͨ��API
```bash
curl -X POST http://localhost/api/devices/ESP-001/force_update \
  -H "Content-Type: application/json" \
  -d '{
    "target_version": "v1.0.1"
  }'
```

### 5. �豸�汾�ع�

#### ͨ��API
```bash
curl -X POST http://localhost/api/devices/ESP-001/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "target_version": "v1.0.0",
    "reason": "�°汾���ڼ���������"
  }'
```

### 6. �鿴�豸�汾��ʷ

#### ͨ��API
```bash
curl http://localhost/api/devices/ESP-001/version_history
```

## WebSocket��ϢЭ��

### �豸�˷��͵���Ϣ

#### 1. �汾�������
```json
{
  "type": "version_check",
  "device_id": "ESP-001",
  "firmware_version": "v1.0.0",
  "protocol_version": "1.0",
  "hardware_version": "1.0"
}
```

#### 2. OTA״̬�ϱ�
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

#### 3. �汾�ع�����
```json
{
  "type": "rollback_request",
  "device_id": "ESP-001",
  "target_version": "v1.0.0",
  "reason": "�°汾���ȶ�"
}
```

### �������˷��͵���Ϣ

#### 1. �汾�����Ӧ
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
  "release_notes": "�޸���ιʳ����������",
  "is_compatible": true
}
```

#### 2. OTA����ָ��
```json
{
  "type": "ota_update",
  "url": "http://example.com/firmware/v1.0.1.bin",
  "version": "v1.0.1",
  "checksum": "sha256:abc123...",
  "force": false
}
```

#### 3. �汾�ع���Ӧ
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

## �汾�����Լ��

ϵͳ���Զ�������¼����ԣ�

1. **Ӳ���汾������**��Ŀ��̼������Ӳ���汾Ҫ��
2. **Э��汾������**��Ŀ��̼������Э��汾Ҫ��
3. **�汾�ż�����**�����汾�ű�����ܱ�ʾ������

## ע������

1. **�汾�Ÿ�ʽ**������ʹ�����廯�汾�ţ��� v1.0.0��
2. **ǿ�Ƹ���**������ʹ��ǿ�Ƹ��¹��ܣ����ܵ����豸���ȶ�
3. **�ع�����**���ع�ǰȷ��Ŀ��汾�ȶ��ɿ�
4. **���簲ȫ**��ȷ���̼�����URL�İ�ȫ��
5. **���ݲ���**����Ҫ�汾���鱣������

## �����ų�

### ��������

1. **�汾���ʧ��**
   - ����豸��������
   - ȷ�Ϸ������汾����������
   - �鿴��������־

2. **OTA����ʧ��**
   - ���̼��ļ�������
   - ȷ���豸�洢�ռ����
   - �鿴�豸�˴�����־

3. **�汾�ع�ʧ��**
   - ȷ��Ŀ��汾����
   - ����豸������
   - �鿴�ع���ʷ��¼

### ��־�鿴

��������־���¼���а汾��ز�����������
- �汾�������
- OTA����״̬
- �汾�ع�����
- ������Ϣ

�豸����־���¼��
- �汾�����
- OTA��������
- �����ɹ�/ʧ��״̬ 