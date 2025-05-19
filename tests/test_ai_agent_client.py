# test_ai_agent_client.py
import asyncio
import websockets
import json

AGENT_ID = "test_agent_001"
SERVER_URL = f"ws://localhost:8000/ws/agent/{AGENT_ID}"

async def run_ai_agent_client():
    async with websockets.connect(SERVER_URL) as websocket:
        print(f"AI Agent client '{AGENT_ID}' connected to server.")

        # 1. 发送 REQUEST_SOFTWARE_LIST 消息
        request_list_message = {
            "type": "REQUEST_SOFTWARE_LIST"
        }
        await websocket.send(json.dumps(request_list_message))
        print(f"Sent REQUEST_SOFTWARE_LIST: {json.dumps(request_list_message)}")

        # 2. 等待服务器的软件列表响应
        response = await websocket.recv()
        print(f"Received from server: {response}")
        try:
            software_list_data = json.loads(response)
            if software_list_data.get("type") == "SOFTWARE_LIST_RESPONSE":
                print("Successfully received software list:")
                for sw in software_list_data.get("payload", []):
                    print(f"  - ID: {sw.get('software_id')}, Name: {sw.get('name')}")
            else:
                print(f"Received unexpected message type: {software_list_data.get('type')}")
        except json.JSONDecodeError:
            print(f"Failed to decode JSON response: {response}")


        # 可以在这里保持连接并进行其他操作
        try:
            while True:
                message_from_server = await websocket.recv() # 持续监听
                print(f"AI Agent received: {message_from_server}")
        except websockets.exceptions.ConnectionClosed:
            print(f"AI Agent client '{AGENT_ID}' connection closed.")
        except Exception as e:
            print(f"An error occurred in AI agent client: {e}")


if __name__ == "__main__":
    asyncio.run(run_ai_agent_client())