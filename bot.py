import discord
import os
import logging
import google.generativeai as genai
import config_loader
import asyncio # Import asyncio

_message_queue = None # 全局变量，用于存储消息队列

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Gemini API 初始化 ---
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    gemini_model = genai.GenerativeModel(config_loader.config.get('gemini_model', 'gemini-1.5-flash'))
    logging.info("Google Gemini API 初始化成功。")
except Exception as e:
    logging.error(f"Google Gemini API 初始化失败: {e}")
    gemini_model = None

# --- Discord 机器人客户端 ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """当机器人成功连接时调用"""
    logging.info(f'机器人已以 {client.user} 的身份登录')
    logging.info(f'机器人ID: {client.user.id}')
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

    # 启动一个后台任务来处理来自队列的消息
    client.loop.create_task(message_queue_processor())

async def message_queue_processor():
    """后台任务：从消息队列中读取并处理消息"""
    while True:
        if _message_queue and not _message_queue.empty():
            message_task = _message_queue.get()
            task_type = message_task.get('type')

            if task_type == 'channel_message':
                channel_id = message_task.get('channel_id')
                message_content = message_task.get('message_content')
                await send_message_to_channel(channel_id, message_content)
            elif task_type == 'dm_message':
                user_id = message_task.get('user_id')
                message_content = message_task.get('message_content')
                await send_dm_to_user(user_id, message_content)
            else:
                logging.warning(f"未知消息任务类型: {task_type}")
        await asyncio.sleep(1) # 避免CPU占用过高，每秒检查一次

@client.event
async def on_message(message):
    """当收到消息时调用"""
    # 1. 忽略机器人自己的消息
    if message.author == client.user:
        return

    # 2. 违禁词检查
    # 将消息内容转为小写以便匹配
    message_content_lower = message.content.lower()
    if any(word in message_content_lower for word in config_loader.banned_words):
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, 您的消息包含不当词汇，已被删除。", delete_after=10)
            logging.warning(f"用户 {message.author} 的消息因包含违禁词被删除: {message.content}")
            return # 删除后不再继续处理
        except discord.Forbidden:
            logging.error("机器人没有删除消息的权限。")
        except Exception as e:
            logging.error(f"删除消息时发生错误: {e}")
        return

    # 3. 检查机器人是否被提及或使用了命令前缀
    prefix = config_loader.config.get('command_prefix')
    is_mentioned = client.user.mentioned_in(message)
    is_command = prefix and message.content.startswith(prefix)

    if not is_mentioned and not is_command:
        return

    # 提取问题内容
    if is_mentioned:
        # 移除提及部分
        question = message.content.replace(f'<@!{client.user.id}>', '').replace(f'<@{client.user.id}>', '').strip()
    else: # is_command
        question = message.content[len(prefix):].strip()

    if not question:
        await message.channel.send(f"{message.author.mention}, 请输入您的问题。")
        return

    # 4. 调用 Gemini API 生成回复
    if not gemini_model:
        await message.channel.send("抱歉，智能问答服务当前不可用。")
        return
        
    async with message.channel.typing():
        try:
            # 构建包含FAQ的提示
            prompt = f"""
            请根据以下FAQ内容和你的通用知识来回答用户的问题。优先使用FAQ中的信息。

            --- FAQ 开始 ---
            {config_loader.faq_content}
            --- FAQ 结束 ---

            用户的问题是: "{question}"
            """
            
            response = await gemini_model.generate_content_async(prompt)
            
            # 发送回复
            await message.reply(response.text)
            logging.info(f"成功回复用户 {message.author}: {question}")

        except Exception as e:
            logging.error(f"调用 Gemini API 时出错: {e}")
            await message.reply("抱歉，我在思考时遇到了一个问题，请稍后再试。")

async def send_message_to_channel(channel_id: int, message_content: str):
    """
    主动向指定频道发送消息。
    :param channel_id: 频道ID
    :param message_content: 消息内容
    """
    try:
        channel = await client.fetch_channel(channel_id)
        if channel:
            logging.info(f"成功找到频道 {channel.name} (ID: {channel_id})。尝试发送消息...")
            await channel.send(message_content)
            logging.info(f"成功向频道 {channel_id} 发送消息。")
        else:
            logging.error(f"未找到频道ID: {channel_id}。请确认机器人已加入该服务器且有权限查看该频道。")
    except Exception as e:
        logging.error(f"向频道 {channel_id} 发送消息失败: {e}")

async def send_dm_to_user(user_id: int, message_content: str):
    """
    主动向指定用户发送私信。
    :param user_id: 用户ID
    :param message_content: 消息内容
    """
    try:
        user = await client.fetch_user(user_id)
        if user:
            await user.send(message_content)
            logging.info(f"成功向用户 {user_id} 发送私信。")
        else:
            logging.error(f"未找到用户ID: {user_id}。")
    except Exception as e:
        logging.error(f"向用户 {user_id} 发送私信失败: {e}")

def run_bot(message_queue):
    """启动机器人"""
    global _message_queue
    _message_queue = message_queue
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logging.error("错误: DISCORD_BOT_TOKEN 环境变量未设置。")
        return

    try:
        client.run(token)
    except discord.errors.LoginFailure:
        logging.error("Discord Token 无效，请检查 .env 文件中的 DISCORD_BOT_TOKEN。")
    except Exception as e:
        logging.error(f"启动机器人时发生未知错误: {e}")
