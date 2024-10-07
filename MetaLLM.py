import discord
from discord.ext import commands
import aiohttp
import os
from dotenv import load_dotenv
import logging
import logging.handlers
import asyncio
import json
from datetime import datetime
import time
import random

# Setup and configuration
logger = logging.getLogger('MetaLLM')
logger.setLevel(logging.DEBUG)
file_handler = logging.handlers.RotatingFileHandler(
    filename='MetaLLM.log',
    maxBytes=5*1024*1024,  # 5 MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

load_dotenv()

BOT_NAME = "META"
LM_STUDIO_URL = os.getenv(f'LM_STUDIO_URL_{BOT_NAME}', 'http://localhost:1234')
MODEL_ID_LLM = os.getenv(f'MODEL_ID_LLM_{BOT_NAME}', "meta")
DISCORD_TOKEN = os.getenv(f'DISCORD_TOKEN_{BOT_NAME}')
OTHER_BOTS = ["HERMES", "NEMO", "NEMOTRON"]
SYSTEM_PROMPT = {
    "role": "system",
    "content": f"You are {BOT_NAME}, you are in a conversation with multiple other people."
}

CHAT_HISTORY_SERVICE_URL = "http://192.168.178.117:8000"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='?', intents=intents)

HEADERS = {"Content-Type": "application/json"}
message_queue = {}
processing_channels = set()
last_response_time = {}

MAX_MESSAGE_LENGTH = 1900  # Maximum length of a single Discord message

async def record_chat_history(channel_id, message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{CHAT_HISTORY_SERVICE_URL}/add_message", json={
                "channel_id": channel_id,
                "user_id": message['user_id'],
                "content": message['content'],
                "replying_to": message.get('replying_to'),
                "role": message['role']
            }) as response:
                if response.status != 200:
                    logger.error(f"Failed to record chat history: {await response.text()}")
                else:
                    return await response.json()
    except Exception as e:
        logger.error(f"Failed to record chat history: {str(e)}")

async def get_conversation_history(channel_id, limit=10):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{CHAT_HISTORY_SERVICE_URL}/get_conversation_history/{channel_id}", 
                                   params={"limit": limit}) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get conversation history: {await response.text()}")
                    return []
    except Exception as e:
        logger.error(f"Failed to get conversation history: {str(e)}")
        return []

async def get_relevant_context(channel_id, query, limit=5):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{CHAT_HISTORY_SERVICE_URL}/get_relevant_context/{channel_id}", 
                                   params={"query": query, "limit": limit}) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get relevant context: {await response.text()}")
                    return []
    except Exception as e:
        logger.error(f"Failed to get relevant context: {str(e)}")
        return []

async def get_llm_response(prompt):
    try:
        # Filter the prompt to only include 'role' and 'content' fields
        filtered_prompt = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in prompt
            if "role" in msg and "content" in msg
        ]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LM_STUDIO_URL}/v1/chat/completions", headers=HEADERS, json={
                "model": MODEL_ID_LLM,
                "messages": filtered_prompt,
                "temperature": 0.7,
                "max_tokens": 500
            }) as response:
                if response.status == 200:
                    data = await response.json()
                    full_response = data['choices'][0]['message']['content'].strip()
                    
                    # Extract only the actual message content
                    content_start = full_response.find("Message:") + 8
                    if content_start > 8:  # If "Message:" is found
                        actual_content = full_response[content_start:].strip()
                    else:
                        actual_content = full_response
                    
                    return actual_content
                else:
                    logger.error(f"Failed to get LLM response: {await response.text()}")
                    return None
    except Exception as e:
        logger.error(f"Failed to get LLM response: {str(e)}")
        return None

def split_message(content):
    parts = []
    while len(content) > MAX_MESSAGE_LENGTH:
        split_index = content.rfind(' ', 0, MAX_MESSAGE_LENGTH)
        if split_index == -1:
            split_index = MAX_MESSAGE_LENGTH
        parts.append(content[:split_index])
        content = content[split_index:].lstrip()
    parts.append(content)
    return parts

async def send_split_message(channel, content):
    parts = split_message(content)
    for part in parts:
        await channel.send(part)

