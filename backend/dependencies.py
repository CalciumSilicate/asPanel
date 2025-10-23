from backend.core.constants import PYTHON_EXECUTABLE

from backend.services.mcdr_manager import MCDRManager
from backend.services.archive_manager import ArchiveManager
from backend.services.server_service import ServerService
from backend.services.task_manager import TaskManager
from backend.services.plugin_manager import PluginManager
from backend.services.dependency_handler import DependencyHandler

mcdr_manager = MCDRManager()
archive_manager = ArchiveManager()
dependency_handler = DependencyHandler(PYTHON_EXECUTABLE)
plugin_manager = PluginManager(dependency_handler)
server_service = ServerService(mcdr_manager, plugin_manager)
task_manager = TaskManager()

mcdr_manager.set_server_service(server_service)
