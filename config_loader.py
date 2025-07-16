import yaml
import logging
import threading
import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 全局变量来存储配置
config = {}
faq_content = ""
banned_words = set()

# 文件路径
CONFIG_FILE = 'config.yml'
FAQ_FILE = 'FAQ.md'
BANNED_WORDS_FILE = 'banned_words.txt'

def load_all_configs():
    """加载所有配置文件"""
    global config, faq_content, banned_words
    
    # 加载 config.yml
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            logging.info(f"成功加载配置: {CONFIG_FILE}")
    except Exception as e:
        logging.error(f"加载 {CONFIG_FILE} 失败: {e}")

    # 加载 FAQ.md
    try:
        faq_path = config.get('faq_file', FAQ_FILE)
        with open(faq_path, 'r', encoding='utf-8') as f:
            faq_content = f.read()
            logging.info(f"成功加载知识库: {faq_path}")
    except Exception as e:
        logging.error(f"加载 {faq_path} 失败: {e}")

    # 加载 banned_words.txt
    try:
        banned_words_path = config.get('banned_words_file', BANNED_WORDS_FILE)
        with open(banned_words_path, 'r', encoding='utf-8') as f:
            banned_words = {line.strip().lower() for line in f if line.strip()}
            logging.info(f"成功加载违禁词: {banned_words_path} ({len(banned_words)} 个)")
    except Exception as e:
        logging.error(f"加载 {banned_words_path} 失败: {e}")

def start_watching():
    """启动文件监控的后台线程"""
    # 初始加载
    load_all_configs()
    
    # 获取要监控的文件列表
    files_to_watch = [
        CONFIG_FILE,
        config.get('faq_file', FAQ_FILE),
        config.get('banned_words_file', BANNED_WORDS_FILE)
    ]
    
    event_handler = ConfigChangeHandler(files_to_watch)
    observer = Observer()
    # 监控当前目录
    observer.schedule(event_handler, path='.', recursive=False)
    
    # observer.start() 是非阻塞的，它会在一个新线程中运行
    observer.start()
    logging.info(f"文件监控已启动，支持热加载。正在监控: {files_to_watch}")
    return observer

class ConfigChangeHandler(FileSystemEventHandler):
    """文件变化处理器"""
    def __init__(self, files_to_watch):
        super().__init__()
        # 将文件列表转换为绝对路径以进行可靠的比较
        self.files_to_watch = [os.path.abspath(f) for f in files_to_watch]

    def on_modified(self, event):
        if not event.is_directory and os.path.abspath(event.src_path) in self.files_to_watch:
            logging.info(f"检测到文件变化: {event.src_path}, 正在热重载...")
            # 使用线程锁来避免重载过程中的竞争条件
            with threading.Lock():
                load_all_configs()

def run_watcher_in_thread():
    """在后台线程中运行文件监控"""
    # 这个函数现在只是一个别名，真正的启动在 main.py 中处理
    # 为了保持兼容性，我们保留它，但建议直接调用 start_watching
    return start_watching()

# 首次加载
load_all_configs()
