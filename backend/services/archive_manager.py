# archive_manager.py

import os
import shutil
import tarfile
from pathlib import Path
import uuid

from backend.core.config import ARCHIVE_STORAGE_PATH
from backend import server_parser


class ArchiveManager:
    """处理与服务器存档相关的操作"""

    def __init__(self):
        self.storage_path = Path(ARCHIVE_STORAGE_PATH)
        self.storage_path.mkdir(exist_ok=True)

    @staticmethod
    def get_path_size(path: Path) -> int:
        """计算文件或目录的总大小 (以字节为单位)"""
        if path.is_file():
            return path.stat().st_size
        elif path.is_dir():
            total_size = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if not os.path.islink(fp):
                        total_size += os.path.getsize(fp)
            return total_size
        return 0

    def create_tar_from_server_world(self, server_path: str, world_name: str, task_id: str) -> Path:
        """从服务器世界文件夹创建 .tar.gz 存档"""
        source_world_path = Path(server_path) / "server" / world_name
        if not source_world_path.is_dir():
            raise FileNotFoundError(f"世界文件夹 '{source_world_path}' 不存在")

        archive_filename = f"{task_id}.tar.gz"
        archive_path = self.storage_path / archive_filename

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(source_world_path, arcname=world_name)

        return archive_path

    def process_uploaded_archive(self, temp_file_path: Path, archive_name: str) -> Path:
        """
        [重构] 处理上传的存档。
        新逻辑会解压到临时位置，找到真正的世界文件夹（含level.dat），
        然后将其移动到永久存储位置，确保存档结构的正确性。
        """
        # 1. 为最终的、正确的存档目录创建一个唯一的路径
        final_world_path = self.storage_path / f"{archive_name}_{uuid.uuid4().hex[:8]}"
        # 2. 为解压过程创建一个临时的、一次性的目录
        temp_extract_dir = self.storage_path / f"temp_extract_{uuid.uuid4().hex[:8]}"
        temp_extract_dir.mkdir()
        try:
            # 3. 将上传的压缩包解压到临时目录
            shutil.unpack_archive(temp_file_path, temp_extract_dir)
            # 4. 在临时目录中查找真正的世界文件夹 (包含 level.dat)
            found_world_dir = None
            # 检查 level.dat 是否在解压后的根目录
            if (temp_extract_dir / 'level.dat').is_file():
                found_world_dir = temp_extract_dir
            else:
                # 如果不在根目录，则在第一层子目录中查找
                for item in temp_extract_dir.iterdir():
                    if item.is_dir() and (item / 'level.dat').is_file():
                        found_world_dir = item
                        break  # 找到后立即停止搜索
            if not found_world_dir:
                raise ValueError("上传的存档中未找到有效的世界文件夹 (缺少 level.dat)。")
            # 5. 将找到的真实世界文件夹移动到最终的目标位置
            # shutil.move 会自动处理重命名
            shutil.move(str(found_world_dir), str(final_world_path))
            return final_world_path
        except Exception as e:
            # 如果过程中出现任何错误，确保清理所有创建的目录
            shutil.rmtree(final_world_path, ignore_errors=True)
            raise IOError(f"处理上传的存档时出错: {e}")
        finally:
            # 6. 无论成功与否，都清理临时上传文件和临时解压目录
            if temp_file_path.exists():
                os.remove(temp_file_path)
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir, ignore_errors=True)

    def download_archive(self, archive_path: Path) -> Path:
        """为下载准备任何类型的存档文件"""
        if not archive_path.exists():
            raise FileNotFoundError("存档文件或目录不存在")

        if archive_path.is_file() and archive_path.name.endswith('.tar.gz'):
            # 对于 .tar.gz 文件，直接返回路径
            return archive_path
        elif archive_path.is_dir():
            # 对于目录，将其压缩成临时的 .tar.gz 文件
            temp_tar_name = self.storage_path / f"download_{uuid.uuid4().hex}.tar.gz"
            with tarfile.open(temp_tar_name, "w:gz") as tar:
                tar.add(archive_path, arcname=archive_path.name)
            return temp_tar_name
        else:
            raise ValueError("不支持的存档类型或文件格式")

    @staticmethod
    def restore_archive(archive_path: Path, server_path: Path):
        """将任何类型的存档恢复到指定的服务器世界目录"""
        if not server_path.is_dir():
            raise FileNotFoundError(f"目标服务器路径 '{server_path}' 不存在")

        # 从服务器配置中获取世界名称
        server_properties_path = server_path / 'server' / 'server.properties'
        if not server_properties_path.exists():
            raise FileNotFoundError("在目标服务器中找不到 server.properties")

        properties = server_parser.parse_properties(str(server_properties_path))
        world_name = properties.get("level-name", "world")
        target_world_path = server_path / 'server' / world_name

        # 删除现有的世界文件夹
        if target_world_path.exists():
            shutil.rmtree(target_world_path)

        # 开始恢复
        if archive_path.is_dir():
            # 如果存档是解压的目录，直接复制
            shutil.copytree(archive_path, target_world_path)
        elif archive_path.is_file() and archive_path.name.endswith('.tar.gz'):
            # 如果是 .tar.gz 文件，解压到目标位置
            with tarfile.open(archive_path, 'r:gz') as tar:
                # 为了安全，逐个成员地提取
                for member in tar.getmembers():
                    # 移除路径中的任何 '..' 或绝对路径，以防止路径遍历攻击
                    member_path = os.path.normpath(member.name)
                    if member_path.startswith(('..', '/', '\\')):
                        continue  # 跳过不安全的路径

                    # 确保解压到正确的顶级目录
                    # tar 存档中的根目录应该是 'world' 或类似的名称
                    # 我们希望它在 target_world_path 下解压
                    # shutil.unpack_archive 更简单，处理多种情况
                    pass  # 使用下面的 unpack_archive

            # 使用 shutil.unpack_archive 更安全、更简单
            shutil.unpack_archive(archive_path, server_path / 'server')

            # 解压后，存档的根目录可能与 world_name 不同
            # 我们需要找到它并重命名为正确的 world_name
            unpacked_root = None
            with tarfile.open(archive_path, 'r:gz') as tar:
                # 假设存档中只有一个顶级目录
                top_level_dirs = {p.split('/')[0] for p in tar.getnames()}
                if len(top_level_dirs) == 1:
                    unpacked_root = server_path / 'server' / list(top_level_dirs)[0]

            if unpacked_root and unpacked_root.exists() and unpacked_root.name != world_name:
                unpacked_root.rename(target_world_path)
        else:
            raise ValueError("不支持的存档文件格式，无法恢复")
