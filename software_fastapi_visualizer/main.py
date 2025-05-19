# software_fastapi_visualizer/main.py
import asyncio
import websockets  # For connecting to intermediary_server
import json
from typing import Set, Optional, Tuple, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketState

try:
    from . import client_config as cfg
except ImportError:

    class cfg:  # Fallback config
        SOFTWARE_ID = "choutuan_clone_visual_fastapi_v1"
        SOFTWARE_NAME = "丑团"
        SOFTWARE_DESCRIPTION = (
            "一个提供外卖、酒店等服务的FastAPI可视化综合应用，由AI控制。"
        )
        SOFTWARE_KEYWORDS = ["可视化外卖FastAPI", "AI控制酒店FastAPI"]
        INTERMEDIARY_SERVER_WS_URL = "ws://localhost:8000/ws/software/"


app = FastAPI(title=cfg.SOFTWARE_NAME)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Global Application State ---
current_view_name: str = "homepage"
cart_items: list = []
pending_item_for_form: Optional[Dict[str, Any]] = (
    None  # Context for a form requested by AI/action OR by this software for AI
)
gui_ws_connections: Set[WebSocket] = set()
text_input_values: Dict[str, str] = {}


class IntermediaryConnection:
    ws: Optional[websockets.WebSocketClientProtocol] = None


intermediary_conn = IntermediaryConnection()


# --- Capability Definitions ---
def get_capabilities_for_view(view_name: str) -> dict:
    global cart_items, pending_item_for_form, text_input_values
    if view_name == "homepage":
        return {
            "current_view": "homepage",
            "elements": [
                {
                    "id": "hp_waimai_button",
                    "type": "button",
                    "label": "外卖",
                    "description": "点击进入外卖频道",
                },
                {
                    "id": "hp_hotel_button",
                    "type": "button",
                    "label": "酒店",
                    "description": "点击进入酒店预订",
                },
                {
                    "id": "hp_movie_button",
                    "type": "button",
                    "label": "电影",
                    "description": "点击查看电影票",
                },
            ],
        }
    elif view_name == "waimai_page":
        return {
            "current_view": "waimai_page",
            "elements": [
                {
                    "id": "wm_search_food_input",
                    "type": "text_input",
                    "label": "搜索想吃的",
                    "description": "输入食物名称进行搜索",
                    "current_value": text_input_values.get("wm_search_food_input", ""),
                },
                {
                    "id": "wm_search_food_button",
                    "type": "button",
                    "label": "搜索美食",
                    "description": "点击开始搜索食物",
                },
                {
                    "id": "wm_food_list_item_1",
                    "type": "list_item",
                    "label": "北京烤鸭 (示例)",
                    "description": "选择北京烤鸭",
                },
                {
                    "id": "wm_food_list_item_2",
                    "type": "list_item",
                    "label": "宫保鸡丁 (示例)",
                    "description": "选择宫保鸡丁",
                },
                {
                    "id": "wm_view_cart_button",
                    "type": "button",
                    "label": f"查看购物车 ({len(cart_items)}件)",
                    "description": "点击查看当前购物车中的商品",
                },
                {
                    "id": "wm_back_to_home_button",
                    "type": "button",
                    "label": "返回首页",
                    "description": "点击返回应用首页",
                },
            ],
        }
    elif view_name == "food_details_page":
        item_name_context = (
            pending_item_for_form["name"] if pending_item_for_form else "商品"
        )
        return {
            "current_view": "food_details_page",
            "item_context": item_name_context,
            "elements": [
                {
                    "id": "fd_select_taste_button",
                    "type": "button",
                    "label": f"选择{item_name_context}规格",
                    "description": "点击选择商品口味和数量",
                },
                {
                    "id": "fd_add_to_cart_button",
                    "type": "button",
                    "label": "加入购物车",
                    "description": "将当前商品（需先选规格）加入购物车",
                },
                {
                    "id": "fd_back_to_waimai_button",
                    "type": "button",
                    "label": "返回外卖列表",
                    "description": "点击返回外卖列表页",
                },
            ],
        }
    elif view_name == "cart_page":
        cart_summary = ", ".join(
            [
                f"{item['name']}({item.get('taste', '默认')})x{item.get('quantity', 1)}"
                for item in cart_items
            ]
        )
        cart_summary = cart_summary if cart_summary else "购物车是空的"
        elements = [
            {
                "id": "cp_item_summary",
                "type": "label",
                "label": f"购物车: {cart_summary}",
                "description": "当前购物车商品",
            },
            {
                "id": "cp_continue_shopping_button",
                "type": "button",
                "label": "继续点餐",
                "description": "返回外卖列表",
            },
        ]
        if cart_items:
            elements.append(
                {
                    "id": "cp_proceed_to_checkout_button",
                    "type": "button",
                    "label": "去结算",
                    "description": "进入订单确认页",
                }
            )
        return {"current_view": "cart_page", "elements": elements}
    elif view_name == "checkout_page":
        return {
            "current_view": "checkout_page",
            "elements": [
                {
                    "id": "co_address_field",
                    "type": "text_input",
                    "label": "配送地址",
                    "description": "输入配送地址",
                    "current_value": text_input_values.get("co_address_field", ""),
                },
                {
                    "id": "co_phone_field",
                    "type": "text_input",
                    "label": "联系电话",
                    "description": "输入联系电话",
                    "current_value": text_input_values.get("co_phone_field", ""),
                },
                {
                    "id": "co_confirm_order_button",
                    "type": "button",
                    "label": "确认下单",
                    "description": "最终提交订单",
                },
                {
                    "id": "co_back_to_cart_button",
                    "type": "button",
                    "label": "返回购物车",
                    "description": "返回修改购物车",
                },
            ],
        }
    elif view_name == "order_success_page":
        return {
            "current_view": "order_success_page",
            "elements": [
                {
                    "id": "os_message_label",
                    "type": "label",
                    "label": "订单提交成功！",
                    "description": "订单成功信息",
                },
                {
                    "id": "os_back_to_home_button",
                    "type": "button",
                    "label": "返回首页",
                    "description": "点击返回应用首页",
                },
            ],
        }
    else:
        return {
            "current_view": view_name if view_name else "unknown_page",
            "elements": [
                {
                    "id": "err_label",
                    "type": "label",
                    "label": f"页面 {view_name} 未定义能力",
                    "description": "",
                }
            ],
        }


