from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
import logging

app = FastAPI()

# Логгирование
logging.basicConfig(level=logging.INFO)

# Разрешаем CORS для всех доменов (во время разработки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Управление подключениями и хранением истории сообщений для каждой комнаты
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, List[WebSocket]] = {}
        self.chat_history: dict[str, List[str]] = {}  # История сообщений для каждой комнаты

    async def connect(self, websocket: WebSocket, chat_id: str):
        await websocket.accept()

        # Если комнаты еще нет, инициализируем её
        if chat_id not in self.active_connections:
            self.active_connections[chat_id] = []
            self.chat_history[chat_id] = []

        logging.info(f"New connection to chat {chat_id}. Current history: {self.chat_history[chat_id]}")

        # Отправляем историю сообщений при подключении нового пользователя
        if self.chat_history[chat_id]:
            logging.info(f"Sending chat history to new user in chat {chat_id}")
            for message in self.chat_history[chat_id]:
                await websocket.send_text(message)

        # Добавляем нового клиента в список активных подключений
        self.active_connections[chat_id].append(websocket)
        logging.info(f"User connected to chat {chat_id}. Active users: {len(self.active_connections[chat_id])}")

    def disconnect(self, websocket: WebSocket, chat_id: str):
        self.active_connections[chat_id].remove(websocket)
        if not self.active_connections[chat_id]:
            del self.active_connections[chat_id]
        logging.info(f"User disconnected from chat {chat_id}. Remaining users: {len(self.active_connections.get(chat_id, []))}")

    async def broadcast(self, message: str, chat_id: str):
        # Сохраняем сообщение в историю
        self.chat_history[chat_id].append(message)
        logging.info(f"New message in chat {chat_id}: {message}. Total messages: {len(self.chat_history[chat_id])}")

        # Рассылаем сообщение всем активным участникам комнаты
        for connection in self.active_connections.get(chat_id, []):
            await connection.send_text(message)
        logging.info(f"Message broadcasted to {len(self.active_connections[chat_id])} users in chat {chat_id}")

manager = ConnectionManager()

# WebSocket эндпоинт для разных чатов
@app.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    await manager.connect(websocket, chat_id)
    try:
        while True:
            # Ожидание получения JSON-объекта с текстом и username
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Формируем строку для отправки (username: message)
            # Формируем объект для отправки в формате JSON
            message_to_send = json.dumps({
                'username': message_data['username'],
                'message': message_data['message']
            })

            # Рассылаем сообщение всем участникам комнаты и сохраняем его в историю
            await manager.broadcast(message_to_send, chat_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, chat_id)
