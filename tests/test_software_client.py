# test_software_client.py
import asyncio
import websockets
import json
import uuid # For generating unique element IDs if needed

SOFTWARE_ID = "choutuan_clone_v1_test"
SERVER_URL = f"ws://localhost:8000/ws/software/{SOFTWARE_ID}"

current_view_name = "homepage"
# 模拟购物车中的物品 (简化表示)
cart_items = []

def get_capabilities_for_view(view_name: str) -> dict:
    global cart_items
    if view_name == "homepage":
        return {
            "current_view": "homepage",
            "elements": [
                {"id": "hp_waimai_button", "type": "button", "label": "外卖", "description": "点击进入外卖频道"},
                {"id": "hp_hotel_button", "type": "button", "label": "酒店", "description": "点击进入酒店预订"},
                {"id": "hp_movie_button", "type": "button", "label": "电影", "description": "点击查看电影票"},
            ]
        }
    elif view_name == "waimai_page":
        return {
            "current_view": "waimai_page",
            "elements": [
                {"id": "wm_search_food_input", "type": "text_input", "label": "搜索想吃的", "description": "输入食物名称进行搜索"},
                {"id": "wm_search_food_button", "type": "button", "label": "搜索美食", "description": "点击开始搜索食物"},
                {"id": "wm_food_list_item_1", "type": "list_item", "label": "北京烤鸭 (示例)", "description": "选择北京烤鸭"},
                {"id": "wm_food_list_item_2", "type": "list_item", "label": "宫保鸡丁 (示例)", "description": "选择宫保鸡丁"},
                {"id": "wm_view_cart_button", "type": "button", "label": f"查看购物车 ({len(cart_items)}件)", "description": "点击查看当前购物车中的商品"},
                {"id": "wm_back_to_home_button", "type": "button", "label": "返回首页", "description": "点击返回应用首页"},
            ]
        }
    elif view_name == "food_details_page":
        # 假设我们知道当前正在查看哪个商品，这里简化，不动态传入商品名
        return {
            "current_view": "food_details_page",
            "item_context": "北京烤鸭", # 示例上下文
            "elements": [
                {"id": "fd_select_taste_button", "type": "button", "label": "选择口味和数量", "description": "点击选择商品口味和数量"},
                {"id": "fd_add_to_cart_button", "type": "button", "label": "加入购物车", "description": "将当前商品（需先选规格）加入购物车"},
                {"id": "fd_back_to_waimai_button", "type": "button", "label": "返回外卖列表", "description": "点击返回外卖列表页"},
            ]
        }
    elif view_name == "cart_page":
        cart_summary = ", ".join([f"{item['name']}({item.get('taste', '默认口味')})x{item.get('quantity',1)}" for item in cart_items])
        cart_summary = cart_summary if cart_summary else "购物车是空的"
        elements = [
            {"id": "cp_item_summary", "type": "label", "label": f"购物车商品: {cart_summary}", "description": "当前购物车中的商品"},
            {"id": "cp_continue_shopping_button", "type": "button", "label": "继续点餐", "description": "返回外卖列表继续选择商品"},
        ]
        if cart_items: # 只有购物车不为空时才显示结算按钮
            elements.append({"id": "cp_proceed_to_checkout_button", "type": "button", "label": "去结算", "description": "点击进入订单确认和支付页面"})
        return {
            "current_view": "cart_page",
            "elements": elements
        }
    elif view_name == "checkout_page":
        return {
            "current_view": "checkout_page",
            "elements": [
                {"id": "co_address_field", "type": "text_input", "label": "配送地址", "description": "输入您的配送地址"},
                {"id": "co_phone_field", "type": "text_input", "label": "联系电话", "description": "输入您的联系电话"},
                {"id": "co_confirm_order_button", "type": "button", "label": "确认下单", "description": "点击最终确认并提交订单"},
                {"id": "co_back_to_cart_button", "type": "button", "label": "返回购物车", "description": "返回修改购物车"},
            ]
        }
    elif view_name == "order_success_page":
        return {
            "current_view": "order_success_page",
            "elements": [
                {"id": "os_message_label", "type": "label", "label": "订单提交成功！感谢您的光临！", "description": "订单成功信息"},
                {"id": "os_back_to_home_button", "type": "button", "label": "返回首页", "description": "点击返回应用首页"},
            ]
        }
    else: # 未知页面或未配置
        return {"current_view": "unknown_page", "elements": [{"id": "err_label", "type": "label", "label": "未知页面", "description": "当前页面未定义能力"}]}