# --- Helper: Perform Action and Update State ---
def _perform_action_and_update_state(
    command: str, element_id: str, text_to_type: Optional[str] = None
) -> Tuple[bool, bool, Optional[Dict[str, Any]], str]:
    global current_view_name, cart_items, pending_item_for_form, text_input_values
    action_successful = True
    should_send_form_request = False
    form_request_payload = None
    action_description = f"{command} on {element_id}"
    print(
        f"  StateUpdater: Processing {command} on '{element_id}'"
        + (f" with text '{text_to_type}'" if text_to_type else "")
    )

    if command == "CLICK":
        action_description = f"Clicked '{element_id}'"
        if element_id == "hp_waimai_button":
            current_view_name = "waimai_page"
        elif element_id == "wm_search_food_button":
            search_term = text_input_values.get("wm_search_food_input", "")
            action_description = f"Clicked search button for term: '{search_term}'"
            print(
                f"    StateUpdater: Search initiated for '{search_term}'. (Demo: No actual search)"
            )
        elif element_id == "wm_food_list_item_1":
            current_view_name = "food_details_page"
            pending_item_for_form = {"name": "北京烤鸭", "id": "wm_food_list_item_1"}
        elif element_id == "wm_food_list_item_2":
            current_view_name = "food_details_page"
            pending_item_for_form = {"name": "宫保鸡丁", "id": "wm_food_list_item_2"}
        elif element_id == "fd_select_taste_button":
            if pending_item_for_form:
                form_desc = f"请选择 {pending_item_for_form['name']} 的口味和数量"
                form_request_payload = {
                    "software_id": cfg.SOFTWARE_ID,
                    "form_description": form_desc,
                    "item_context": pending_item_for_form,
                    "fields": [
                        {
                            "id": "taste",
                            "label": "口味",
                            "type": "select",
                            "options": ["原味", "微辣", "麻辣"],
                        },
                        {
                            "id": "quantity",
                            "label": "数量",
                            "type": "number",
                            "default": 1,
                            "min": 1,
                        },
                    ],
                }
                should_send_form_request = True
                action_description = f"Clicked '{element_id}', requesting form for {pending_item_for_form['name']}"
            else:
                action_successful = False
                action_description = "Error: Clicked select taste with no pending item."
        elif element_id == "fd_add_to_cart_button":
            if (
                pending_item_for_form
                and pending_item_for_form.get("taste")
                and pending_item_for_form.get("quantity")
            ):
                cart_items.append(pending_item_for_form.copy())
                action_description = f"Added {pending_item_for_form['name']} to cart. Cart items: {len(cart_items)}"
                pending_item_for_form = None
                current_view_name = "cart_page"
            else:
                action_successful = False
                action_description = (
                    "Error: Tried to add to cart, but taste/quantity not selected."
                )
        elif (
            element_id == "wm_view_cart_button"
            or element_id == "co_back_to_cart_button"
        ):
            current_view_name = "cart_page"
        elif element_id == "cp_proceed_to_checkout_button":
            current_view_name = "checkout_page"
        elif element_id == "co_confirm_order_button":
            address = text_input_values.get("co_address_field", "")
            phone = text_input_values.get("co_phone_field", "")
            if not cart_items:
                action_successful = False
                action_description = "Error: Cart is empty."
            elif not address or not phone:
                action_successful = False
                action_description = "Error: Address or phone is missing for checkout."
            else:
                action_description = f"Order placed for {json.dumps(cart_items, ensure_ascii=False)} to address '{address}', phone '{phone}'"
                print(f"    SIMULATED ORDER: {action_description}")
                cart_items = []
                text_input_values.pop("co_address_field", None)
                text_input_values.pop("co_phone_field", None)
                current_view_name = "order_success_page"
        elif element_id in ["wm_back_to_home_button", "os_back_to_home_button"]:
            current_view_name = "homepage"
        elif element_id == "cp_continue_shopping_button":
            current_view_name = "waimai_page"
        elif element_id == "fd_back_to_waimai_button":
            current_view_name = "waimai_page"
        else:
            print(
                f"    StateUpdater Warning: Unhandled CLICK on '{element_id}' in '{current_view_name}'."
            )
    elif command == "TYPE_TEXT":
        action_description = f"AI typed '{text_to_type}' into '{element_id}'"
        text_input_values[element_id] = text_to_type
        print(f"    StateUpdater (AI): '{text_to_type}' stored for '{element_id}'.")
    else:
        action_successful = False
        action_description = f"Error: Unknown command '{command}'"
        print(f"    StateUpdater Error: Unknown command '{command}'")
    print(
        f"  StateUpdater: New view '{current_view_name}', Cart items: {len(cart_items)}, Inputs: {text_input_values}"
    )
    return (
        action_successful,
        should_send_form_request,
        form_request_payload,
        action_description,
    )


