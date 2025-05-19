# ai_agent/websocket_client.py
import asyncio
import websockets
import json
from typing import Callable, Any, Optional, Dict
from websockets.protocol import State # 导入 State
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK # 导入异常

from . import agent_config # 导入配置

class AgentWebsocketClient:
    def __init__(self, agent_id: str, server_url_template: str, on_message_callback: Callable):
        self.agent_id = agent_id
        self.server_url = server_url_template.format(client_type="agent", client_id=self.agent_id)
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.on_message_callback = on_message_callback
        self._is_running = False
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.server_url)
            self._is_running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            print(f"AI Agent '{self.agent_id}' connected to intermediary server at {self.server_url}")
            return True
        except Exception as e:
            print(f"Failed to connect AI Agent to server: {e}")
            self.websocket = None
            return False

    async def _receive_loop(self):
        if not self.websocket:
            return
        try:
            async for message_str in self.websocket:
                try:
                    message_data = json.loads(message_str)
                    await self.on_message_callback(message_data)
                except json.JSONDecodeError:
                    print(f"Error: Received non-JSON message from server: {message_str}")
                except Exception as e:
                    print(f"Error processing message from server: {e}")
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
            print(f"Connection to server closed: {type(e).__name__} - {e}")
        except asyncio.CancelledError:
            print("Receive loop was cancelled.")
        except Exception as e:
            print(f"Error in receive loop: {type(e).__name__} - {e}")
        finally:
            self._is_running = False
            # 在 finally 块中再次检查 websocket 对象是否存在且未关闭
            if self.websocket and self.websocket.state != State.CLOSED:
                try:
                    await self.websocket.close()
                except Exception as e:
                    print(f"Error during websocket close in receive_loop finally: {e}")
            self.websocket = None # 清理websocket对象

    async def send_message(self, message: Dict[str, Any]):
        if self.websocket and self.websocket.state == State.OPEN:
            try:
                await self.websocket.send(json.dumps(message))
            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as e:
                print(f"Cannot send message: Connection closed ({type(e).__name__} - {e}). Attempting to disconnect.")
                await self.disconnect() # 尝试优雅断开并清理
            except Exception as e:
                print(f"Error sending message: {e}")
        else:
            print("Cannot send message: WebSocket is not connected or not open.")

    async def disconnect(self):
        print("Attempting to disconnect AI Agent...")
        self._is_running = False # 首先设置运行状态为False

        if self._receive_task and not self._receive_task.done():
            print("Cancelling receive loop task...")
            self._receive_task.cancel()
            try:
                await self._receive_task
                print("Receive loop task successfully awaited after cancellation.")
            except asyncio.CancelledError:
                print("Receive loop task was indeed cancelled.")
            except Exception as e:
                print(f"Exception during receive_task await in disconnect: {type(e).__name__} - {e}")
        elif self._receive_task and self._receive_task.done():
            print("Receive loop task was already done.")


        if self.websocket:
            if self.websocket.state != State.CLOSED:
                print(f"Closing WebSocket connection (current state: {self.websocket.state})...")
                try:
                    await self.websocket.close()
                    print("AI Agent WebSocket connection closed successfully.")
                except Exception as e:
                    print(f"Error during websocket close in disconnect: {type(e).__name__} - {e}")
            else:
                 print("AI Agent WebSocket already closed.")
        else:
            print("No active WebSocket connection to close.")

        self.websocket = None # 确保清理
        print("AI Agent disconnected.")


    def is_connected(self) -> bool:
        return self.websocket is not None and self.websocket.state == State.OPEN and self._is_running