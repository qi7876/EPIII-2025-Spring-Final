# ai_agent/llm_handler.py
from openai import OpenAI
from . import agent_config
import json
from typing import Optional, Any
import asyncio # Added import
import sys     # Added import

class LLMHandler:
    def __init__(self):
        self.client = OpenAI(
            api_key=agent_config.LLM_API_KEY,
            base_url=agent_config.LLM_BASE_URL,
        )
        self.model = agent_config.LLM_MODEL
        self.conversation_history = [] # 用于存储多轮对话

    def add_message_to_history(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})

    def clear_history(self):
        self.conversation_history = []

    async def _spinner(self, stop_event: asyncio.Event, message: str):
        """Helper coroutine to display a CLI spinner."""
        animation_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        idx = 0
        # Start on a new line for the spinner message
        sys.stdout.write("\n") 
        sys.stdout.flush()
        
        try:
            while not stop_event.is_set():
                char = animation_chars[idx % len(animation_chars)]
                # \r to return to beginning of line, then print char and message
                sys.stdout.write(f"\r{char} {message}")
                sys.stdout.flush()
                idx += 1
                try:
                    # Wait for 0.1s or until stop_event is set
                    await asyncio.wait_for(stop_event.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass # Timeout means event not set, continue animation
        except asyncio.CancelledError:
            # If the spinner task is cancelled, re-raise after cleanup.
            raise
        finally:
            # Cleanup: Clear the spinner line
            # Ensure enough spaces to cover the message and spinner character
            sys.stdout.write("\r" + " " * (len(message) + 2) + "\r")
            sys.stdout.flush()

    async def get_llm_response(self, user_prompt: str, system_prompt: Optional[str] = None, expect_json: bool = False) -> Any:
        """
        获取LLM的响应。

        :param user_prompt: 用户的当前输入。
        :param system_prompt: （可选）系统级指令。如果提供，会作为对话的第一条消息。
        :param expect_json: 是否期望LLM输出JSON格式。
        :return: LLM的响应内容，如果是JSON则解析后的Python对象，否则是字符串。
        """
        messages_for_llm = []
        if system_prompt:
            messages_for_llm.append({"role": "system", "content": system_prompt})

        # 添加当前对话历史（如果存在）
        messages_for_llm.extend(self.conversation_history)
        # 添加最新的用户输入
        messages_for_llm.append({"role": "user", "content": user_prompt})

        spinner_message = f"Sending to LLM ({self.model})..."
        stop_spinner_event = asyncio.Event()
        spinner_task = asyncio.create_task(self._spinner(stop_spinner_event, spinner_message))

        llm_reply_content = None
        api_response = None

        try:
            # The original print statement is now handled by the spinner:
            # print(f"\nSending to LLM ({self.model}):")
            # The commented-out message dump:
            # for msg in messages_for_llm:
            #     print(f"  Role: {msg['role']}, Content: {msg['content'][:100]}...")

            response_format_param = {'type': 'json_object'} if expect_json else None

            # Run the blocking OpenAI API call in a separate thread
            api_response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages_for_llm,
                response_format=response_format_param,
                temperature=0
            )
            llm_reply_content = api_response.choices[0].message.content

        except Exception as e:
            # Ensure spinner stops and cleans up before printing error
            if not stop_spinner_event.is_set():
                stop_spinner_event.set()
            try:
                await spinner_task
            except asyncio.CancelledError: # Propagate if outer task cancelled
                raise
            
            # Print error after spinner is gone
            # Ensure error message starts on a new line if spinner cleared the current one
            sys.stdout.write("\n") # Ensure new line after spinner clears
            sys.stdout.flush()
            print(f"Error calling LLM API: {e}")
            return {"error": f"LLM API call failed: {e}"} if expect_json else f"Error: LLM API call failed: {e}"
        finally:
            # This finally block ensures the spinner is always stopped and awaited.
            if not stop_spinner_event.is_set():
                stop_spinner_event.set()
            try:
                await spinner_task
            except asyncio.CancelledError: # Propagate if outer task cancelled
                # The spinner's own finally block should handle its line clearing.
                raise
        
        # If successful, process the response
        # 将LLM的回复也加入历史，以便进行多轮对话
        self.add_message_to_history("user", user_prompt) # 用户的原始输入
        self.add_message_to_history("assistant", llm_reply_content) # LLM的回复

        if expect_json:
            try:
                return json.loads(llm_reply_content)
            except json.JSONDecodeError:
                # This print should not interfere with the cleared spinner line.
                # It will print on a new line after the spinner is gone.
                sys.stdout.write("\n") # Ensure new line
                sys.stdout.flush()
                print(f"LLM did not return valid JSON: {llm_reply_content}")
                return {"error": "LLM did not return valid JSON", "raw_response": llm_reply_content}
        else:
            return llm_reply_content

    # --- 后续会添加更具体的LLM调用方法 ---
    async def select_software_and_generate_plan(self, user_requirement: str, available_softwares: list):
        # TODO: 构建prompt，让LLM从available_softwares中选择一个，并初步规划操作
        # 这里的available_softwares应该是从服务器获取的软件信息列表
        print(f"LLM: Received user requirement: '{user_requirement}'")
        print(f"LLM: Available softwares: {available_softwares}")
        # 这是一个占位符实现
        if not available_softwares:
            return None, "No software available to handle the request."

        # 简化：暂时手动选择第一个软件，并生成一个假计划
        selected_software = available_softwares[0]
        fake_plan = {
            "actions": [
                {"command": "CLICK", "element_id": "some_button", "description": "Click a button (fake plan)"}
            ]
        }
        print(f"LLM: (Fake) Selected software: {selected_software['name']}, Plan: {fake_plan}")
        return selected_software['software_id'], fake_plan

# 单例
llm_handler_instance = LLMHandler()