# --- WebSocket Communication with GUI ---
async def broadcast_to_gui(message: dict):
    send_tasks = []
    for ws in list(gui_ws_connections):
        if ws.client_state == WebSocketState.CONNECTED:
            send_tasks.append(ws.send_json(message))
        else:
            gui_ws_connections.remove(ws)
    if send_tasks:
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                print(f"Error broadcasting to GUI: {result}")


@app.websocket("/ws_gui")
async def websocket_gui_endpoint(websocket: WebSocket):
    await websocket.accept()
    gui_ws_connections.add(websocket)
    print(f"GUI client connected: {websocket.client}. Total: {len(gui_ws_connections)}")
    try:
        await websocket.send_json(
            {
                "type": "INIT_DATA",
                "software_id": cfg.SOFTWARE_ID,
                "software_name": cfg.SOFTWARE_NAME,
            }
        )
        await websocket.send_json(
            {
                "type": "UPDATE_CAPABILITIES",
                "payload": get_capabilities_for_view(current_view_name),
            }
        )
        while True:
            data_str = await websocket.receive_text()
            print(f"Received from GUI client {websocket.client}: {data_str}")
            try:
                data = json.loads(data_str)
                if data.get("type") == "USER_ACTION":
                    await handle_user_action_from_gui(data.get("payload"))
                elif data.get("type") == "USER_INPUT_CHANGE":
                    await handle_user_input_change(data.get("payload"))
                elif data.get("type") == "USER_FILLED_FORM_DATA":
                    await handle_user_filled_form_data(data.get("payload"))
                else:
                    print(f"Unknown message type from GUI: {data.get('type')}")
            except Exception as e_proc:
                print(f"Error processing message from GUI: {e_proc}")
    except WebSocketDisconnect:
        print(f"GUI client disconnected: {websocket.client}")
    except Exception as e:
        print(f"Error with GUI WS {websocket.client}: {type(e).__name__} - {e}")
    finally:
        if websocket in gui_ws_connections:
            gui_ws_connections.remove(websocket)
        print(f"GUI client removed. Total: {len(gui_ws_connections)}")