async def run_software_client():
    global current_view_name, cart_items
    # 存储上一个被点击的、等待表单数据的物品信息 (简化)
    pending_item_for_form = None

    async with websockets.connect(SERVER_URL) as websocket:
        print(f"Software client '{SOFTWARE_ID}' connected to server.")
        identify_message = {
            "type": "IDENTIFY_SOFTWARE",
            "payload": {
                "software_id": SOFTWARE_ID, "name": "丑团克隆测试版",
                "description": "一个用于测试的提供外卖、酒店等服务的综合应用。",
                "keywords": ["测试外卖", "测试酒店", "电影票"]
            }
        }
        await websocket.send(json.dumps(identify_message))
        print(f"Sent IDENTIFY_SOFTWARE: {json.dumps(identify_message)}")
        response_str = await websocket.recv()
        print(f"Received from server (ack): {response_str}")

        print(f"\nSoftware client '{SOFTWARE_ID}' is now listening for commands...")
        try:
            while True:
                message_str = await websocket.recv()
                print(f"\n<-- Software client received from server: {message_str}")
                message_data = json.loads(message_str)
                msg_type = message_data.get("type")

                if msg_type == "REQUEST_SOFTWARE_CAPABILITIES":
                    capabilities = get_capabilities_for_view(current_view_name)
                    response_capabilities_msg = {
                        "type": "SOFTWARE_CAPABILITIES_RESPONSE",
                        "software_id": SOFTWARE_ID, "payload": capabilities
                    }
                    await websocket.send(json.dumps(response_capabilities_msg))
                    print(f"--> Sent SOFTWARE_CAPABILITIES_RESPONSE: {json.dumps(capabilities, ensure_ascii=False)}")

                elif msg_type == "EXECUTE_SOLUTION_PLAN":
                    plan_payload = message_data.get("payload", {})
                    solution = plan_payload.get("solution", {})
                    actions_from_ai = solution.get("actions", [])
                    print(f"Received EXECUTE_SOLUTION_PLAN with {len(actions_from_ai)} actions.")

                    actions_executed_this_batch = 0
                    last_action_description_this_batch = "No actions in plan."
                    stop_processing_current_plan = False # 标志位：如果触发了FORM_REQUEST，则停止处理本轮后续actions

                    for i, action in enumerate(actions_from_ai):
                        if stop_processing_current_plan:
                            print(f"  Skipping remaining actions in this plan due to FORM_REQUEST trigger.")
                            break

                        command = action.get("command")
                        element_id = action.get("element_id")
                        text_to_type = action.get("text")
                        action_description = action.get("description", f"Executing {command} on {element_id}")
                        print(f"  Simulating action {i+1}/{len(actions_from_ai)}: {command} on element '{element_id}' (Desc: {action_description})")
                        if text_to_type: print(f"    Text: '{text_to_type}'")

                        action_performed_successfully = True # 假设当前单个action成功

                        # --- 核心状态转换逻辑 ---
                        if command == "CLICK":
                            if element_id == "hp_waimai_button":
                                current_view_name = "waimai_page"
                            elif element_id == "wm_food_list_item_1": # 假设选择北京烤鸭
                                current_view_name = "food_details_page"
                                pending_item_for_form = {"name": "北京烤鸭", "id": "wm_food_list_item_1"}
                            elif element_id == "wm_food_list_item_2": # 假设选择宫保鸡丁
                                current_view_name = "food_details_page"
                                pending_item_for_form = {"name": "宫保鸡丁", "id": "wm_food_list_item_2"}
                            elif element_id == "fd_select_taste_button":
                                if pending_item_for_form:
                                    print(f"    --> Clicked 'select taste' for {pending_item_for_form['name']}, preparing FORM_REQUEST.")
                                    form_request_msg = {
                                        "type": "FORM_REQUEST",
                                        "payload": {
                                            "software_id": SOFTWARE_ID,
                                            "form_description": f"请选择 {pending_item_for_form['name']} 的口味和数量",
                                            "item_context": pending_item_for_form, # 把当前物品信息带过去
                                            "fields": [
                                                {"id": "taste", "label": "口味", "type": "select", "options": ["原味", "微辣", "麻辣"]},
                                                {"id": "quantity", "label": "数量", "type": "number", "default": 1, "min":1}
                                            ]
                                        }
                                    }
                                    await websocket.send(json.dumps(form_request_msg))
                                    print(f"--> Sent FORM_REQUEST. Waiting for FORM_DATA_RESPONSE.")
                                    stop_processing_current_plan = True # 发送表单请求后，暂停处理本批次后续actions
                                else:
                                    print("    Error: fd_select_taste_button clicked but no pending_item_for_form.")
                                    action_performed_successfully = False
                            elif element_id == "fd_add_to_cart_button":
                                if pending_item_for_form and pending_item_for_form.get("taste") and pending_item_for_form.get("quantity"):
                                    print(f"    --> Clicked 'add to cart' for {pending_item_for_form['name']} ({pending_item_for_form['taste']} x{pending_item_for_form['quantity']}).")
                                    cart_items.append(pending_item_for_form.copy()) # 加入购物车
                                    pending_item_for_form = None # 清理待处理物品
                                    current_view_name = "cart_page" # 跳转到购物车页面
                                else:
                                    print(f"    Error: Cannot add to cart. Taste/quantity for {pending_item_for_form} not selected via form yet.")
                                    action_performed_successfully = False
                            elif element_id == "wm_view_cart_button" or element_id == "co_back_to_cart_button":
                                current_view_name = "cart_page"
                            elif element_id == "cp_proceed_to_checkout_button":
                                current_view_name = "checkout_page"
                            elif element_id == "co_confirm_order_button":
                                # 模拟下单成功
                                print(f"    SIMULATING ORDER PLACEMENT for items: {cart_items}")
                                if not cart_items: # 简单校验
                                     print("    Error: Cart is empty, cannot place order.")
                                     action_performed_successfully = False
                                else:
                                    print(f"    ORDER PLACED (SIMULATED)! Items: {json.dumps(cart_items, ensure_ascii=False)}")
                                    cart_items = [] # 清空购物车
                                    current_view_name = "order_success_page"
                            elif element_id == "wm_back_to_home_button" or element_id == "os_back_to_home_button" or element_id == "cp_continue_shopping_button":
                                current_view_name = "waimai_page" if element_id == "cp_continue_shopping_button" else "homepage"
                            elif element_id == "fd_back_to_waimai_button":
                                current_view_name = "waimai_page"
                            else:
                                print(f"    Warning: Click on unhandled element_id '{element_id}' in view '{current_view_name}'. Assuming no state change.")
                                # action_performed_successfully = False # 或者认为这种点击无效
                        elif command == "TYPE_TEXT":
                            print(f"    Simulated typing '{text_to_type}' into '{element_id}'.")
                            # 实际应用中，这里可能需要更新某个输入框的值，并在后续能力中体现
                        else:
                            print(f"    Unknown command: {command}")
                            action_performed_successfully = False

                        if action_performed_successfully:
                            actions_executed_this_batch += 1
                            last_action_description_this_batch = action_description
                        else: # 如果单个action失败，也停止处理本批次后续actions
                            print(f"    Action '{action_description}' failed or led to waiting state. Stopping current plan execution.")
                            stop_processing_current_plan = True # 确保停止

                        await asyncio.sleep(0.2) # 模拟操作耗时

                    # 只有在没有触发FORM_REQUEST且至少执行了一个action时，才发送常规的ACTION_STATUS_UPDATE
                    if not stop_processing_current_plan and actions_executed_this_batch > 0:
                        new_capabilities = get_capabilities_for_view(current_view_name)
                        status_to_send = "SUCCESS"
                        message_to_send = f"Successfully simulated {actions_executed_this_batch} actions. Last: {last_action_description_this_batch}."

                        if current_view_name == "order_success_page":
                            status_to_send = "TASK_COMPLETED_BY_SOFTWARE" # 特殊状态表示软件认为任务完成
                            message_to_send = "Order placed successfully!"

                        status_update_msg = {
                            "type": "ACTION_STATUS_UPDATE",
                            "payload": {
                                "software_id": SOFTWARE_ID,
                                # "action_index_completed": actions_executed_this_batch -1, # 或者发送执行了多少个
                                "status": status_to_send,
                                "message": message_to_send,
                                "current_capabilities": new_capabilities
                            }
                        }
                        await websocket.send(json.dumps(status_update_msg))
                        print(f"--> Sent ACTION_STATUS_UPDATE. New view: {current_view_name}. Status: {status_to_send}")
                    elif not stop_processing_current_plan and actions_executed_this_batch == 0 and actions_from_ai:
                        # 如果AI发来了actions，但没有一个被执行（例如都是未知命令或无效操作）
                        print("    No actions from the plan were successfully executed.")
                        # 可以选择发送一个失败的ACTION_STATUS_UPDATE
                        status_update_msg = {
                            "type": "ACTION_STATUS_UPDATE",
                            "payload": {
                                "software_id": SOFTWARE_ID,
                                "status": "FAILURE",
                                "message": "No actions from the plan could be executed.",
                                "current_capabilities": get_capabilities_for_view(current_view_name) # 返回当前能力
                            }
                        }
                        await websocket.send(json.dumps(status_update_msg))
                        print(f"--> Sent ACTION_STATUS_UPDATE (FAILURE). Current view: {current_view_name}")


                elif msg_type == "FORM_DATA_RESPONSE":
                    form_data_payload = message_data.get("payload", {})
                    form_data = form_data_payload.get("form_data", {})
                    # item_context_from_form = form_data_payload.get("item_context") # 如果AI传回了上下文

                    print(f"Received FORM_DATA_RESPONSE: {form_data}")
                    if pending_item_for_form and form_data.get("taste") and form_data.get("quantity"):
                        pending_item_for_form["taste"] = form_data["taste"]
                        pending_item_for_form["quantity"] = int(form_data["quantity"])
                        print(f"  Updated pending item '{pending_item_for_form['name']}' with taste: {form_data['taste']}, quantity: {form_data['quantity']}")

                        # 表单填写完成后，我们应该让AI基于更新后的状态（即可以加入购物车了）进行下一步规划
                        # 所以，我们发送一个ACTION_STATUS_UPDATE，其中包含当前food_details_page的能力
                        # LLM的对话历史中应该已经记录了表单填写事件
                        current_capabilities_after_form = get_capabilities_for_view(current_view_name) # 视图仍是food_details_page
                        status_update_msg = {
                            "type": "ACTION_STATUS_UPDATE",
                            "payload": {
                                "software_id": SOFTWARE_ID,
                                "status": "SUCCESS_FORM_FILLED", # AI端可以识别这个状态
                                "message": f"Form data {form_data} processed for item {pending_item_for_form['name']}. Ready to add to cart.",
                                "current_capabilities": current_capabilities_after_form
                            }
                        }
                        await websocket.send(json.dumps(status_update_msg))
                        print(f"--> Sent ACTION_STATUS_UPDATE after processing form data. Current view: {current_view_name}")
                    else:
                        print("  Error: Received form data but no pending item or missing taste/quantity.")
                        # 可以发送一个失败的ACTION_STATUS_UPDATE
                        status_update_msg = {
                            "type": "ACTION_STATUS_UPDATE",
                            "payload": {
                                "software_id": SOFTWARE_ID,
                                "status": "FAILURE_FORM_PROCESSING",
                                "message": "Error processing form data due to missing context or data.",
                                "current_capabilities": get_capabilities_for_view(current_view_name)
                            }
                        }
                        await websocket.send(json.dumps(status_update_msg))
                        print(f"--> Sent ACTION_STATUS_UPDATE (FAILURE_FORM_PROCESSING).")


                else:
                    print(f"Software client received unhandled message type: {msg_type}")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"Software client '{SOFTWARE_ID}' connection closed: {e}")
        except Exception as e:
            print(f"An error occurred in software client: {type(e).__name__} - {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_software_client())