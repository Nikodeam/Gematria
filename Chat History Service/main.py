from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
import json
import uuid
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import aiohttp

app = FastAPI()

# LM Studio configuration
LM_STUDIO_URL = "http://localhost:1234"
MODEL_ID_EMBEDDING = "embed"
HEADERS = {"Content-Type": "application/json"}

# Database setup
conn = sqlite3.connect('chat_history.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS messages
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              channel_id TEXT,
              user_id TEXT,
              timestamp TEXT,
              replying_to TEXT,
              content TEXT,
              embedding TEXT,
              role TEXT)''')
conn.commit()

class Message(BaseModel):
    channel_id: str
    user_id: str  # This will be the full Discord ID format, e.g., "<@1234567890>"
    content: str
    replying_to: Optional[str] = None  # This will also be the full Discord ID format, e.g., "<@1234567890>"
    role: str  # Add this field

async def get_embedding(text):
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{LM_STUDIO_URL}/v1/embeddings", headers=HEADERS, json={
            "model": MODEL_ID_EMBEDDING,
            "input": text
        }) as response:
            if response.status == 200:
                data = await response.json()
                return data['data'][0]['embedding']
    return None

# Remove get_summary function

@app.post("/add_message")
async def add_message(message: Message):
    timestamp = datetime.utcnow().isoformat()
    embedding = await get_embedding(message.content)
    
    c.execute('''INSERT INTO messages 
                 (channel_id, user_id, timestamp, replying_to, content, embedding, role)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (message.channel_id, message.user_id, timestamp, message.replying_to,
               message.content, json.dumps(embedding), message.role))
    conn.commit()
    
    return {"status": "success", "message_id": c.lastrowid}

@app.get("/get_conversation_history/{channel_id}")
async def get_conversation_history(channel_id: str, limit: int = 10):
    c.execute('''SELECT id, user_id, timestamp, replying_to, content, role
                 FROM messages WHERE channel_id = ? 
                 ORDER BY timestamp DESC LIMIT ?''', (channel_id, limit))
    messages = c.fetchall()
    
    return [{"id": msg[0], "user": msg[1], "timestamp": msg[2], "replying_to": msg[3],
             "content": msg[4], "role": msg[5]} for msg in reversed(messages)]

@app.get("/get_relevant_context/{channel_id}")
async def get_relevant_context(channel_id: str, query: str, limit: int = 5):
    query_embedding = await get_embedding(query)
    
    c.execute("SELECT * FROM messages WHERE channel_id = ?", (channel_id,))
    messages = c.fetchall()
    
    if not messages:
        return []
    
    embeddings = [np.array(json.loads(msg[6])) for msg in messages]
    similarities = cosine_similarity([query_embedding], embeddings)[0]
    
    top_indices = np.argsort(similarities)[-limit:][::-1]
    relevant_messages = [messages[i] for i in top_indices]
    
    return [{"id": msg[0], "user": msg[2], "timestamp": msg[3], "replying_to": msg[4],
             "content": msg[5], "role": msg[7]} for msg in relevant_messages]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="192.168.178.117", port=8000)