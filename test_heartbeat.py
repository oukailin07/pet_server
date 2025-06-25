import requests
data = {
    "device_id": "",
    "device_type": "pet_feeder",
    "firmware_version": "1.0.0"
}
r = requests.post("http://127.0.0.1:80/device/heartbeat", json=data)
print(r.status_code)
print(r.text)