"""
Web 服务：接收浏览器发来的消息，调 main.py 处理，返回结果
让李敏能在浏览器里操作，录视频展示
"""

from flask import Flask, request, jsonify, render_template

from main import process_message

app = Flask(__name__)


@app.route("/")
def index():
    """渲染对话页面"""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """接收客户消息，返回处理结果"""
    data = request.get_json()
    msg = data.get("message", "").strip()
    if not msg:
        return jsonify({"error": "消息不能为空"}), 400

    result = process_message(msg)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
