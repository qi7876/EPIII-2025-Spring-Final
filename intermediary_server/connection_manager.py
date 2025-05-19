# intermediary_server/connection_manager.py
from typing import Dict, List, Optional
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # software_id -> WebSocket
        self.active_software_connections: Dict[str, WebSocket] = {}
        # client_id (e.g., websocket.client.id) -> WebSocket
        self.active_agent_connections: Dict[str, WebSocket] = {} # 使用WebSocket对象本身或其唯一标识符作为key

    async def connect_software(self, websocket: WebSocket, software_id: str):
        await websocket.accept()
        self.active_software_connections[software_id] = websocket
        print(f"Software client '{software_id}' connected.")

    def disconnect_software(self, software_id: str):
        if software_id in self.active_software_connections:
            # WebSocket 对象可能已经关闭，这里主要是清理字典
            del self.active_software_connections[software_id]
            print(f"Software client '{software_id}' disconnected.")

    async def connect_agent(self, websocket: WebSocket, agent_id: str = "default_agent"):
        await websocket.accept()
        # agent_id 可以通过握手消息获取，或者简单地使用websocket对象本身或其哈希
        # 为了简单，我们先用一个 agent_id (未来可以扩展)
        # 或者直接用 websocket 对象作为 key 如果不需要持久化 agent_id
        client_key = f"{websocket.client.host}:{websocket.client.port}" # 示例key
        self.active_agent_connections[client_key] = websocket
        print(f"AI Agent client '{client_key}' connected.")

    def disconnect_agent(self, websocket: WebSocket):
        client_key = f"{websocket.client.host}:{websocket.client.port}"
        if client_key in self.active_agent_connections:
            del self.active_agent_connections[client_key]
            print(f"AI Agent client '{client_key}' disconnected.")

    async def send_to_software(self, software_id: str, message: dict):
        websocket = self.active_software_connections.get(software_id)
        if websocket:
            await websocket.send_json(message)
        else:
            print(f"Error: Software client '{software_id}' not found or not connected.")

    async def send_to_agent(self, websocket: WebSocket, message: dict): # 或者 agent_id
        # client_key = f"{websocket.client.host}:{websocket.client.port}"
        # target_websocket = self.active_agent_connections.get(client_key)
        # if target_websocket: # 确保websocket仍然在连接池中
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending message to agent {websocket.client}: {e}")
            # 可能需要从连接池中移除
            # self.disconnect_agent(websocket)


    async def broadcast_to_agents(self, message: dict):
        for ws in self.active_agent_connections.values():
            try:
                await ws.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to agent {ws.client}: {e}")
                # 可能需要从连接池中移除


# 单例模式
connection_manager_instance = ConnectionManager()