async def handle_user_input_change(payload: dict):
    global text_input_values
    element_id = payload.get("element_id")
    value = payload.get("value")
    element_type = payload.get("element_type")
    print(
        f"Processing USER_INPUT_CHANGE: Element '{element_id}' (type: {element_type}) new value: '{value}'"
    )
    if element_type == "text_input":
        text_input_values[element_id] = value
        print(f"  Stored user input for '{element_id}': '{value}'")
    else:
        print(
            f"  Warning: Unhandled element_type '{element_type}' for USER_INPUT_CHANGE."
        )
        return
    new_capabilities = get_capabilities_for_view(current_view_name)
    await broadcast_to_gui({"type": "UPDATE_CAPABILITIES", "payload": new_capabilities})
    if (
        intermediary_conn.ws
        and intermediary_conn.ws.state == websockets.protocol.State.OPEN
    ):
        status_update_payload = {
            "software_id": cfg.SOFTWARE_ID,
            "status": "USER_MODIFIED_STATE",
            "message": f"User input value for '{element_id}' to '{value}'.",
            "changed_element": {"id": element_id, "value": value, "type": element_type},
            "current_capabilities": new_capabilities,
        }
        await intermediary_conn.ws.send(
            json.dumps(
                {"type": "ACTION_STATUS_UPDATE", "payload": status_update_payload}
            )
        )
        print(
            f"--> Sent ACTION_STATUS_UPDATE (USER_MODIFIED_STATE) to intermediary for '{element_id}'."
        )
    else:
        print(
            "Cannot send USER_MODIFIED_STATE to intermediary: WS not connected or not open."
        )


async def handle_user_action_from_gui(action_payload: dict):
    command = action_payload.get("command")
    element_id = action_payload.get("element_id")
    print(f"Processing USER_ACTION: {command} on {element_id}")
    await broadcast_to_gui(
        {"type": "EXECUTE_ACTION_VISUALIZATION", "payload": action_payload}
    )
    success, send_form, form_payload, action_desc_status = (
        _perform_action_and_update_state(command, element_id)
    )
    new_capabilities = get_capabilities_for_view(current_view_name)
    await broadcast_to_gui({"type": "UPDATE_CAPABILITIES", "payload": new_capabilities})
    if (
        intermediary_conn.ws
        and intermediary_conn.ws.state == websockets.protocol.State.OPEN
    ):
        if send_form and form_payload:
            await intermediary_conn.ws.send(
                json.dumps({"type": "FORM_REQUEST", "payload": form_payload})
            )
            print(f"--> Sent FORM_REQUEST to intermediary (user triggered).")
            await broadcast_to_gui(
                {
                    "type": "LOG_MESSAGE",
                    "message": f"User action triggered FORM_REQUEST for {pending_item_for_form['name'] if pending_item_for_form else 'item'}.",
                }
            )
        else:
            status_to_send = "SUCCESS" if success else "FAILURE"
            if current_view_name == "order_success_page" and success:
                status_to_send = "TASK_COMPLETED_BY_SOFTWARE"
            status_update_payload = {
                "software_id": cfg.SOFTWARE_ID,
                "status": status_to_send,
                "message": f"User action: {action_desc_status}",
                "current_capabilities": new_capabilities,
            }
            await intermediary_conn.ws.send(
                json.dumps(
                    {"type": "ACTION_STATUS_UPDATE", "payload": status_update_payload}
                )
            )
            print(
                f"--> Sent ACTION_STATUS_UPDATE to intermediary (user triggered). Status: {status_to_send}"
            )
    else:
        print("Cannot send update to intermediary: WS not connected or not open.")
        await broadcast_to_gui(
            {
                "type": "LOG_MESSAGE",
                "message": "Error: Cannot sync user action with AI system.",
            }
        )


