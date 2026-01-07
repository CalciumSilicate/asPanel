"""
ASPanel 玩家绑定确认插件
玩家在游戏内执行 /aspanel bind <code> 确认绑定
"""
import os
import httpx
from mcdreforged.api.all import *
from pathlib import Path

PLUGIN_METADATA = {
    "id": "aspanel_bind",
    "version": "1.0.0",
    "name": "ASPanel Bind Confirm",
    "description": "用于确认 ASPanel 玩家绑定的 MCDR 插件",
    "author": "ASPanel",
    "link": "https://github.com/CalciumSilicate/asPanel",
    "dependencies": {
        "mcdreforged": ">=2.0.0"
    }
}

# ASPanel API 地址（需要配置）
ASPANEL_API_URL = "http://127.0.0.1:8000"
def _read_aspanel_port() -> int:
    """
    读取 ASPanel 的 config.yaml 获取端口。
    插件运行在 MCDR 服务器目录，ASPanel 配置文件在上级目录。
    查找顺序：
    1. 当前目录向上查找 config.yaml / config.yml
    2. 环境变量 ASPANEL_PORT
    3. 默认值 8013
    """
    # 从当前目录向上查找 config.yaml
    current = Path(".").resolve()
    for _ in range(10):  # 最多向上查找 10 层
        for name in ["config.yaml", "config.yml"]:
            cfg_path = current / name
            if cfg_path.exists() and cfg_path.is_file():
                try:
                    import yaml
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}
                    server_cfg = data.get("server") or {}
                    port = server_cfg.get("port")
                    if isinstance(port, int) and port > 0:
                        return port
                except Exception:
                    pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    
    # 回退到环境变量
    env_port = os.getenv("ASPANEL_PORT")
    if env_port and env_port.isdigit():
        return int(env_port)
    
    # 默认值
    return 8013

def get_config(server: PluginServerInterface) -> dict:
    """获取插件配置"""
    aspanel_port = _read_aspanel_port()
    default_config = {
        "api_url": "http://127.0.0.1:{}".format(aspanel_port),
        "enabled": True
    }
    return server.load_config_simple(default_config=default_config)


@new_thread("aspanel_bind")
def confirm_bind(source: CommandSource, code: str):
    """确认绑定"""
    if not isinstance(source, PlayerCommandSource):
        source.reply(RText("此命令只能由玩家执行", RColor.red))
        return
    
    player_name = source.player
    config = get_config(source.get_server())
    
    if not config.get("enabled", True):
        source.reply(RText("绑定功能已禁用", RColor.red))
        return
    
    api_url = config.get("api_url", ASPANEL_API_URL)
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f"{api_url}/api/bind/verify",
                json={
                    "code": code,
                    "player_name": player_name
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    source.reply(RText("✓ 绑定成功！你的账号已与面板账号关联", RColor.green))
                else:
                    source.reply(RText(f"绑定失败: {data.get('message', '未知错误')}", RColor.red))
            else:
                try:
                    error = response.json()
                    msg = error.get("detail", str(response.status_code))
                except:
                    msg = f"HTTP {response.status_code}"
                source.reply(RText(f"绑定失败: {msg}", RColor.red))
                
    except httpx.TimeoutException:
        source.reply(RText("请求超时，请稍后重试", RColor.red))
    except httpx.RequestError as e:
        source.reply(RText(f"网络错误: {e}", RColor.red))
    except Exception as e:
        source.reply(RText(f"发生错误: {e}", RColor.red))


def on_load(server: PluginServerInterface, prev_module):
    """插件加载"""
    server.register_command(
        Literal("!!aspanel")
        .then(
            Literal("bind")
            .then(
                Text("code")
                .runs(lambda src, ctx: confirm_bind(src, ctx["code"]))
            )
        )
    )
    
    # 也注册 /bindconfirm 作为快捷方式
    server.register_command(
        Literal("!!bindconfirm")
        .then(
            Text("code")
            .runs(lambda src, ctx: confirm_bind(src, ctx["code"]))
        )
    )
    
    server.logger.info("ASPanel Bind Confirm 插件已加载")


def on_unload(server: PluginServerInterface):
    """插件卸载"""
    server.logger.info("ASPanel Bind Confirm 插件已卸载")
