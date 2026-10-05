# 🛡️ CẤU HÌNH SOC / SOAR PIPELINE
**Kiến trúc:** Cowrie Honeypot -> Log Forwarder (Python) -> n8n SOAR Automation -> GeoIP Lookup -> PostgreSQL Database & Telegram Alert

---

## 1. File Cấu Hình Docker (`docker-compose.yml`)

```yaml
services:
  # 1. Honeypot Cowrie (Bẫy SSH/Telnet)
  cowrie:
    image: cowrie/cowrie:latest
    container_name: honeypot_cowrie
    restart: always
    ports:
      - "2222:2222"
    volumes:
      - cowrie-logs:/cowrie/cowrie-git/var/log/cowrie
    networks:
      - soc_net

  # 2. SOC Log Forwarder (Quét real-time cowrie.json -> đẩy sang n8n Webhook)
  log_forwarder:
    image: python:3.11-alpine
    container_name: soc_log_forwarder
    restart: always
    volumes:
      - cowrie-logs:/logs:ro
      - ./honeypot/forwarder.py:/app/forwarder.py:ro
    command: sh -c "pip install --no-cache-dir requests && python /app/forwarder.py"
    networks:
      - soc_net

  # 3. n8n SOAR Engine
  n8n:
    image: n8nio/n8n:latest
    container_name: automation_n8n
    restart: always
    ports:
      - "5678:5678"
    dns:
      - 8.8.8.8
      - 1.1.1.1
    environment:
      - N8N_PORT=5678
      - WEBHOOK_URL=http://localhost:5678/
    volumes:
      - n8n-data:/home/node/.n8n
    networks:
      - soc_net

  # 4. PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: soc_postgres
    restart: always
    environment:
      POSTGRES_USER: soc_admin
      POSTGRES_PASSWORD: 123456
      POSTGRES_DB: honeypot_soc
    ports:
      - "5433:5432" # Port 5433 kết nối từ Windows (DBeaver)
    volumes:
      - pg-data:/var/lib/postgresql/data
    networks:
      - soc_net

networks:
  soc_net:
    driver: bridge

volumes:
  cowrie-logs:
  n8n-data:
  pg-data:
```

---

## 2. Mã Nguồn Log Forwarder (honeypot/forwarder.py)

File này nằm tại 03_SourceCode/honeypot/forwarder.py, có nhiệm vụ theo dõi luồng file log JSON của Cowrie theo thời gian thực và đẩy tự động sự kiện đăng nhập SSH về Webhook của n8n.

```python
import json
import time
import requests

LOG_FILE = "/logs/cowrie.json"
WEBHOOK_URL = "http://automation_n8n:5678/webhook/ac879bf9-fbef-47c7-8c18-91f0559ec6b1"

# Lấy IP Public thật của máy cá nhân làm Demo khi test ở Local
try:
    MY_PUBLIC_IP = requests.get("[https://api.ipify.org](https://api.ipify.org)", timeout=5).text
except Exception:
    MY_PUBLIC_IP = "8.8.8.8"

print(f"🚀 SOC Log Forwarder đã khởi động! IP Demo: {MY_PUBLIC_IP}", flush=True)

while True:
    try:
        with open(LOG_FILE, "r") as f:
            f.seek(0, 2)  # Đọc từ cuối file (chỉ bắt các sự kiện mới phát sinh)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                try:
                    data = json.loads(line)
                    # Chỉ lọc lấy các sự kiện SSH Login (Thành công & Thất bại)
                    if data.get("eventid") in ["cowrie.login.failed", "cowrie.login.success"]:
                        # Đổi IP Local (172.x.x.x / 127.0.0.1) thành IP Public để GeoIP tra cứu vị trí khi test Local
                        if data.get("src_ip", "").startswith("172.") or data.get("src_ip") == "127.0.0.1":
                            data["src_ip"] = MY_PUBLIC_IP
                            
                        response = requests.post(WEBHOOK_URL, json=data, timeout=5)
                        print(f"[+] Đã đẩy sự kiện {data.get('eventid')} (IP: {data.get('src_ip')}) -> n8n (Status: {response.status_code})", flush=True)
                except Exception:
                    pass
    except FileNotFoundError:
        time.sleep(1)
```

---

## 3. Lệnh Quản Lý Hệ Thống (PowerShell)

🚀 Khởi Chạy / Quản Lý Container

```powerShell
# Khởi chạy toàn bộ hệ thống ngầm
docker compose up -d

# Kiểm tra trạng thái các container đang chạy
docker ps

# Xem log kiểm tra Log Forwarder real-time
docker logs -f soc_log_forwarder

# Tắt hệ thống (Giữ lại dữ liệu DB & Volume)
docker compose down

# Reset toàn bộ container và Volume về ban đầu
docker compose down -v
```

🔑 Xóa Host Key Cũ (Khi gặp lỗi SSH WARNING)

```powerShell
ssh-keygen -R "[localhost]:2222"
```

---

## 4. Cấu Hình Cơ Sở Dữ Liệu PostgreSQL
### 🔌 Thông Số Kết Nối DBeaver

