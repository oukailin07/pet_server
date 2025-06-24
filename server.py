from flask import Flask, request, jsonify, render_template
from datetime import datetime

app = Flask(__name__)
data_list = []

@app.route('/upload', methods=['POST'])
def upload():
    json_data = request.get_json()
    json_data['timestamp'] = datetime.now().isoformat()
    data_list.append(json_data)
    return jsonify({"status": "ok"})

@app.route('/data', methods=['GET'])
def get_data():
    return jsonify(data_list[-20:])  # 只返回最近20条

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)

