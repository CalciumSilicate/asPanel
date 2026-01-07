# backend/services/dependency_handler.py

import asyncio
import re
from typing import List
from packaging.specifiers import SpecifierSet
from packaging.version import Version, InvalidVersion
from packaging.requirements import Requirement, InvalidRequirement

from backend.core.logger import logger

# 设置一个简单的日志记录器

class DependencyHandler:
    def __init__(self, python_executable: str):
        self.python_executable = python_executable

    async def _run_pip_command(self, *args) -> tuple[bool, str, str]:
        """异步执行 pip 命令并返回结果"""
        command = [self.python_executable, "-m", "pip", *args]
        logger.info(f"执行命令: {' '.join(command)}")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode('utf-8', errors='replace').strip()
        stderr_str = stderr.decode('utf-8', errors='replace').strip()

        if process.returncode == 0:
            logger.info(f"命令成功: {stdout_str[:200]}...")
            return True, stdout_str, stderr_str
        else:
            logger.error(f"命令失败 (code {process.returncode}): {stderr_str}")
            return False, stdout_str, stderr_str

    async def get_installed_version(self, package_name: str) -> Version | None:
        """获取已安装的 pypi 包版本"""
        success, stdout, _ = await self._run_pip_command("show", package_name)
        if success:
            match = re.search(r"^Version:\s*([^\s]+)", stdout, re.MULTILINE)
            if match:
                try:
                    return Version(match.group(1))
                except InvalidVersion:
                    return None
        return None

    async def check_mcdreforged_version(self, specifier_str: str) -> bool:
        """检查当前 mcdreforged 版本是否满足要求"""
        installed_version = await self.get_installed_version("mcdreforged")
        if not installed_version:
            logger.warning("未找到 mcdreforged。假定不满足版本要求。")
            return False
        
        # 清理非标准版本说明符（如 ">=2.0.0-" 末尾的 "-"）
        cleaned_specifier = specifier_str.rstrip('-')
        try:
            specifier = SpecifierSet(cleaned_specifier, prereleases=True)
        except Exception as e:
            logger.warning(f"无法解析版本说明符 '{specifier_str}'，跳过检查: {e}")
            return True
        
        is_ok = installed_version in specifier
        if not is_ok:
            logger.error(f"MCDReforged 版本不匹配！要求: '{specifier_str}', 已安装: '{installed_version}'")
        else:
            logger.info(f"MCDReforged 版本检查通过。要求: '{specifier_str}', 已安装: '{installed_version}'")
        return is_ok

    async def install_python_requirements(self, requirements: List[str]):
        """
        验证并安装指定的 python requirements 列表。
        使用 `packaging` 库来确保格式的正确性和安全性。
        """
        if not requirements:
            logger.debug("没有需要安装的 python requirements。")
            return
        valid_requirements = []
        for req_str in requirements:
            try:
                # 尝试将字符串解析为一个 Requirement 对象。
                # 如果成功，说明这是一个语法有效的需求说明符。
                Requirement(req_str)
                valid_requirements.append(req_str)
            except InvalidRequirement:
                # 如果解析失败，记录一个警告并跳过这个无效的需求。
                logger.warning(f"检测到无效或格式不正确的 requirement，已忽略: '{req_str}'")
        if not valid_requirements:
            logger.info("所有提供的 requirements 均无效或已被处理，无需安装。")
            return
        logger.info(f"正在准备安装以下有效 requirements: {valid_requirements}")
        # 将所有有效的 requirements 一次性传递给 pip install
        # 每个 requirement 都是独立的参数，这能防止 shell 注入
        success, stdout, stderr = await self._run_pip_command("install", *valid_requirements)
        if not success:
            # 在错误日志中同时记录 stdout 和 stderr，以便于排查问题
            error_message = f"Pip install failed.\n- STDERR: {stderr}\n- STDOUT: {stdout}"
            logger.error(error_message)
            raise RuntimeError("Pip install failed. Check logs for details.")
        logger.success(f"成功安装/更新 requirements: {', '.join(valid_requirements)}")