|Thông Số|Giá Trị|
|-|-|
|Host|localhost|
|Port|5433|
|Database|honeypot_soc|
|Username|soc_admin|
|Password|123456|

### 📜 Script Tạo Bảng incidents (Chạy trên DBeaver)

```SQL
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(100),
    src_ip VARCHAR(45) NOT NULL,
    src_port INT,
    username VARCHAR(100),
    password VARCHAR(100),
    country VARCHAR(100),
    city VARCHAR(100),
    latitude NUMERIC(10, 7),
    longitude NUMERIC(10, 7),
    isp VARCHAR(150),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 🔍 Lệnh Truy Vấn Kiểm Tra Dữ Liệu

```SQL
SELECT * FROM incidents ORDER BY created_at DESC;
```

## 5. Cấu Hình Workflow Trên n8n (http://localhost:5678)
### Sơ đồ luồng xử lý (Data Pipeline):
[1. Webhook] ➔ [2. HTTP Request (GeoIP)] ➔ [3. PostgreSQL (Database)] ➔ [4. Telegram (Cảnh báo)]
### 🪝 Node 1: Webhook (Nhận log từ Log Forwarder)
1. Thêm Node Webhook.
2. HTTP Method: POST.
3. Path: Giữ nguyên UUID (Ví dụ: ac879bf9-fbef-47c7-8c18-91f0559ec6b1).
### 🌐 Node 2: HTTP Request (Tra cứu Vị trí GeoIP)
1. Thêm Node HTTP Request nối sau Node Webhook.
2. Method: GET.
3. URL (Expression):

```plaintext
[http://ip-api.com/json/](http://ip-api.com/json/){{ $('Webhook').item.json.body.src_ip }}
```

4. Settings: Bật Never Error = On, Timeout = 3000 ms.
### 🐘 Node 3: PostgreSQL (Lưu Log Tấn Công vào CSDL)
1. Thêm Node PostgreSQL (Action: Insert rows in a table) nối sau Node HTTP Request.
2. Credential Connection (Chạy trong mạng Docker):
    - Host: soc_postgres
    - Port: 5432
    - Database: honeypot_soc
    - User: soc_admin
    - Password: 123456
3. Table: incidents.
4. Mapping Dữ Liệu:

|Cột CSDL|Giá Trị Ánh Xạ (Expression)|Nguồn Dữ Liệu|
|-|-|-|
|event_id|{{ $('Webhook').item.json.body.eventid }}|Từ Webhook|
|src_ip|{{ $('Webhook').item.json.body.src_ip }}|Từ Webhook|
|src_port|{{ $('Webhook').item.json.body.src_port }}|Từ Webhook|
|username|{{ $('Webhook').item.json.body.username }}|Từ Webhook|
|password|{{ $('Webhook').item.json.body.password }}|Từ Webhook|
|country|{{ $json.country }}|Từ HTTP Request (GeoIP)|
|city|{{ $json.city }}|Từ HTTP Request (GeoIP)|
|isp|{{ $json.isp }}|Từ HTTP Request (GeoIP)|

### 📲 Node 4: Telegram (Bắn Cảnh Báo Real-time)
1. Thêm Node Telegram (Action: Send a text message) nối sau Node PostgreSQL.
2. Credential: Bot Token từ @BotFather.
3. Chat ID: ID Chat/Group nhận cảnh báo.
4. Text (Expression):

```plaintext
🚨 CẢNH BÁO AN NINH - HONEYPOT SOC
----------------------------------
📌 Hành vi: Dò quét mật khẩu / Tấn công SSH (Cowrie)
⏰ Thời gian: {{ $now.setZone('Asia/Ho_Chi_Minh').toFormat('HH:mm:ss - dd/MM/yyyy') }}
🌐 IP Tấn công: {{ $('Webhook').item.json.body.src_ip }}
📍 Vị trí: {{ $('HTTP Request').item.json.city }}, {{ $('HTTP Request').item.json.country }}
🏢 Nhà mạng (ISP): {{ $('HTTP Request').item.json.isp }}
👤 Username: {{ $('Webhook').item.json.body.username }}
🔑 Password: {{ $('Webhook').item.json.body.password }}
🎯 Trạng thái: Đã ghi nhận log & Lưu Postgres
```

### ⚡ Kích Hoạt Workflow
1. Nhấn Save (Ctrl + S).
2. Gạt công tắc Active ở góc trên bên phải sang màu Xanh lá cây.

## 6. Kịch Bản Kiểm Thử (Testing Pipeline)

### 💥 1. Test Tấn Công Thật SSH Vào Honeypot (PowerShell)

```powerShell
ssh root@localhost -p 2222
```

*(Đăng nhập mật khẩu bất kỳ, ví dụ: 123456 hoặc admin123)*

### 🎯 2. Test Bắn Dữ Liệu Mẫu Trực Tiếp Vào Webhook n8n

```powerShell
Invoke-RestMethod -Uri "http://localhost:5678/webhook/ac879bf9-fbef-47c7-8c18-91f0559ec6b1" -Method Post -ContentType "application/json" -Body '{"eventid": "cowrie.login.failed", "src_ip": "8.8.8.8", "src_port": 52123, "username": "admin", "password": "123"}'
```
