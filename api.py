import threading
from flask import Flask, jsonify, request
import logging
import asyncio
import config_loader
import bot # Import the bot module
from waitress import serve # Import waitress

_message_queue = None # 全局变量，用于存储消息队列

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/api/status', methods=['GET'])
def get_status():
    """返回机器人和API的状态"""
    return jsonify({
        "status": "ok",
        "message": "Discord bot and API are running.",
        "config": config_loader.config  # 显示当前加载的配置
    })

@app.route('/api/reload', methods=['POST'])
def reload_configs():
    """手动触发重新加载配置"""
    try:
        config_loader.load_all_configs()
        logging.info("手动触发配置重载成功。")
        return jsonify({"status": "success", "message": "Configurations reloaded."})
    except Exception as e:
        logging.error(f"手动触发配置重载失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/send_channel_message', methods=['POST'])
def send_channel_message():
    """通过API向指定频道发送消息"""
    data = request.get_json()
    channel_id = data.get('channel_id')
    message_content = data.get('message_content')

    if not channel_id or not message_content:
        return jsonify({"status": "error", "message": "缺少 channel_id 或 message_content"}), 400

    try:
        if _message_queue:
            _message_queue.put({
                'type': 'channel_message',
                'channel_id': channel_id,
                'message_content': message_content
            })
            return jsonify({"status": "success", "message": "频道消息任务已添加到队列。"}, 200)
        else:
            return jsonify({"status": "error", "message": "消息队列未初始化。"}, 500)
    except Exception as e:
        logging.error(f"API发送频道消息失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/send_dm', methods=['POST'])
def send_dm():
    """通过API向指定用户发送私信"""
    data = request.get_json()
    user_id = data.get('user_id')
    message_content = data.get('message_content')

    if not user_id or not message_content:
        return jsonify({"status": "error", "message": "缺少 user_id 或 message_content"}), 400

    try:
        if _message_queue:
            _message_queue.put({
                'type': 'dm_message',
                'user_id': user_id,
                'message_content': message_content
            })
            return jsonify({"status": "success", "message": "私信任务已添加到队列。"}, 200)
        else:
            return jsonify({"status": "error", "message": "消息队列未初始化。"}, 500)
    except Exception as e:
        logging.error(f"API发送私信失败: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def start_api_process(message_queue):
    """在与机器人不同的端口上运行 Flask API 进程"""
    global _message_queue
    _message_queue = message_queue
    host = config_loader.config.get('api_host', '0.0.0.0')
    port = config_loader.config.get('api_port', 5001)
    
    # 禁用 Flask 的默认日志，以避免与主日志冲突
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.INFO)
    serve(app, host=host, port=port)
    logging.info(f"Flask API 已在 http://{host}:{port} 的后台进程中启动。")
