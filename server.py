from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)

# 假设这是粮桶余粮的存储变量
grain_level = 0.0

# 上传粮桶余粮的接口
@app.route('/upload_grain_level', methods=['POST'])
def upload_grain_level():
    global grain_level
    # 获取上传的 JSON 数据
    json_data = request.get_json()
    # 假设数据格式是 {"grain_level": 25.5}
    if 'grain_level' not in json_data:
        return jsonify({"error": "grain_level is required"}), 400
    
    try:
        # 解析并更新粮桶余粮
        grain_level = float(json_data['grain_level'])
        return jsonify({"status": "success", "grain_level": grain_level})
    except ValueError:
        return jsonify({"error": "Invalid grain level value"}), 400

# 获取粮桶余粮的接口
@app.route('/get_grain_level', methods=['GET'])
def get_grain_level():
    return jsonify({"grain_level": grain_level})

# 主页
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
