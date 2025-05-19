# ai_agent/agent_cli.py
import asyncio
import json
from typing import Dict, Any, List, Optional

from .websocket_client import AgentWebsocketClient
from .llm_handler import llm_handler_instance as llm_handler
from . import agent_config

# ANSI escape codes for colors
class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    RESET = "\033[0m"

    @staticmethod
    def _colorize(text: str, color: str) -> str:
        return f"{color}{text}{Colors.RESET}"

    @staticmethod
    def prompt(text: str) -> str:
        return f"{Colors.CYAN}{Colors.BOLD}{text}{Colors.RESET}"

    @staticmethod
    def info(text: str) -> str:
        return Colors._colorize(text, Colors.BLUE)

    @staticmethod
    def success(text: str) -> str:
        return Colors._colorize(text, Colors.GREEN)

    @staticmethod
    def warning(text: str) -> str:
        return Colors._colorize(text, Colors.YELLOW)

    @staticmethod
    def error(text: str) -> str:
        return Colors._colorize(text, Colors.RED)

    @staticmethod
    def header(text: str) -> str:
        return f"{Colors.MAGENTA}{Colors.BOLD}{text}{Colors.RESET}"

class AIAgentCLI:
    def __init__(self):
        self.ws_client = AgentWebsocketClient(
            agent_id=agent_config.AGENT_ID,
            server_url_template=agent_config.INTERMEDIARY_SERVER_URL_TEMPLATE,
            on_message_callback=self.handle_server_message
        )
        self.available_softwares: List[Dict[str, Any]] = []
        self.selected_software_id: Optional[str] = None
        self.current_task_description: Optional[str] = None
        self.is_waiting_for_llm = False # True if waiting for LLM API response
        self._expected_message_type: Optional[str] = None
        self._message_future: Optional[asyncio.Future] = None
        self.current_item_context_from_form_request: Optional[Dict[str, Any]] = None

    async def handle_server_message(self, message_data: Dict[str, Any]):
        msg_type = message_data.get("type")
        payload = message_data.get("payload")
        # 打印时对payload进行格式化，确保中文正常显示
        print(f"\n{Colors.info(f'<-- Received from server:')} {Colors.BOLD}Type:{Colors.RESET} {msg_type}")
        # Avoid printing full payload unless necessary or simple
        # if payload:
        #     print(Colors.info(f"    Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'Data received.'}"))


        if self._message_future and not self._message_future.done() and msg_type == self._expected_message_type:
            self._message_future.set_result(payload)
            return # Message handled by a specific waiter

        # General message handling
        if msg_type == "SOFTWARE_LIST_RESPONSE":
            self.available_softwares = payload if payload else []
            # Displaying the list is handled by the function that requested it

        elif msg_type == "SOFTWARE_CAPABILITIES_RESPONSE":
            software_id = message_data.get("software_id") # software_id is at the top level of this message
            print(Colors.info(f"Received capabilities for software '{Colors.BOLD}{software_id}{Colors.RESET}'."))
            if self.selected_software_id == software_id:
                await self.process_capabilities_and_plan_next_step(payload) # payload is the capabilities dict
            else:
                print(Colors.warning(f"Warning: Received capabilities for unselected software '{software_id}'. Ignoring."))


        elif msg_type == "ACTION_STATUS_UPDATE":
            software_id = payload.get("software_id")
            status = payload.get("status")
            message = payload.get("message")
            current_capabilities = payload.get("current_capabilities")
            print(Colors.info(f"Action status from '{Colors.BOLD}{software_id}{Colors.RESET}': {Colors.YELLOW}{status}{Colors.RESET} - {message}"))

            if status == "TASK_COMPLETED_BY_SOFTWARE":
                print(Colors.success(f"\nSoftware '{Colors.BOLD}{software_id}{Colors.RESET}' reported task completion: {message}"))
                print(Colors.success(f"{Colors.BOLD}Congratulations! Your task is completed by the software.{Colors.RESET}"))
                self.current_task_description = None
                self.selected_software_id = None
                llm_handler.clear_history()
                self.is_waiting_for_llm = False
                return

            if status not in ["FAILURE", "FAILURE_FORM_PROCESSING"] and current_capabilities:
                if self.selected_software_id == software_id:
                    await self.process_capabilities_and_plan_next_step(current_capabilities)
            elif status in ["FAILURE", "FAILURE_FORM_PROCESSING"]:
                print(Colors.error(f"Task execution failed or form processing error on software '{Colors.BOLD}{software_id}{Colors.RESET}': {message}"))
                failure_context = (
                    f"The software '{software_id}' reported an error after my last planned actions. "
                    f"Status: '{status}', Message: '{message}'. "
                )
                if current_capabilities:
                    failure_context += f"The current capabilities at the time of failure were: {json.dumps(current_capabilities, ensure_ascii=False, indent=2)}. "
                else:
                    failure_context += "The software did not provide updated capabilities with this failure notice. You might need to re-request capabilities or carefully re-evaluate based on the last known state."
                failure_context += "Please analyze this failure and plan the next step accordingly, perhaps by trying a different approach or asking the user for help if you are stuck."
                llm_handler.add_message_to_history("system", failure_context)

                if current_capabilities:
                    print(Colors.info("Attempting to re-plan based on failure feedback and current capabilities..."))
                    await self.process_capabilities_and_plan_next_step(current_capabilities)
                else:
                    print(Colors.warning("Software reported failure without new capabilities. LLM might need to re-request capabilities or user intervention is needed."))
                    self.is_waiting_for_llm = False # Allow user input / main loop to take over
            else:
                print(Colors.warning(f"Received ACTION_STATUS_UPDATE with status '{status}' but no capabilities or unhandled status."))
                self.is_waiting_for_llm = False

        elif msg_type == "FORM_REQUEST":
            software_id = payload.get("software_id")
            form_description = payload.get("form_description")
            fields = payload.get("fields")
            self.current_item_context_from_form_request = payload.get("item_context")
            print(Colors.header(f"\n--- Form Request from {software_id} ---"))
            if self.current_item_context_from_form_request:
                print(Colors.info(f"Context: {self.current_item_context_from_form_request.get('name', 'Unknown item')}"))
            print(Colors.info(form_description))
            await self.handle_form_request(software_id, fields)
        else:
            print(Colors.warning(f"Received unhandled message type: {msg_type}"))

    async def _wait_for_specific_message(self, msg_type: str, timeout: float = 10.0) -> Optional[Any]:
        if not self.ws_client.is_connected():
            print(Colors.error("Not connected to server. Cannot wait for message."))
            return None
        self._expected_message_type = msg_type
        self._message_future = asyncio.Future()
        try:
            payload = await asyncio.wait_for(self._message_future, timeout=timeout)
            return payload
        except asyncio.TimeoutError:
            print(Colors.warning(f"Timeout waiting for message type '{msg_type}'"))
            return None
        finally:
            self._expected_message_type = None
            self._message_future = None

    def _display_software_list(self):
        if not self.available_softwares:
            print(Colors.warning("No software available."))
            return
        print(Colors.header("\nAvailable Software:"))
        for i, sw in enumerate(self.available_softwares):
            print(f"  {Colors.CYAN}{i+1}.{Colors.RESET} {Colors.BOLD}{sw.get('name')}{Colors.RESET} (ID: {sw.get('software_id')}) - {sw.get('description')}")

    async def request_software_list(self):
        if not self.ws_client.is_connected():
            print(Colors.error("Not connected to server. Cannot request software list."))
            return False
        print(Colors.info(f"\n{Colors.BOLD}--> Requesting software list from server...{Colors.RESET}"))
        await self.ws_client.send_message({"type": "REQUEST_SOFTWARE_LIST"})
        payload = await self._wait_for_specific_message("SOFTWARE_LIST_RESPONSE")
        if payload is not None:
            self.available_softwares = payload
            return True
        return False

    async def process_capabilities_and_plan_next_step(self, capabilities: Dict[str, Any]):
        if not self.current_task_description or not self.selected_software_id:
            print(Colors.warning("No current task or selected software to plan for."))
            self.is_waiting_for_llm = False
            return

        print(Colors.info(f"\n{Colors.BOLD}LLM is planning next step for task:{Colors.RESET} '{self.current_task_description}' on '{Colors.BOLD}{self.selected_software_id}{Colors.RESET}'..."))
        self.is_waiting_for_llm = True # Waiting for LLM API response

        system_prompt_for_planning = f"""
You are an AI assistant controlling a software application to achieve the user's task: "{self.current_task_description}".
You are interacting with software: "{self.selected_software_id}".
The software has provided its current capabilities (UI elements and actions).
Your dialogue history with the user and previous interactions with the software are also part of your context.

**Available Commands for `actions`:**
- `CLICK`: Used to click on buttons, links, or other clickable elements.
  - `{{ "command": "CLICK", "element_id": "id_of_element_to_click", "description": "Reason for clicking." }}`
- `TYPE_TEXT`: Used to type text into input fields (elements with `type: "text_input"`).
  - `{{ "command": "TYPE_TEXT", "element_id": "id_of_input_field", "text": "text_to_type", "description": "Reason for typing." }}`

**Important Considerations for Planning:**
1.  **Use Only Defined Commands:** You MUST use only the `CLICK` or `TYPE_TEXT` commands as defined above. Do not invent new commands.
2.  **Valid Element IDs:** Ensure that the `element_id` specified in an action exists in the `elements` list of the current software capabilities. If an element is not listed, you cannot interact with it.
3.  **Filling Multiple Fields:** If you need to fill multiple text input fields on a page, you MUST generate a separate `TYPE_TEXT` action for each field.
4.  **Prioritize Options/Selections & Forms:** If elements for choices exist, handle them. If a click leads to a `FORM_REQUEST` from software, your next step after user fills it is to use that info.
5.  **Step-by-Step Execution:** Plan one or a very small, logical sequence of actions at a time.
6.  **Task Completion:** Only set "is_task_complete": true when an order confirmation is received from the software (e.g., via `ACTION_STATUS_UPDATE` with status 'TASK_COMPLETED_BY_SOFTWARE').
7.  **Context is Key**: Refer to the dialogue history.
8.  **If Information is Missing:** If you need more information from the user to proceed (e.g., what specific item to search for, delivery details not yet provided), set "actions" to an empty list or null, and clearly state what information you need in "next_step_reasoning". The user will then be prompted.

Based on these capabilities, dialogue history, and available commands, decide the next actions.
Output your decision as a JSON object:
{{
  "thought": "Your reasoning for choosing the action(s), ensuring you only use defined commands and valid element_ids.",
  "actions": [
    // One or more actions using ONLY CLICK or TYPE_TEXT with valid element_ids
    // OR an empty list/null if awaiting user clarification (see point 8 above)
  ],
  "is_task_complete": false,
  "next_step_reasoning": "What you expect to happen next. If awaiting user input, clearly state the question for the user here."
}}

Current software capabilities:
{json.dumps(capabilities, indent=2, ensure_ascii=False)}
"""
        user_prompt_for_planning = "What is the next best action or sequence of actions to achieve the task, considering the current capabilities, our conversation history, and the need for valid actions?"

        llm_response = await llm_handler.get_llm_response(
            user_prompt=user_prompt_for_planning,
            system_prompt=system_prompt_for_planning,
            expect_json=True
        )
        # LLM API call finished, so we are no longer "waiting for LLM" in that specific sense.
        # However, the overall agent might still be in a state of processing this response.
        # self.is_waiting_for_llm = False # Set this later based on outcome

        if llm_response and not llm_response.get("error"):
            # print(f"LLM Plan: {json.dumps(llm_response, indent=2, ensure_ascii=False)}")
            print(Colors.info(f"{Colors.BOLD}LLM Plan received.{Colors.RESET}"))
            print(f"  {Colors.BOLD}Thought:{Colors.RESET} {llm_response.get('thought', 'N/A')}")
            if llm_response.get("actions"):
                 print(f"  {Colors.BOLD}Planned Actions:{Colors.RESET} {len(llm_response.get('actions'))} action(s)")
            else:
                 print(f"  {Colors.BOLD}Planned Actions:{Colors.RESET} None")
            print(f"  {Colors.BOLD}Next Step Reasoning:{Colors.RESET} {llm_response.get('next_step_reasoning', 'N/A')}")

            planned_actions = llm_response.get("actions")
            is_task_complete_by_llm = llm_response.get("is_task_complete", False)
            next_step_reasoning = llm_response.get("next_step_reasoning", "")

            valid_actions_to_send = []
            actions_are_valid_overall = True # Assume valid until proven otherwise

            if isinstance(planned_actions, list): # 首先检查是不是列表 (包括空列表)
                if not planned_actions: # 空列表 []
                    print(Colors.info("LLM planned an empty list of actions."))
                    # actions_are_valid_overall 保持 True，valid_actions_to_send 为空
                else: # planned_actions 是一个非空列表
                    available_element_ids = {el.get("id") for el in capabilities.get("elements", []) if el.get("id")}
                    for action_idx, action in enumerate(planned_actions):
                        cmd = action.get("command")
                        eid = action.get("element_id")
                        action_valid_this_step = True
                        if cmd not in ["CLICK", "TYPE_TEXT"]:
                            print(Colors.error(f"LLM Validation Error (Action {action_idx+1}): Invalid command '{cmd}'. Action ignored."))
                            action_valid_this_step = False
                        if eid and eid not in available_element_ids:
                            print(Colors.error(f"LLM Validation Error (Action {action_idx+1}): Element ID '{eid}' for command '{cmd}' does not exist. Action ignored."))
                            action_valid_this_step = False
                        
                        if action_valid_this_step:
                            valid_actions_to_send.append(action)
                        else:
                            actions_are_valid_overall = False # Mark that at least one action was invalid
            
            elif planned_actions is None: # LLM 显式返回 null
                print(Colors.info("LLM explicitly planned no actions (actions: null)."))
                # actions_are_valid_overall 保持 True，valid_actions_to_send 为空
            else: # planned_actions 不是列表也不是 None (例如，是个字符串或其他错误类型)
                print(Colors.error(f"LLM Validation Error: 'actions' field is not a list or null. Value: {planned_actions}"))
                actions_are_valid_overall = False # 结构性错误

            # --- 后续处理 ---
            # 如果 actions_are_valid_overall 为 False，意味着LLM的输出结构有问题，或者包含了无效指令
            # 此时，即使 valid_actions_to_send 可能有一些内容（如果部分有效），我们也应该优先处理错误
            if not actions_are_valid_overall:
                print(Colors.warning("LLM plan contained invalid actions or had an incorrect structure. Requesting LLM to replan or clarify."))
                llm_handler.add_message_to_history(
                    "system",
                    f"My previous plan was problematic. It either contained actions targeting non-existent elements, used invalid commands, or the 'actions' field was not a list. "
                    f"The problematic plan was related to these actions: {planned_actions}. " # 给LLM看它之前错在哪
                    f"Please re-evaluate based on the provided capabilities: {json.dumps(capabilities, indent=2, ensure_ascii=False)}. "
                    f"Ensure all element_ids exist, commands are 'CLICK' or 'TYPE_TEXT', and 'actions' is a list (can be empty if awaiting clarification)."
                )
                self.is_waiting_for_llm = False
                # 考虑是否立即重新规划，或者让主循环处理
                # 如果立即重新规划：
                # print("Attempting to replan immediately due to invalid previous plan...")
                # await self.process_capabilities_and_plan_next_step(capabilities)
                return # 返回，让主循环或用户决定下一步

            # 到这里，actions_are_valid_overall 为 True，意味着 planned_actions 是 list 或 None
            # valid_actions_to_send 可能为空（如果 planned_actions 是 [] 或 None，或所有action都无效但结构是list）
            # 或者包含有效action

            if is_task_complete_by_llm:
                print(Colors.success(f"\nLLM believes the task '{Colors.BOLD}{self.current_task_description}{Colors.RESET}' is complete. Reasoning: {next_step_reasoning}"))
                if not valid_actions_to_send: # 没有可执行的action了，LLM也认为完成了
                    print(Colors.info("LLM indicates task complete with no further actions. Waiting for software confirmation or user input."))
                    self.is_waiting_for_llm = False
                    return

            if valid_actions_to_send: # 有效的action可以发送
                solution_plan = {"actions": valid_actions_to_send}
                print(Colors.info(f"\n{Colors.BOLD}--> Sending {len(valid_actions_to_send)} valid action(s) to software '{self.selected_software_id}'...{Colors.RESET}"))
                await self.ws_client.send_message({
                    "type": "EXECUTE_SOLUTION_PLAN",
                    "payload": {
                        "software_id": self.selected_software_id,
                        "solution": solution_plan
                    }
                })
                # is_waiting_for_llm 保持 True，等待 ACTION_STATUS_UPDATE
            elif not valid_actions_to_send and next_step_reasoning: # 没有有效action，但LLM有话要说（通常是提问）
                print(Colors.header("\n--- LLM Needs Clarification ---"))
                print(f"{Colors.BOLD}LLM:{Colors.RESET} {Colors.info(next_step_reasoning)}")
                llm_handler.add_message_to_history("assistant", f"I need more information to proceed: {next_step_reasoning}")
                self.is_waiting_for_llm = False # 等待用户输入

                user_response_for_clarification = ""
                try:
                    print(Colors.prompt("AI needs more info. Your response (press Enter if no input): "), end='', flush=True)
                    user_response_for_clarification = await asyncio.to_thread(input)
                except Exception as e:
                    print(Colors.error(f"Error during input for clarification: {e}"))

                if user_response_for_clarification.strip():
                    llm_handler.add_message_to_history("user", user_response_for_clarification.strip())
                    print(Colors.success("Thanks! Re-planning with your information..."))
                    await self.process_capabilities_and_plan_next_step(capabilities) # 重新规划
                else:
                    print(Colors.warning("No response or empty response from user. LLM may remain stuck. You can try 'abort' or provide input next time."))
                    # is_waiting_for_llm 保持 False
            elif not is_task_complete_by_llm: # 没有有效action，没有澄清，LLM也不认为完成
                print(Colors.warning(f"LLM did not provide any valid actions and does not consider task complete. Reasoning: {llm_response.get('thought')} - {next_step_reasoning}"))
                self.is_waiting_for_llm = False
        else: # LLM API 调用本身失败
            error_detail = llm_response.get('error', str(llm_response)) if isinstance(llm_response, dict) else str(llm_response)
            print(Colors.error(f"Failed to get a valid plan from LLM: {error_detail}"))
            self.is_waiting_for_llm = False

    async def handle_form_request(self, software_id: str, fields: List[Dict[str, Any]]):
        # self.is_waiting_for_llm should be False here, as we are now waiting for user console input
        self.is_waiting_for_llm = False

        form_data = {}
        print(Colors.header("Please fill out the following form:"))
        for field in fields:
            field_id = field.get("id")
            label = field.get("label")
            options = field.get("options")
            default_value_from_field = field.get("default", "")

            prompt_text_parts = [f"{Colors.CYAN}{label}{Colors.RESET}"]
            if options:
                prompt_text_parts.append(f" (Options: {Colors.YELLOW}{', '.join(options)}{Colors.RESET})")
            if default_value_from_field:
                prompt_text_parts.append(f" [default: {Colors.GREEN}{default_value_from_field}{Colors.RESET}]")
            prompt_text_parts.append(": ")
            
            full_prompt_text = "".join(prompt_text_parts)

            user_input_form = ""
            try:
                print(full_prompt_text, end='', flush=True) # Use print for colored prompt
                user_input_form = await asyncio.to_thread(input)
            except Exception as e:
                 print(Colors.error(f"Error during form input: {e}"))
            form_data[field_id] = user_input_form if user_input_form.strip() else str(default_value_from_field)


        print(Colors.info(f"\n{Colors.BOLD}--> Sending form data to software '{software_id}'...{Colors.RESET}"))
        message_to_send_to_software = {
            "type": "FORM_DATA_RESPONSE",
            "payload": { "software_id": software_id, "form_data": form_data }
        }
        await self.ws_client.send_message(message_to_send_to_software)

        history_message_content = (
            f"User was presented with a form by software '{software_id}'. "
        )
        if self.current_item_context_from_form_request:
             history_message_content += f"The form was likely for item: '{self.current_item_context_from_form_request.get('name', 'Unknown Item')}'. "
        history_message_content += f"User submitted the following data: {json.dumps(form_data)}. " # Keep JSON for history
        history_message_content += "I have sent this data to the software and am now awaiting its status update and new capabilities."

        llm_handler.add_message_to_history("assistant", history_message_content)
        print(Colors.info(f"Added to LLM history: User filled form with {len(form_data)} fields."))
        self.current_item_context_from_form_request = None
        self.is_waiting_for_llm = True # Now wait for ACTION_STATUS_UPDATE from software

    async def run(self):
        print(Colors.success(f"{Colors.BOLD}Starting AI Agent CLI...{Colors.RESET}"))
        if not await self.ws_client.connect():
            print(Colors.error("Exiting due to connection failure."))
            return

        try:
            while True:
                if self.is_waiting_for_llm:
                    await asyncio.sleep(0.1) # Yield control while waiting for async operations
                    continue

                if not self.current_task_description:
                    print(Colors.prompt("\nWhat would you like to do? (Type 'list' to see software, 'quit' to exit, 'abort' to cancel current task)"))
                    user_input_task = ""
                    try:
                        # input() itself doesn't easily support ANSI for its prompt string on all terminals
                        # So we print the prompt separately if complex coloring is needed.
                        # For simple prompt like "> ", direct use is fine.
                        user_input_task = await asyncio.to_thread(input, Colors.prompt("> "))
                    except Exception as e:
                        print(Colors.error(f"Error reading user task: {e}"))
                        continue # or break, depending on desired behavior

                    self.current_task_description = user_input_task.strip()

                    if not self.current_task_description:
                        continue
                    if self.current_task_description.lower() == 'quit':
                        break
                    if self.current_task_description.lower() == 'list':
                        if await self.request_software_list():
                            self._display_software_list()
                        self.current_task_description = None
                        continue
                    if self.current_task_description.lower() == 'abort':
                        print(Colors.warning("Current task aborted."))
                        self.current_task_description = None
                        self.selected_software_id = None
                        llm_handler.clear_history()
                        continue

                    print(Colors.info(f"Received task: {Colors.BOLD}{self.current_task_description}{Colors.RESET}"))
                    llm_handler.clear_history()
                    llm_handler.add_message_to_history("user", f"My task is: {self.current_task_description}")

                    if not await self.request_software_list() or not self.available_softwares:
                        print(Colors.error("Could not get software list or no software available. Cannot proceed with the task."))
                        self.current_task_description = None
                        continue
                    self._display_software_list()
                    if not self.available_softwares: # Should be redundant due to check above, but safe
                        self.current_task_description = None
                        continue

                    sw_choice_input = ""
                    try:
                        sw_choice_input = await asyncio.to_thread(input, Colors.prompt("Enter the number of the software to use: "))
                    except Exception as e:
                        print(Colors.error(f"Error reading software choice: {e}"))
                        self.current_task_description = None; continue


                    try:
                        choice_idx = int(sw_choice_input) - 1
                        if 0 <= choice_idx < len(self.available_softwares):
                            self.selected_software_id = self.available_softwares[choice_idx]['software_id']
                        else:
                            print(Colors.warning("Invalid selection."))
                            self.current_task_description = None; continue
                    except ValueError:
                        print(Colors.warning("Invalid input. Please enter a number."))
                        self.current_task_description = None; continue

                    if self.selected_software_id:
                        print(Colors.info(f"Selected software ID: {Colors.BOLD}{self.selected_software_id}{Colors.RESET}"))
                        print(Colors.info(f"\n{Colors.BOLD}--> Requesting initial capabilities for '{self.selected_software_id}'...{Colors.RESET}"))
                        await self.ws_client.send_message({
                            "type": "REQUEST_SOFTWARE_CAPABILITIES",
                            "payload": {"software_id": self.selected_software_id}
                        })
                        self.is_waiting_for_llm = True # Now waiting for capabilities response then LLM planning
                    else: # Should not happen if selection logic is correct
                        self.current_task_description = None

                await asyncio.sleep(0.1) # Main loop yield
        except KeyboardInterrupt:
            print(Colors.warning("\nUser interrupted. Exiting..."))
        except Exception as e:
            print(Colors.error(f"An unexpected error occurred in CLI main loop: {type(e).__name__} - {e}"))
            import traceback
            traceback.print_exc()
        finally:
            if self.ws_client.is_connected():
                await self.ws_client.disconnect()
            print(Colors.info("AI Agent CLI stopped."))

if __name__ == "__main__":
    cli = AIAgentCLI()
    asyncio.run(cli.run())