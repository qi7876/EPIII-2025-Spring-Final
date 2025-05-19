# intermediary_server/message_models.py
from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field

class SoftwareInfo(BaseModel):
    software_id: str = Field(..., description="软件的唯一ID")
    name: str = Field(..., description="软件名称")
    description: str = Field(..., description="软件功能简介")
    keywords: List[str] = Field(default_factory=list, description="描述软件功能的关键词列表")

class BaseMessage(BaseModel):
    type: str # 消息类型

# --- 软件客户端 -> 服务器 ---
class IdentifySoftwareMessage(BaseMessage):
    type: Literal["IDENTIFY_SOFTWARE"] = "IDENTIFY_SOFTWARE"
    payload: SoftwareInfo

class RegisterSoftwareMessage(BaseMessage): # 其实IdentifySoftwareMessage已经包含了注册信息
    type: Literal["REGISTER_SOFTWARE"] = "REGISTER_SOFTWARE" # 可以考虑合并或区分
    payload: SoftwareInfo

# --- 服务器 -> 软件客户端 ---
class RegistrationAckMessage(BaseMessage):
    type: Literal["REGISTRATION_ACK"] = "REGISTRATION_ACK"
    payload: Dict[str, Any] = Field(default_factory=lambda: {"status": "success", "message": "Software registered successfully."})

# --- AI 代理 -> 服务器 ---
class IdentifyAgentMessage(BaseMessage):
    type: Literal["IDENTIFY_AGENT"] = "IDENTIFY_AGENT"
    # agent_id: Optional[str] = None # 如果需要区分多个AI代理实例

class RequestSoftwareListMessage(BaseMessage):
    type: Literal["REQUEST_SOFTWARE_LIST"] = "REQUEST_SOFTWARE_LIST"

# --- 服务器 -> AI 代理 ---
class SoftwareListResponseMessage(BaseMessage):
    type: Literal["SOFTWARE_LIST_RESPONSE"] = "SOFTWARE_LIST_RESPONSE"
    payload: List[SoftwareInfo]


# --- AI 代理 -> 服务器 (转发给软件) ---
class RequestSoftwareCapabilitiesMessage(BaseMessage):
    type: Literal["REQUEST_SOFTWARE_CAPABILITIES"] = "REQUEST_SOFTWARE_CAPABILITIES"
    payload: Dict[str, str] = Field(..., description="{'software_id': 'target_software_id'}")

# --- 软件 -> 服务器 (转发给AI) ---
class SoftwareCapabilities(BaseModel):
    current_view: str
    elements: List[Dict[str, Any]] # 简化表示，具体结构可进一步定义

class SoftwareCapabilitiesResponseMessage(BaseMessage):
    type: Literal["SOFTWARE_CAPABILITIES_RESPONSE"] = "SOFTWARE_CAPABILITIES_RESPONSE"
    payload: SoftwareCapabilities
    software_id: str # 标记是哪个软件的capabilities

# --- AI 代理 -> 服务器 (转发给软件) ---
class Action(BaseModel):
    command: str
    element_id: Optional[str] = None
    text: Optional[str] = None
    description: Optional[str] = None

class SolutionPlan(BaseModel):
    actions: List[Action]

class ExecuteSolutionPlanMessage(BaseMessage):
    type: Literal["EXECUTE_SOLUTION_PLAN"] = "EXECUTE_SOLUTION_PLAN"
    payload: Dict[str, Any] = Field(..., description="{'software_id': 'target_software_id', 'solution': SolutionPlan}")

# --- 软件 -> 服务器 (转发给AI) ---
class ActionStatusUpdateMessage(BaseMessage):
    type: Literal["ACTION_STATUS_UPDATE"] = "ACTION_STATUS_UPDATE"
    payload: Dict[str, Any] = Field(..., description="{'software_id': ..., 'action_index_completed': ..., 'status': ..., 'message': ..., 'current_capabilities': ...}")

# --- 软件 -> 服务器 (转发给AI) ---
class FormField(BaseModel):
    id: str
    label: str
    type: str # e.g., "text", "select", "number"
    options: Optional[List[str]] = None
    default: Optional[Any] = None

class FormRequestPayload(BaseModel):
    software_id: str
    form_description: str
    fields: List[FormField]

class FormRequestMessage(BaseMessage):
    type: Literal["FORM_REQUEST"] = "FORM_REQUEST"
    payload: FormRequestPayload

# --- AI 代理 -> 服务器 (转发给软件) ---
class FormDataResponsePayload(BaseModel):
    software_id: str
    form_data: Dict[str, Any]

class FormDataResponseMessage(BaseMessage):
    type: Literal["FORM_DATA_RESPONSE"] = "FORM_DATA_RESPONSE"
    payload: FormDataResponsePayload

# 用于解析传入的通用消息，判断其具体类型
class GenericMessage(BaseModel):
    type: str
    payload: Optional[Dict[str, Any]] = None
    software_id: Optional[str] = None # 有些消息可能需要这个顶层字段