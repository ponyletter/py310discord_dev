import os
import logging
from dotenv import load_dotenv
import multiprocessing # Import multiprocessing

# 在所有其他导入之前加载 .env 文件
# 这确保了环境变量在其他模块（如 bot.py）导入时已经可用
load_dotenv()

# 导入我们的模块
import config_loader
import api
import bot

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

def main():
    """
    主函数，用于启动所有服务。
    """
    logging.info("正在启动 Gemini Discord 机器人...")

    # 创建一个用于进程间通信的队列
    message_queue = multiprocessing.Queue()

    # 1. 在后台启动文件监视器以实现热加载
    observer = config_loader.start_watching()

    # 2. 在单独进程中启动 Flask API
    api_process = multiprocessing.Process(target=api.start_api_process, args=(message_queue,), daemon=True)
    api_process.start()
    logging.info(f"Flask API 进程已启动 (PID: {api_process.pid})")

    # 3. 在主线程中运行 Discord 机器人 (这是一个阻塞操作)
    try:
        bot.run_bot(message_queue)
    except KeyboardInterrupt:
        logging.info("检测到手动中断，正在关闭服务...")
    finally:
        observer.stop()
        observer.join()
        if api_process.is_alive():
            api_process.terminate()
            api_process.join()
            logging.info("Flask API 进程已终止。")
        logging.info("文件监控已停止。")

    logging.info("机器人已停止。")

if __name__ == '__main__':
    # 验证必要的环境变量
    if not os.getenv("DISCORD_BOT_TOKEN"):
        logging.error("致命错误: DISCORD_BOT_TOKEN 未在 .env 文件中设置。")
    elif not os.getenv("GOOGLE_API_KEY"):
        logging.error("致命错误: GOOGLE_API_KEY 未在 .env 文件中设置。")
    else:
        main()
