# backend/core/dependencies.py

from backend.core.constants import PYTHON_EXECUTABLE
from backend.services.mcdr_manager import MCDRManager
from backend.services.archive_manager import ArchiveManager
from backend.services.server_service import ServerService
from backend.services.task_manager import TaskManager
from backend.services.plugin_manager import PluginManager
from backend.services.dependency_handler import DependencyHandler
from backend.services.mod_manager import ModManager

mcdr_manager = MCDRManager()
archive_manager = ArchiveManager()
dependency_handler = DependencyHandler(PYTHON_EXECUTABLE)
plugin_manager = PluginManager(dependency_handler)
task_manager = TaskManager()
mod_manager = ModManager()
server_service = ServerService(mcdr_manager, plugin_manager, mod_manager)

mcdr_manager.set_server_service(server_service)
