# backend/services/plugin_manager.py

import ast
import json
import os
import shutil
import zipfile
import httpx
from fastapi import UploadFile, HTTPException, status
from typing import Dict, Tuple, Any, Optional, Set
from pathlib import Path

from backend.core import schemas
from backend.core.constants import UPLOADED_PLUGINS_PATH, TEMP_PATH
from backend.core.utils import get_file_md5, get_file_sha256, get_size_bytes
from backend.core.schemas import ServerPluginType
from backend.core.logger import logger
from backend.services.dependency_handler import DependencyHandler


class PluginManager:
    def __init__(self, dependency_handler: DependencyHandler):
        # 确保上传插件的存储目录存在
        UPLOADED_PLUGINS_PATH.mkdir(parents=True, exist_ok=True)
        TEMP_PATH.mkdir(parents=True, exist_ok=True)
        self.dependency_handler = dependency_handler

    @staticmethod
    def read_meta(fp: str | Path, plugin_type: ServerPluginType) -> Tuple[bool, Dict[str, Any]]:
        # ... (此部分代码保持不变，已经很完善)
        path = Path(fp)
        try:
            if plugin_type in (ServerPluginType.MCDR, ServerPluginType.PYZ):
                return PluginManager._read_meta_from_zip(path)
            elif plugin_type is ServerPluginType.FOLDER:
                return PluginManager._read_meta_from_folder(path)
            elif plugin_type is ServerPluginType.PY:
                return PluginManager._read_meta_from_py(path)
            else:
                return False, {}
        except Exception:
            # 任何异常都视为读取失败
            return False, {}

    @staticmethod
    def get_plugin_info(fp: Path) -> schemas.ServerPlugin:
        # ... (此部分代码保持不变，已经很完善)
        is_dir = fp.is_dir()
        file_name = fp.name
        path = fp.parent.absolute() / fp.name
        size = get_size_bytes(fp)
        enabled = not fp.name.endswith(".disabled")

        if not is_dir:
            ext = Path(fp.name.replace(".disabled", "")).suffix
            # 修正：保证 .pyz 也能被正确识别
            file_type_str = ext.upper().replace(".", "")
            if file_type_str == "DISABLED":  # 如果文件是 .py.disabled
                file_type_str = Path(fp.name.replace(".disabled", "")).suffix.upper().replace(".", "")

            hash_md5 = get_file_md5(path)
            hash_sha256 = get_file_sha256(path)
        else:
            file_type_str = "FOLDER"
            hash_md5 = None
            hash_sha256 = None

        try:
            file_type = ServerPluginType(file_type_str)
        except ValueError:
            # 对于未知类型，可以标记为 FOLDER 或其他默认值
            file_type = ServerPluginType.FOLDER if is_dir else ServerPluginType.MCDR  # 兜底

        read_meta_ok, meta = PluginManager.read_meta(fp, file_type)
        return schemas.ServerPlugin(
            file_name=file_name,
            path=str(path),
            type=file_type,
            size=size,
            meta=meta,
            enabled=enabled,
            hash_md5=hash_md5,
            hash_sha256=hash_sha256,
            read_meta_ok=read_meta_ok
        )

    @staticmethod
    def get_plugins_info(fp: Path) -> schemas.ServerPlugins:
        # ... (此部分代码保持不变)
        ls = os.listdir(fp)
        if "__pycache__" in ls:
            ls.remove("__pycache__")
        return schemas.ServerPlugins(
            data=list(sorted([PluginManager.get_plugin_info(fp / f) for f in ls],
                             key=lambda x: x.file_name)) if fp.is_dir() else []
        )

    # --- 新增的插件操作方法 ---

    @staticmethod
    async def install_from_url(server_path: Path, download_url: str, file_name: str) -> Path:
        """从 URL 下载插件并安装到指定服务器的插件目录"""
        plugins_dir = server_path / 'plugins'
        plugins_dir.mkdir(exist_ok=True)
        target_path = plugins_dir / file_name

        temp_download_path = TEMP_PATH / f"{os.urandom(8).hex()}_{file_name}"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("GET", download_url, follow_redirects=True) as response:
                    response.raise_for_status()
                    with open(temp_download_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)

            shutil.move(temp_download_path, target_path)
            PluginManager._cleanup_old_versions(plugins_dir, target_path)
            return target_path
        except httpx.HTTPError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Download failed: {e}")
        except OSError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Failed to save plugin file: {e}")
        finally:
            if temp_download_path.exists():
                os.remove(temp_download_path)

    @staticmethod
    def install_from_local_path(server_path: Path, source_path: Path, file_name: str) -> Path:
        """从本地路径复制插件到服务器插件目录"""
        plugins_dir = server_path / 'plugins'
        plugins_dir.mkdir(exist_ok=True)
        target_path = plugins_dir / file_name

        try:
            shutil.copy2(source_path, target_path)
            PluginManager._cleanup_old_versions(plugins_dir, target_path)
            return target_path
        except OSError as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to copy plugin: {e}")

    @staticmethod
    async def save_uploaded_plugin(file: UploadFile) -> Tuple[Path, Dict[str, Any]]:
        """保存上传的插件文件到中央仓库，并返回路径和元数据"""
        # 防止恶意文件名
        filename = "".join(c for c in file.filename if c.isalnum() or c in "._-").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid file name")

        # 使用 hash 避免文件名冲突
        content = await file.read()
        file_hash = get_file_md5(content)
        file_extension = Path(filename).suffix
        storage_filename = f"{file_hash}{file_extension}"
        storage_path = UPLOADED_PLUGINS_PATH / storage_filename

        try:
            with open(storage_path, "wb") as f:
                f.write(content)

            meta = {}
            if storage_path.suffix.lower() in ['.mcdr', '.pyz', '.zip']:
                _, meta = PluginManager._read_meta_from_zip(storage_path)
            elif storage_path.suffix.lower() == '.py':
                _, meta = PluginManager._read_meta_from_py(storage_path)

            return storage_path, meta
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    @staticmethod
    def switch_plugin(server_path: Path, file_name: str, enable: Optional[bool] = None) -> Tuple[Path, bool]:
        """启用、禁用或切换插件的状态 (.disabled 后缀)"""
        plugins_dir = server_path / 'plugins'

        path = plugins_dir / file_name
        if not path.exists():
            path = plugins_dir / file_name.replace(".disabled", "")
            if not path.exists():
                path = plugins_dir / (file_name + ".disabled")
                if not path.exists():
                    raise HTTPException(status_code=404, detail=f"Plugin file '{file_name}' not found.")

        is_currently_enabled = not path.name.endswith('.disabled')

        if enable is None:
            # 切换状态
            enable = not is_currently_enabled

        if enable and not is_currently_enabled:
            # 启用
            target_name = path.name.removesuffix('.disabled')
            target_path = path.with_name(target_name)
            path.rename(target_path)
            return target_path, True
        elif not enable and is_currently_enabled:
            # 禁用
            target_name = path.name + '.disabled'
            target_path = path.with_name(target_name)
            path.rename(target_path)
            return target_path, False

        # 状态无需改变
        return path, is_currently_enabled

    @staticmethod
    def delete_plugin(server_path: Path, file_name: str):
        """从服务器的插件目录中删除一个插件"""
        plugins_dir = server_path / 'plugins'
        target_path = plugins_dir / file_name

        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Plugin file '{file_name}' not found.")

        try:
            if target_path.is_dir():
                shutil.rmtree(target_path)
            else:
                os.remove(target_path)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plugin file: {e}")

    # --- 静态私有方法 _read_meta... 保持不变 ---

    @staticmethod
    def _cleanup_old_versions(plugins_dir: Path, newly_installed_path: Path):
        """
        根据新安装插件的 plugin_id，查找并删除该插件目录下的所有旧版本。
        """
        try:
            # 1. 获取新安装插件的 plugin_id
            new_plugin_info = PluginManager.get_plugin_info(newly_installed_path)
            new_plugin_id = new_plugin_info.meta.get("id")
            if not new_plugin_id:
                logger.warning(
                    f"无法从 {newly_installed_path.name} 读取 plugin ID，跳过旧版本清理。")
                return
            logger.info(f"正在为插件 ID '{new_plugin_id}' 清理旧版本...")
            # 2. 遍历插件目录中的所有项目
            for item in plugins_dir.iterdir():
                # 跳过我们刚刚安装的文件
                if item.resolve() == newly_installed_path.resolve():
                    continue
                try:
                    # 3. 获取其他插件的 plugin_id
                    old_plugin_info = PluginManager.get_plugin_info(item)
                    old_plugin_id = old_plugin_info.meta.get("id")
                    # 4. 如果 id 匹配，则删除旧插件
                    if old_plugin_id == new_plugin_id:
                        logger.info(f"找到并删除旧版本: {item.name}")
                        if item.is_dir():
                            shutil.rmtree(item)
                        else:
                            os.remove(item)
                except Exception:
                    # 读取其他插件元数据失败是正常的，静默跳过
                    pass
        except Exception as e:
            # 确保清理过程中的任何异常都不会中断整个安装流程
            logger.error(f"清理插件旧版本时发生意外错误: {e}", exc_info=True)

    @staticmethod
    def _read_meta_from_zip(path: Path) -> Tuple[bool, Dict[str, Any]]:
        # ... (代码不变)
        if not path.is_file():
            return False, {}
        try:
            with zipfile.ZipFile(path, "r") as zf:
                # 寻找以 mcdreforged.plugin.json 结尾的文件
                candidates = [n for n in zf.namelist() if n.endswith("mcdreforged.plugin.json")]
                if not candidates:
                    return False, {}
                # 取路径层级最短的那个（更可能是顶层 Plugin/mcdreforged.plugin.json）
                target = sorted(candidates, key=lambda s: (s.count("/"), len(s)))[0]
                with zf.open(target) as f:
                    data = f.read().decode("utf-8", errors="replace")
                meta = json.loads(data)
                if isinstance(meta, dict):
                    return True, meta
                return False, {}
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError, OSError, UnicodeDecodeError):
            return False, {}

    @staticmethod
    def _read_meta_from_folder(path: Path) -> Tuple[bool, Dict[str, Any]]:
        # ... (代码不变)
        if not path.is_dir():
            return False, {}
        # 优先直接在根目录找
        meta_path = path / "mcdreforged.plugin.json"
        if meta_path.is_file():
            return PluginManager._load_json_file(meta_path)

        # 兜底：只在第一层子目录里找一次（兼容 Plugin/mcdreforged.plugin.json）
        try:
            for child in path.iterdir():
                if child.is_dir():
                    p = child / "mcdreforged.plugin.json"
                    if p.is_file():
                        return PluginManager._load_json_file(p)
        except OSError:
            pass
        return False, {}

    @staticmethod
    def _read_meta_from_py(path: Path) -> Tuple[bool, Dict[str, Any]]:
        # ... (代码不变)
        if not path.is_file():
            return False, {}
        try:
            src = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src, filename=str(path))
            meta_node: Optional[ast.AST] = None

            # 寻找形如 PLUGIN_METADATA = {...} 的顶层赋值
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "PLUGIN_METADATA":
                            meta_node = node.value
                            break
                elif isinstance(node, ast.AnnAssign):
                    # 支持类型注解赋值：PLUGIN_METADATA: Dict[str, Any] = {...}
                    if (isinstance(node.target, ast.Name) and node.target.id == "PLUGIN_METADATA"
                            and node.value is not None):
                        meta_node = node.value
                if meta_node is not None:
                    break

            if meta_node is None:
                return False, {}

            meta = ast.literal_eval(meta_node)  # 只允许字面量
            if isinstance(meta, dict):
                return True, meta
            return False, {}
        except (SyntaxError, ValueError, UnicodeDecodeError, OSError):
            return False, {}

    @staticmethod
    def _load_json_file(p: Path) -> Tuple[bool, Dict[str, Any]]:
        # ... (代码不变)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            data = json.loads(text)
            return (True, data) if isinstance(data, dict) else (False, {})
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False, {}

    # 这是一个辅助函数，将在 plugin_manager 中被调用
    async def process_installation_task(
            self,
            server_id: int,
            plugin_id: str,
            tag_name: str,
            # 传递依赖注入的函数或类实例
            mcdr_plugins_catalogue: schemas.PluginCatalogue,
            get_server_by_id_func,
            db_session_factory
    ):
        """
        完整的后台安装任务，包括递归依赖处理。
        """
        from collections import deque
        db = db_session_factory()
        try:
            server = get_server_by_id_func(db, server_id)
            install_queue = deque([(plugin_id, tag_name)])
            processed_plugins: Set[str] = set()

            logger.info(f"开始为服务器 {server.name} 安装插件 {plugin_id} 及其依赖...")

            while install_queue:
                current_plugin_id, current_tag = install_queue.popleft()
                if current_plugin_id in processed_plugins:
                    continue

                logger.info(f"处理插件: {current_plugin_id}")

                plugin_info = mcdr_plugins_catalogue.plugins.get(current_plugin_id)
                if not plugin_info:
                    logger.error(f"插件 '{current_plugin_id}' 在市场中未找到，跳过。")
                    continue

                # 查找目标版本
                release_info = plugin_info.release
                target_release = next((r for r in release_info.releases if r.meta.version == current_tag),
                                      None) if current_tag != "latest" else next(
                    (r for r in release_info.releases if r.meta.version == release_info.latest_version), None)

                if not target_release or not target_release.asset:
                    logger.error(f"找不到插件 '{current_plugin_id}' 版本 '{current_tag}' 的可下载文件。")
                    continue

                # 1. 安装插件本体
                logger.info(f"正在下载并安装 {target_release.asset.name}...")
                await PluginManager.install_from_url(
                    server_path=Path(server.path),
                    download_url=target_release.asset.browser_download_url,
                    file_name=target_release.asset.name
                )
                processed_plugins.add(current_plugin_id)

                # 2. 处理 Python 依赖
                if target_release.meta and target_release.meta.requirements:
                    logger.info(
                        f"正在为 {current_plugin_id} 安装 Python requirements: {target_release.meta.requirements}")
                    await self.dependency_handler.install_python_requirements(target_release.meta.requirements)

                # 3. 处理 MCDR 插件依赖
                if target_release.meta and target_release.meta.dependencies:
                    logger.info(f"正在处理 {current_plugin_id} 的 MCDR 依赖: {target_release.meta.dependencies}")
                    for dep_id, dep_specifier in target_release.meta.dependencies.items():
                        if dep_id == "mcdreforged":
                            if not await self.dependency_handler.check_mcdreforged_version(dep_specifier):
                                # 如果版本不匹配，可以选择是中止还是仅警告
                                raise RuntimeError(f"MCDReforged 版本不满足 '{current_plugin_id}' 的要求!")
                        elif dep_id not in processed_plugins:
                            # 对于插件依赖，我们总是尝试安装最新版，因为解析版本范围并从市场找到匹配版本非常复杂
                            # 这是一个简化的、但通常有效的策略
                            install_queue.append((dep_id, "latest"))

            logger.info(f"插件 {plugin_id} 及其所有依赖项已成功安装到服务器 {server.name}。")

        except Exception as e:
            raise e
            logger.error(f"为服务器 {server_id} 安装插件 {plugin_id} 时发生严重错误: {e}", exc_info=True)
        finally:
            db.close()
