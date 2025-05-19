# intermediary_server/server.py
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from .connection_manager import connection_manager_instance as conn_manager
from .software_registry import software_registry_instance as sw_registry
from .message_models import (
    BaseMessage, GenericMessage,
    IdentifySoftwareMessage, IdentifyAgentMessage, SoftwareInfo,
    RequestSoftwareListMessage, SoftwareListResponseMessage, RegistrationAckMessage,
    RequestSoftwareCapabilitiesMessage, SoftwareCapabilitiesResponseMessage,
    ExecuteSolutionPlanMessage, ActionStatusUpdateMessage,
    FormRequestMessage, FormDataResponseMessage
)

app = FastAPI(title="AI Agent Control Intermediary Server")

@app.websocket("/ws/{client_type}/{client_id}") # client_type: "software" or "agent"
async def websocket_endpoint(websocket: WebSocket, client_type: str, client_id: str):
    if client_type == "software":
        # 对于软件客户端，client_id 就是 software_id
        await conn_manager.connect_software(websocket, client_id)
        # 软件连接后，应该立即发送其信息进行注册
        # 或者，我们可以在这里等待一个 IDENTIFY_SOFTWARE 消息
        # 为了简化，我们假设 software_id 在URL中提供，并且软件连接后会主动发送注册信息
        print(f"Software client '{client_id}' awaiting registration info via message.")
    elif client_type == "agent":
        # 对于AI代理，client_id 可以是一个唯一标识符，或者暂时用 "default"
        await conn_manager.connect_agent(websocket, client_id)
        print(f"AI Agent client '{client_id}' connected.")
    else:
        print(f"Unknown client type '{client_type}'. Closing connection.")
        await websocket.close(code=4001) # 自定义关闭码
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
                # 首先尝试解析为 GenericMessage 来获取 type
                generic_msg = GenericMessage.model_validate(message_data)
                print(f"Received message of type: {generic_msg.type} from {client_type} '{client_id}'")

                # --- 根据客户端类型和消息类型处理 ---
                if client_type == "software":
                    if generic_msg.type == IdentifySoftwareMessage.model_fields['type'].default: # "IDENTIFY_SOFTWARE"
                        try:
                            id_msg = IdentifySoftwareMessage.model_validate(message_data)
                            # 确保URL中的client_id与消息中的software_id一致
                            if id_msg.payload.software_id != client_id:
                                print(f"Warning: URL client_id '{client_id}' differs from payload software_id '{id_msg.payload.software_id}'. Using payload.")
                                # 如果不一致，可能需要断开或以payload为准，这里我们以payload为准并更新连接管理器的key
                                conn_manager.disconnect_software(client_id) #移除旧key（如果存在）
                                actual_software_id = id_msg.payload.software_id
                                await conn_manager.connect_software(websocket, actual_software_id) #用新的ID重新关联
                            else:
                                actual_software_id = client_id

                            sw_registry.register_software(id_msg.payload)
                            ack_msg = RegistrationAckMessage()
                            await websocket.send_json(ack_msg.model_dump())
                            print(f"Software '{actual_software_id}' identified and registered.")
                        except ValidationError as e:
                            print(f"Validation Error for IDENTIFY_SOFTWARE: {e}")
                            await websocket.send_json({"error": "Invalid IDENTIFY_SOFTWARE format", "details": e.errors()})

                    elif generic_msg.type == SoftwareCapabilitiesResponseMessage.model_fields['type'].default: # "SOFTWARE_CAPABILITIES_RESPONSE"
                        try:
                            cap_resp_msg = SoftwareCapabilitiesResponseMessage.model_validate(message_data)
                            # 转发给请求这个能力的AI代理 (这里需要更复杂的逻辑来追踪请求者)
                            # 简化：暂时假设只有一个AI代理或广播
                            print(f"Received capabilities from {cap_resp_msg.software_id}. Broadcasting to agents.")
                            await conn_manager.broadcast_to_agents(cap_resp_msg.model_dump())
                        except ValidationError as e:
                            print(f"Validation Error for SOFTWARE_CAPABILITIES_RESPONSE: {e}")

                    elif generic_msg.type == ActionStatusUpdateMessage.model_fields['type'].default: # "ACTION_STATUS_UPDATE"
                        try:
                            status_update_msg = ActionStatusUpdateMessage.model_validate(message_data)
                            print(f"Received action status from {status_update_msg.payload.get('software_id')}. Broadcasting to agents.")
                            await conn_manager.broadcast_to_agents(status_update_msg.model_dump())
                        except ValidationError as e:
                            print(f"Validation Error for ACTION_STATUS_UPDATE: {e}")

                    elif generic_msg.type == FormRequestMessage.model_fields['type'].default: # "FORM_REQUEST"
                        try:
                            form_req_msg = FormRequestMessage.model_validate(message_data)
                            print(f"Received form request from {form_req_msg.payload.software_id}. Broadcasting to agents.")
                            await conn_manager.broadcast_to_agents(form_req_msg.model_dump())
                        except ValidationError as e:
                            print(f"Validation Error for FORM_REQUEST: {e}")
                    else:
                        print(f"Software client '{client_id}' sent unhandled message type: {generic_msg.type}")


                elif client_type == "agent":
                    if generic_msg.type == RequestSoftwareListMessage.model_fields['type'].default: # "REQUEST_SOFTWARE_LIST"
                        softwares = sw_registry.list_all_software()
                        response_msg = SoftwareListResponseMessage(payload=softwares)
                        await conn_manager.send_to_agent(websocket, response_msg.model_dump())
                        print(f"Sent software list to agent '{client_id}'.")

                    elif generic_msg.type == RequestSoftwareCapabilitiesMessage.model_fields['type'].default: # "REQUEST_SOFTWARE_CAPABILITIES"
                        try:
                            req_cap_msg = RequestSoftwareCapabilitiesMessage.model_validate(message_data)
                            target_software_id = req_cap_msg.payload.get("software_id")
                            if target_software_id:
                                print(f"Agent '{client_id}' requesting capabilities for software '{target_software_id}'. Forwarding...")
                                await conn_manager.send_to_software(target_software_id, req_cap_msg.model_dump())
                            else:
                                await websocket.send_json({"error": "software_id missing in REQUEST_SOFTWARE_CAPABILITIES payload"})
                        except ValidationError as e:
                            print(f"Validation Error for REQUEST_SOFTWARE_CAPABILITIES: {e}")

                    elif generic_msg.type == ExecuteSolutionPlanMessage.model_fields['type'].default: # "EXECUTE_SOLUTION_PLAN"
                        try:
                            exec_plan_msg = ExecuteSolutionPlanMessage.model_validate(message_data)
                            target_software_id = exec_plan_msg.payload.get("software_id")
                            if target_software_id:
                                print(f"Agent '{client_id}' sending solution plan to software '{target_software_id}'. Forwarding...")
                                # 从payload中提取真正的消息体转发
                                await conn_manager.send_to_software(target_software_id, exec_plan_msg.model_dump())
                            else:
                                await websocket.send_json({"error": "software_id missing in EXECUTE_SOLUTION_PLAN payload"})
                        except ValidationError as e:
                            print(f"Validation Error for EXECUTE_SOLUTION_PLAN: {e}")

                    elif generic_msg.type == FormDataResponseMessage.model_fields['type'].default: # "FORM_DATA_RESPONSE"
                        try:
                            form_data_msg = FormDataResponseMessage.model_validate(message_data)
                            target_software_id = form_data_msg.payload.software_id
                            if target_software_id:
                                print(f"Agent '{client_id}' sending form data to software '{target_software_id}'. Forwarding...")
                                await conn_manager.send_to_software(target_software_id, form_data_msg.model_dump())
                            else:
                                await websocket.send_json({"error": "software_id missing in FORM_DATA_RESPONSE payload"})
                        except ValidationError as e:
                            print(f"Validation Error for FORM_DATA_RESPONSE: {e}")
                    else:
                        print(f"AI Agent client '{client_id}' sent unhandled message type: {generic_msg.type}")

            except ValidationError as e:
                print(f"Pydantic Validation Error: {e.errors()}")
                await websocket.send_json({"error": "Invalid message format", "details": e.errors()})
            except json.JSONDecodeError:
                print("Error: Received non-JSON message")
                await websocket.send_json({"error": "Invalid JSON format"})
            except Exception as e:
                print(f"An unexpected error occurred with {client_type} '{client_id}': {e}")
                # Consider breaking loop or specific error handling
                break # Break on general errors to prevent tight loops on bad state

    except WebSocketDisconnect:
        print(f"Client {client_type} '{client_id}' disconnected.")
    finally:
        if client_type == "software":
            conn_manager.disconnect_software(client_id)
            sw_registry.unregister_software(client_id) # 软件断开连接时也从注册表中移除
        elif client_type == "agent":
            conn_manager.disconnect_agent(websocket)

@app.get("/")
async def read_root():
    return {"message": "AI Agent Control Intermediary Server is running."}

# 如果你想直接运行这个文件 (例如 python server.py)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)