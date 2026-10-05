import json
import time
import requests

LOG_FILE = "/logs/cowrie.json"
WEBHOOK_URL = "http://automation_n8n:5678/webhook/ac879bf9-fbef-47c7-8c18-91f0559ec6b1"

# Lấy IP Public thật của máy hiện tại để làm demo khi test local
try:
    MY_PUBLIC_IP = requests.get("https://api.ipify.org", timeout=5).text
except Exception:
    MY_PUBLIC_IP = "1.1.1.1"

print("🚀 SOC Log Forwarder đã khởi động! Đang theo dõi file cowrie.json...", flush=True)

while True:
    try:
        with open(LOG_FILE, "r") as f:
            f.seek(0, 2)  # Đọc từ cuối file (chỉ bắt sự kiện mới)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                try:
                    data = json.loads(line)
                    # Chỉ đẩy các sự kiện đăng nhập SSH
                    if data.get("eventid") in ["cowrie.login.failed", "cowrie.login.success"]:
                        # Đổi IP Local (172.x.x.x / 127.0.0.1) thành IP Public để GeoIP tra cứu được
                        if data.get("src_ip", "").startswith("172.") or data.get("src_ip") == "127.0.0.1":
                            data["src_ip"] = MY_PUBLIC_IP
                        response = requests.post(WEBHOOK_URL, json=data, timeout=5)
                        print(f"[+] Đã đẩy sự kiện {data.get('eventid')} từ IP {data.get('src_ip')} sang n8n (Status: {response.status_code})", flush=True)
                except Exception as e:
                    pass
    except FileNotFoundError:
        time.sleep(1)