async def handle_user_filled_form_data(form_data_payload_from_gui: dict):  # NEW
    global pending_item_for_form
    print(f"Processing USER_FILLED_FORM_DATA: {form_data_payload_from_gui}")
    form_data = form_data_payload_from_gui.get("form_data")
    item_context_from_gui = form_data_payload_from_gui.get("item_context")
    if not form_data:
        print("Error: USER_FILLED_FORM_DATA missing 'form_data'.")
        await broadcast_to_gui(
            {
                "type": "LOG_MESSAGE",
                "message": "[ERROR] Invalid form submission from GUI.",
            }
        )
        return

    current_pending_item_name = "Unknown Item"
    if (
        pending_item_for_form
        and item_context_from_gui
        and pending_item_for_form.get("id") == item_context_from_gui.get("id")
    ):
        pending_item_for_form["taste"] = form_data.get("taste")
        pending_item_for_form["quantity"] = int(form_data.get("quantity", 1))
        current_pending_item_name = pending_item_for_form["name"]
        print(
            f"  Updated pending item '{current_pending_item_name}' with GUI user specs: {form_data}"
        )
    elif item_context_from_gui:
        pending_item_for_form = item_context_from_gui
        pending_item_for_form["taste"] = form_data.get("taste")
        pending_item_for_form["quantity"] = int(form_data.get("quantity", 1))
        current_pending_item_name = pending_item_for_form.get(
            "name", "Item from GUI context"
        )
        print(
            f"  Set/Updated pending item based on GUI context to '{current_pending_item_name}' with specs: {form_data}"
        )
    else:
        print(
            "Warning: Could not fully update pending_item_for_form from GUI form data due to missing context."
        )

    if (
        intermediary_conn.ws
        and intermediary_conn.ws.state == websockets.protocol.State.OPEN
    ):
        form_data_response_to_ai = {
            "type": "FORM_DATA_RESPONSE",
            "payload": {"software_id": cfg.SOFTWARE_ID, "form_data": form_data},
        }
        await intermediary_conn.ws.send(json.dumps(form_data_response_to_ai))
        print(
            f"--> Sent FORM_DATA_RESPONSE to intermediary (data from GUI user for item: {current_pending_item_name})."
        )
        await broadcast_to_gui(
            {
                "type": "LOG_MESSAGE",
                "message": f"User form data for '{current_pending_item_name}' sent to AI.",
            }
        )
        await broadcast_to_gui({"type": "CLEAR_FORM_DISPLAY"})
    else:
        print("Cannot send FORM_DATA_RESPONSE to intermediary: WS not connected.")
        await broadcast_to_gui(
            {
                "type": "LOG_MESSAGE",
                "message": "[ERROR] Failed to send user's form data to AI.",
            }
        )