async def get_structured_input(channel_id, current_message):
    history = await get_conversation_history(channel_id)
    relevant_context = await get_relevant_context(channel_id, current_message.content)
    
    structured_input = [
        {"role": "system", "content": f"You are {BOT_NAME}, an AI assistant in a conversation with multiple humans and other AI assistants on Discord. Respond naturally to messages."},
        {"role": "system", "content": "--- RAG Context Start ---"},
    ]
    
    for msg in relevant_context:
        speaker_type = "Human" if msg['role'] == "human" else "AI Assistant"
        structured_input.append({
            "role": "system",
            "content": f"[Message {msg['id']}]\nSpeaker: {msg['user']} (Type: {speaker_type})\nTime: {msg['timestamp']}\nReplying To: {msg['replying_to'] or 'None'}\nMessage: {msg['content']}"
        })
    
    structured_input.append({"role": "system", "content": "--- RAG Context End ---"})
    structured_input.append({"role": "system", "content": "--- Recent Messages Start ---"})
    
    for msg in history:
        speaker_type = "Human" if msg['role'] == "human" else "AI Assistant"
        structured_input.append({
            "role": "system",
            "content": f"[Message {msg['id']}]\nSpeaker: {msg['user']} (Type: {speaker_type})\nTime: {msg['timestamp']}\nReplying To: {msg['replying_to'] or 'None'}\nMessage: {msg['content']}"
        })
    
    structured_input.append({"role": "system", "content": "--- Recent Messages End ---"})
    structured_input.append({"role": "system", "content": "--- Task ---"})
    
    current_speaker_type = "Human" if not current_message.author.bot else "AI Assistant"
    structured_input.append({
        "role": "system",
        "content": f"Respond to: [Message {current_message.id}] Speaker: <@{current_message.author.id}> (Type: {current_speaker_type}) said: {current_message.content}"
    })
    
    return structured_input

async def process_message_queue(channel_id):
    global last_response_time
    current_time = time.time()

    if channel_id in message_queue and channel_id not in processing_channels:
        processing_channels.add(channel_id)
        try:
            while channel_id in message_queue:
                messages = message_queue.pop(channel_id)
                relevant_messages = [msg for msg in messages if bot.user.mentioned_in(msg) or 
                                     bot.user.name.lower() in msg.content.lower() or
                                     any(msg.author.name.upper() == other_bot for other_bot in OTHER_BOTS) or
                                     msg.reference and msg.reference.resolved and msg.reference.resolved.author == bot.user]
                
                if not relevant_messages:
                    logger.debug(f"No relevant messages found for channel {channel_id}")
                    continue

                for msg in relevant_messages:
                    structured_input = await get_structured_input(channel_id, msg)
                    
                    logger.debug(f"Constructed prompt for channel {channel_id}: {json.dumps(structured_input, indent=2)}")
                    
                    async with msg.channel.typing():
                        logger.debug(f"Requesting LLM response for channel {channel_id}")
                        response_content = await get_llm_response(structured_input)
                    
                    if response_content:
                        logger.debug(f"LLM response received: {response_content}")
                        
                        bot_message = {
                            "user_id": f"<@{bot.user.id}>",
                            "content": response_content,
                            "replying_to": f"<@{msg.author.id}>",
                            "role": "assistant"  # Ensure this is set to "assistant" for bot messages
                        }
                        
                        await record_chat_history(channel_id, bot_message)
                        await send_split_message(msg.channel, response_content)
                        last_response_time[channel_id] = time.time()
                    else:
                        logger.error(f"Failed to get a valid LLM response for channel {channel_id}")
                        await msg.reply(f"{BOT_NAME}: I apologize, but I'm having trouble formulating a complete response at the moment. Please try again later.")
                
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error processing message queue: {str(e)}", exc_info=True)
        finally:
            processing_channels.remove(channel_id)

async def health_check():
    while True:
        logger.info(f"{BOT_NAME} health check: Bot is running")
        await asyncio.sleep(300)  # Check every 5 minutes

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    bot.loop.create_task(health_check())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    # Record all user and other bot messages
    await record_user_message(message)
    
    should_process = (
        bot.user.mentioned_in(message) or 
        bot.user.name.lower() in message.content.lower() or
        message.author.bot or  # Process all bot messages
        (message.reference and message.reference.resolved and message.reference.resolved.author == bot.user) or
        random.random() < 0.1  # 10% chance to spontaneously join the conversation
    )
    
    if should_process:
        channel_id = str(message.channel.id)
        if channel_id not in message_queue:
            message_queue[channel_id] = []
            asyncio.create_task(process_message_queue(channel_id))
        message_queue[channel_id].append(message)
    
    await bot.process_commands(message)

async def record_user_message(message):
    channel_id = str(message.channel.id)
    
    # Determine the role based on whether the message is from another bot
    role = "user" if message.author.bot else "human"
    
    user_message = {
        "user_id": f"<@{message.author.id}>",
        "content": message.content,
        "replying_to": f"<@{message.reference.resolved.author.id}>" if message.reference and message.reference.resolved else None,
        "role": role
    }
    await record_chat_history(channel_id, user_message)

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.error(f"DISCORD_TOKEN_{BOT_NAME} not found in .env file")
    else:
        bot.run(DISCORD_TOKEN)