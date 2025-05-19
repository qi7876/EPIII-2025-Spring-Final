# intermediary_server/software_registry.py
from typing import Dict, List, Optional
from .message_models import SoftwareInfo

class SoftwareRegistry:
    def __init__(self):
        self._registered_softwares: Dict[str, SoftwareInfo] = {}

    def register_software(self, software_info: SoftwareInfo) -> bool:
        if software_info.software_id in self._registered_softwares:
            print(f"Software with ID '{software_info.software_id}' already registered. Updating info.")
        self._registered_softwares[software_info.software_id] = software_info
        print(f"Software '{software_info.name}' (ID: {software_info.software_id}) registered.")
        return True

    def unregister_software(self, software_id: str) -> bool:
        if software_id in self._registered_softwares:
            del self._registered_softwares[software_id]
            print(f"Software with ID '{software_id}' unregistered.")
            return True
        return False

    def get_software_info(self, software_id: str) -> Optional[SoftwareInfo]:
        return self._registered_softwares.get(software_id)

    def list_all_software(self) -> List[SoftwareInfo]:
        return list(self._registered_softwares.values())

# 单例模式，方便在 FastAPI 中使用
software_registry_instance = SoftwareRegistry()