# --- WebSocket Communication with Intermediary Server (Background Task) ---
async def intermediary_client_task():
    global current_view_name, cart_items, pending_item_for_form, text_input_values
    uri = f"{cfg.INTERMEDIARY_SERVER_WS_URL}{cfg.SOFTWARE_ID}"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                intermediary_conn.ws = websocket
                print(
                    f"Connected to Intermediary Server as '{cfg.SOFTWARE_ID}' at {uri}"
                )
                await broadcast_to_gui(
                    {
                        "type": "LOG_MESSAGE",
                        "message": f"Connected to Intermediary Server as {cfg.SOFTWARE_ID}.",
                    }
                )
                identify_msg = {
                    "type": "IDENTIFY_SOFTWARE",
                    "payload": {
                        "software_id": cfg.SOFTWARE_ID,
                        "name": cfg.SOFTWARE_NAME,
                        "description": cfg.SOFTWARE_DESCRIPTION,
                        "keywords": cfg.SOFTWARE_KEYWORDS,
                    },
                }
                await websocket.send(json.dumps(identify_msg))
                ack_str = await websocket.recv()
                ack_data = json.loads(ack_str)
                print(f"Intermediary ack: {ack_data}")
                await broadcast_to_gui(
                    {"type": "LOG_MESSAGE", "message": "Registered. Waiting for AI."}
                )

                async for message_str in websocket:
                    print(f"\n<-- Intermediary: {message_str[:300]}...")
                    message_data = json.loads(message_str)
                    msg_type = message_data.get("type")

                    if (
                        msg_type == "FORM_REQUEST"
                    ):  # From AI, for this software to display to user (via GUI)
                        print(
                            "Received FORM_REQUEST from AI/Intermediary. Broadcasting to GUI."
                        )
                        form_payload_for_gui = message_data.get("payload")
                        if form_payload_for_gui:
                            if form_payload_for_gui.get(
                                "item_context"
                            ):  # Store context for when GUI user submits
                                pending_item_for_form = form_payload_for_gui.get(
                                    "item_context"
                                )
                                print(
                                    f"  Stored pending_item_for_form from AI's FORM_REQUEST: {pending_item_for_form}"
                                )
                            await broadcast_to_gui(
                                {
                                    "type": "DISPLAY_FORM_REQUEST",
                                    "payload": form_payload_for_gui,
                                }
                            )
                            await broadcast_to_gui(
                                {
                                    "type": "LOG_MESSAGE",
                                    "message": f"AI requests form: {form_payload_for_gui.get('form_description')}",
                                }
                            )
                        else:
                            print(
                                "Warning: Received FORM_REQUEST from AI with no payload."
                            )

                    else:  # For other messages, log them to GUI before processing
                        await broadcast_to_gui(
                            {
                                "type": "LOG_MESSAGE",
                                "message": f"AI msg (type {msg_type}): {message_str[:70]}...",
                            }
                        )

                        if msg_type == "REQUEST_SOFTWARE_CAPABILITIES":
                            capabilities = get_capabilities_for_view(current_view_name)
                            response_msg = {
                                "type": "SOFTWARE_CAPABILITIES_RESPONSE",
                                "software_id": cfg.SOFTWARE_ID,
                                "payload": capabilities,
                            }
                            await websocket.send(json.dumps(response_msg))
                            await broadcast_to_gui(
                                {"type": "UPDATE_CAPABILITIES", "payload": capabilities}
                            )
                            print(f"--> Sent CAPS to intermediary.")

                        elif msg_type == "EXECUTE_SOLUTION_PLAN":
                            plan_payload = message_data.get("payload", {})
                            actions_from_ai = plan_payload.get("solution", {}).get(
                                "actions", []
                            )
                            await broadcast_to_gui(
                                {
                                    "type": "AI_THOUGHT",
                                    "message": f"Plan: {len(actions_from_ai)} actions. Executing...",
                                }
                            )
                            stop_processing_current_plan = False
                            actions_executed_count_for_status = 0
                            last_action_desc_for_status = "No actions executed."
                            for i, ai_action_data in enumerate(actions_from_ai):
                                if stop_processing_current_plan:
                                    break
                                await broadcast_to_gui(
                                    {
                                        "type": "EXECUTE_ACTION_VISUALIZATION",
                                        "payload": ai_action_data,
                                    }
                                )
                                await asyncio.sleep(0.8)
                                command = ai_action_data.get("command")
                                element_id = ai_action_data.get("element_id")
                                text_to_type = ai_action_data.get("text")
                                (
                                    success,
                                    send_form,
                                    form_payload_from_action,
                                    action_desc_status,
                                ) = _perform_action_and_update_state(
                                    command, element_id, text_to_type
                                )
                                last_action_desc_for_status = action_desc_status
                                if not success:
                                    stop_processing_current_plan = True
                                    print(
                                        f"    AI Action '{action_desc_status}' failed. Stopping plan."
                                    )
                                if (
                                    send_form and form_payload_from_action
                                ):  # If AI's action on THIS software triggers a form (to be sent back to AI)
                                    await websocket.send(
                                        json.dumps(
                                            {
                                                "type": "FORM_REQUEST",
                                                "payload": form_payload_from_action,
                                            }
                                        )
                                    )
                                    print(
                                        f"--> Sent FORM_REQUEST (AI's action on me triggered it)."
                                    )
                                    await broadcast_to_gui(
                                        {
                                            "type": "LOG_MESSAGE",
                                            "message": f"AI action on this software triggered a FORM_REQUEST (sent to AI).",
                                        }
                                    )
                                    stop_processing_current_plan = True
                                if success:
                                    actions_executed_count_for_status += 1
                                if not stop_processing_current_plan:
                                    current_caps_after_ai_action = (
                                        get_capabilities_for_view(current_view_name)
                                    )
                                    await broadcast_to_gui(
                                        {
                                            "type": "UPDATE_CAPABILITIES",
                                            "payload": current_caps_after_ai_action,
                                        }
                                    )
                                    await asyncio.sleep(0.3)
                            if (
                                not stop_processing_current_plan
                                and actions_executed_count_for_status > 0
                            ):
                                final_capabilities = get_capabilities_for_view(
                                    current_view_name
                                )
                                status_val = "SUCCESS"
                                if current_view_name == "order_success_page":
                                    status_val = "TASK_COMPLETED_BY_SOFTWARE"
                                status_update_payload = {
                                    "software_id": cfg.SOFTWARE_ID,
                                    "status": status_val,
                                    "message": f"AI plan: {last_action_desc_for_status}",
                                    "current_capabilities": final_capabilities,
                                }
                                await websocket.send(
                                    json.dumps(
                                        {
                                            "type": "ACTION_STATUS_UPDATE",
                                            "payload": status_update_payload,
                                        }
                                    )
                                )
                                print(
                                    f"--> Sent ACTION_STATUS_UPDATE (AI plan). Status: {status_val}"
                                )
                            elif (
                                not stop_processing_current_plan and not actions_from_ai
                            ):
                                print("AI sent an empty action plan.")
                            elif (
                                not stop_processing_current_plan
                                and actions_executed_count_for_status == 0
                                and actions_from_ai
                            ):
                                status_update_payload = {
                                    "software_id": cfg.SOFTWARE_ID,
                                    "status": "FAILURE",
                                    "message": "AI plan actions could not be executed.",
                                    "current_capabilities": get_capabilities_for_view(
                                        current_view_name
                                    ),
                                }
                                await websocket.send(
                                    json.dumps(
                                        {
                                            "type": "ACTION_STATUS_UPDATE",
                                            "payload": status_update_payload,
                                        }
                                    )
                                )
                                print(
                                    f"--> Sent ACTION_STATUS_UPDATE (FAILURE, AI plan)."
                                )

                        elif (
                            msg_type == "FORM_DATA_RESPONSE"
                        ):  # This is from AI, in response to a FORM_REQUEST *this software* sent to AI
                            form_data_payload = message_data.get("payload", {})
                            form_data = form_data_payload.get("form_data", {})
                            print(
                                f"Received FORM_DATA_RESPONSE from AI (for a form I initiated): {form_data}"
                            )
                            if (
                                pending_item_for_form
                                and form_data.get("taste")
                                and form_data.get("quantity")
                            ):
                                pending_item_for_form["taste"] = form_data["taste"]
                                pending_item_for_form["quantity"] = int(
                                    form_data["quantity"]
                                )
                                print(
                                    f"  Updated pending item '{pending_item_for_form['name']}' with specs from AI for a form I initiated."
                                )
                                caps_after_form_fill = get_capabilities_for_view(
                                    current_view_name
                                )
                                status_update_payload = {
                                    "software_id": cfg.SOFTWARE_ID,
                                    "status": "SUCCESS_FORM_FILLED",
                                    "message": f"Form (I initiated for {pending_item_for_form['name']}) filled by AI.",
                                    "current_capabilities": caps_after_form_fill,
                                }
                                await websocket.send(
                                    json.dumps(
                                        {
                                            "type": "ACTION_STATUS_UPDATE",
                                            "payload": status_update_payload,
                                        }
                                    )
                                )
                                print(
                                    f"--> Sent ACTION_STATUS_UPDATE (SUCCESS_FORM_FILLED by AI for my form)."
                                )
                                await broadcast_to_gui(
                                    {
                                        "type": "UPDATE_CAPABILITIES",
                                        "payload": caps_after_form_fill,
                                    }
                                )
                            else:
                                print(
                                    f"Error processing FORM_DATA_RESPONSE from AI (for my form): Missing context or data."
                                )
                                status_update_payload = {
                                    "software_id": cfg.SOFTWARE_ID,
                                    "status": "FAILURE_FORM_PROCESSING",
                                    "message": "Error processing AI's form data for a form I initiated.",
                                    "current_capabilities": get_capabilities_for_view(
                                        current_view_name
                                    ),
                                }
                                await websocket.send(
                                    json.dumps(
                                        {
                                            "type": "ACTION_STATUS_UPDATE",
                                            "payload": status_update_payload,
                                        }
                                    )
                                )
                        else:
                            print(
                                f"Unhandled AI message type in intermediary_client_task: {msg_type}"
                            )

        except websockets.exceptions.ConnectionClosed as e:
            print(f"Intermediary WS ConnectionClosed: {e}")
        except ConnectionRefusedError as e:
            print(f"Intermediary WS ConnectionRefused: {e}")
        except Exception as e:
            print(f"Intermediary client CRITICAL error: {type(e).__name__} - {e}")
            import traceback

            traceback.print_exc()
        finally:
            intermediary_conn.ws = None
            print("Attempting to reconnect to Intermediary Server in 5 seconds...")
            await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(intermediary_client_task())
    print("Intermediary client background task created.")


@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "software_name": cfg.SOFTWARE_NAME,
            "software_id": cfg.SOFTWARE_ID,
        },
    )
