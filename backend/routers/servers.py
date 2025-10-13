import json

from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks
from sqlalchemy.orm import Session
import uuid
import shutil
from typing import List
from pathlib import Path
import ruamel.yaml
import yaml
import asyncio
import psutil

from backend import crud, schemas, server_parser, models
from backend.auth import require_role
from backend.database import get_db
from backend.dependencies import mcdr_manager, server_service
from backend.dependencies import task_manager
from backend.schemas import TaskType, Role, PaperBuild, PaperBuildDownload, ServerCoreConfig
from backend.tasks.background import background_download_jar, background_install_fabric
from backend.core.config import DEFAULT_SERVER_PROPERTIES_CONFIG, PUBLIC_PLUGINS_DIRECTORIES
from backend.core.utils import get_file_sha1, get_file_sha256, get_fabric_jar_version, Timer
from backend.core.api import get_velocity_version_detail, get_minecraft_version_detail_by_version_id, \
    get_fabric_version_meta

router = APIRouter(
    prefix="/api",
    tags=["Servers"],
)


# --- Server Endpoints ---
@router.get('/servers', response_model=List[schemas.ServerDetail])
async def get_servers(db: Session = Depends(get_db), _user: models.User = Depends(require_role(Role.GUEST))):
    return await server_service.get_servers_with_details(db)


@router.post('/servers/create', response_model=schemas.Server, status_code=status.HTTP_201_CREATED)
async def create_server(server: schemas.ServerCreate, db: Session = Depends(get_db),
                        user: models.User = Depends(require_role(Role.ADMIN))):
    # PERMISSION: ADMIN
    return await server_service.create_server(server, db, user)


@router.delete("/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(server_id: int, db: Session = Depends(get_db),
                        _user: models.User = Depends(require_role(Role.ADMIN))):
    # PERMISSION: ADMIN
    # 预先获取服务器以便清理 mods 记录
    srv = crud.get_server_by_id(db, server_id)
    srv_path = srv.path if srv else None

    await server_service.delete_server(server_id, db)

    # 删除该服务器的 mods 数据库记录与关联
    if srv_path:
        try:
            crud.cleanup_mods_for_server_path(db, server_id, srv_path)
        except Exception:
            pass

    # 额外清理：plugin 表中的 servers_installed 与 server_link_groups 的 server_ids
    try:
        crud.cleanup_plugins_for_server(db, server_id)
    except Exception:
        pass
    try:
        crud.cleanup_server_link_groups_for_server(db, server_id)
    except Exception:
        pass
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Server Action Endpoints ---
@router.post('/servers/start')
async def start_server(server_id: int, db: Session = Depends(get_db),
                       _user: models.User = Depends(require_role(Role.USER))):
    # PERMISSION: USER
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    success, message = await mcdr_manager.start(server)
    if not success:
        raise HTTPException(409, message)
    return {"status": "success", "pid": message}


@router.post("/servers/stop")
async def stop_server(server_id: int, db: Session = Depends(get_db),
                      _user: models.User = Depends(require_role(Role.USER))):
    # PERMISSION: USER
    server = crud.get_server_by_id(db, server_id)
    await mcdr_manager.stop(server)
    return {"status": "success"}


@router.post("/servers/force-kill")
async def force_kill_server(server_id: int, db: Session = Depends(get_db),
                            _user: models.User = Depends(require_role(Role.ADMIN))):
    # PERMISSION: ADMIN
    server = crud.get_server_by_id(db, server_id)
    server_status, _ = await mcdr_manager.get_status(server_id, server.path)
    if server_status != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="服务器未处于运行状态，无法强制关闭。"
        )
    success, message = await mcdr_manager.force_kill(server)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=message)

    return {"status": "success", "message": message}


@router.post("/servers/restart")
async def restart_server_endpoint(server_id: int, db: Session = Depends(get_db),
                                  _user: models.User = Depends(require_role(Role.HELPER))):
    # PERMISSION: HELPER
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    success, message = await mcdr_manager.restart(server, server.path)
    if not success:
        raise HTTPException(409, message)
    return {"status": "success", "pid": message}


@router.get("/servers/status")
async def get_server_status(server_id: int, db: Session = Depends(get_db),
                            _user: models.User = Depends(require_role(Role.GUEST))):
    # PERMISSION: GUEST
    server = crud.get_server_by_id(db, server_id)
    st, _ = await mcdr_manager.get_status(server_id, server.path)
    return {"status": st}


@router.post("/servers/start-for-while")
async def start_for_while(server_id: int, delay: int = 3, db: Session = Depends(get_db),
                          _user: models.User = Depends(require_role(Role.ADMIN))):
    # PERMISSION: ADMIN
    server = crud.get_server_by_id(db, server_id)
    await mcdr_manager.start_for_a_while(server, delay)


@router.post('/servers/batch-action')
async def batch_action_on_servers(action: str, payload: schemas.BatchActionPayload, db: Session = Depends(get_db),
                                  _user: models.User = Depends(require_role(Role.ADMIN))):
    # PERMISSION: ADMIN
    if not payload.ids:
        raise HTTPException(400, "No server IDs provided")
    tasks = []
    for sid in payload.ids:
        server = crud.get_server_by_id(db, sid)
        if not server:
            continue
        if action == "start":
            tasks.append(mcdr_manager.start(server))
        elif action == "stop":
            tasks.append(mcdr_manager.stop(server))
        elif action == "restart":
            tasks.append(mcdr_manager.restart(server))
        elif action == "delete":
            tasks.append(server_service.delete_server(sid, db))
        elif action == "command" and payload.command:
            tasks.append(mcdr_manager.send_command(server, payload.command))
    if tasks:
        await asyncio.gather(*tasks)
    return {"status": "success", "message": f"Action '{action}' sent."}


@router.get("/servers/config", response_model=schemas.ServerConfigResponse)
async def get_server_config(server_id: int, db: Session = Depends(get_db),
                            _user: models.User = Depends(require_role(Role.HELPER))):
    # PERMISSION: HELPER
    db_server = crud.get_server_by_id(db, server_id)
    if not db_server:
        raise HTTPException(404, "Server not found")
    server = schemas.Server.model_validate(db_server)
    mcdr_path = Path(server.path)
    server_dir = mcdr_path / 'server'
    is_new_setup = not server_dir.exists() or not any(
        f.name not in ['eula.txt', 'velocity.toml'] for f in server_dir.iterdir())
    if is_new_setup:
        default_config = schemas.ServerConfigData(
            core_config=server.core_config,
            jvm=schemas.ServerConfigJvm(),
            vanilla_server_properties=DEFAULT_SERVER_PROPERTIES_CONFIG
        )
        return schemas.ServerConfigResponse(
            is_new_setup=True,
            core_file_exists=False,
            config_file_exists=False,
            config=default_config
        )
    try:
        mcdr_config_path = mcdr_path / 'config.yml'
        with open(mcdr_config_path, 'r', encoding='utf-8') as f:
            mcdr_config = yaml.safe_load(f) or {}
        server_type = server.core_config.server_type
        jvm_config, _ = server_parser.parse_start_command(mcdr_config['start_command'])
        launcher_jar = server.core_config.launcher_jar
        launcher_jar_path = server_dir / launcher_jar if launcher_jar else None

        if server_type in ['vanilla', 'beta18']:
            server_properties = server_parser.parse_properties(server_dir / 'server.properties')
            if not server_properties.get("enable-rcon"):
                server_properties["rcon.port"] = '未启用RCON'
                server_properties["rcon.password"] = '未启用RCON'
            config = schemas.ServerConfigData(
                core_config=server.core_config,
                jvm=jvm_config,
                vanilla_server_properties=server_properties
            )
            return schemas.ServerConfigResponse(
                is_new_setup=False,
                core_file_exists=launcher_jar_path.exists(),
                config_file_exists=True,
                config=config
            )
        elif server_type == 'velocity':
            velocity_toml_path = server_dir / 'velocity.toml'
            velocity_toml = server_parser.parse_velocity_toml(
                velocity_toml_path) if velocity_toml_path.exists() else None
            config = schemas.ServerConfigData(
                core_config=server.core_config,
                jvm=jvm_config,
                velocity_toml=velocity_toml
            )
            return schemas.ServerConfigResponse(
                is_new_setup=False,
                core_file_exists=launcher_jar_path.exists(),
                config_file_exists=velocity_toml_path.exists(),
                config=config
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading config files: {e}")


@router.post("/servers/config")
async def save_server_config(
        payload: schemas.ServerConfigPayload,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        _user: models.User = Depends(require_role(Role.ADMIN))
):
    # PERMISSION: ADMIN
    server = crud.get_server_by_id(db, payload.server_id)
    legacy_server_core_config = ServerCoreConfig.model_validate(json.loads(server.core_config))
    if not server:
        raise HTTPException(404, "Server not found")
    config_data = payload.config
    mcdr_path = Path(server.path)
    server_dir = mcdr_path / 'server'
    # 1. 初始化 ruamel.yaml 实例
    _yaml = ruamel.yaml.YAML()
    _yaml.indent(mapping=2, sequence=4, offset=2)  # 设置标准缩进，保持格式优美
    _yaml.preserve_quotes = True  # 保留原有的引号风格
    vanilla_props = config_data.vanilla_server_properties
    velocity_toml = config_data.velocity_toml
    core_config = config_data.core_config
    server_type = core_config.server_type
    core_version = core_config.core_version
    is_fabric = core_config.is_fabric
    server_jar = core_config.server_jar
    if is_fabric:
        core_config.launcher_jar = 'fabric-server-launch.jar'
    else:
        core_config.launcher_jar = server_jar
    _, legacy_core_config = crud.update_server_core_config(db, payload.server_id, core_config)
    try:
        mcdr_config_path = mcdr_path / 'config.yml'
        with open(mcdr_config_path, 'r', encoding='utf-8') as f:
            mcdr_config = _yaml.load(f)

        jvm = config_data.jvm
        launcher_jar = core_config.launcher_jar
        jvm_args_list = [f"-Xms{jvm.min_memory}", f"-Xmx{jvm.max_memory}", *filter(None, jvm.extra_args.split())]
        mcdr_config['start_command'] = ' '.join(["java", *jvm_args_list, "-jar", launcher_jar])
        mcdr_config['handler'] = f"{config_data.core_config.server_type.lower()}_handler"
        mcdr_config['working_directory'] = 'server'
        mcdr_config['plugin_directories'] = PUBLIC_PLUGINS_DIRECTORIES

        # vanilla/ forge server
        if vanilla_props is not None and vanilla_props.get('enable-rcon'):
            mcdr_config['rcon']['enable'] = True
            mcdr_config['rcon']['port'] = vanilla_props.get('rcon.port')
            mcdr_config['rcon']['password'] = vanilla_props.get('rcon.password')
        elif 'rcon' in mcdr_config:
            mcdr_config['rcon']['enable'] = False
        # write mcdr_config
        with open(mcdr_config_path, 'w', encoding='utf-8') as f:
            _yaml.dump(mcdr_config, f)

        # Initialize server core !!!
        if server_type in ['vanilla', 'beta18']:
            server_dir.mkdir(exist_ok=True)
            server_parser.write_properties_file(server_dir / 'server.properties', vanilla_props)
            jar_path = server_dir / server_jar
            current_sha1 = get_file_sha1(jar_path)
            task_list = []
            if not current_sha1 or core_version != legacy_server_core_config.core_version:
                # not current_sha1 -> server_jar 不存在
                # core_version != (await ...) -> 改变游戏版本
                version_details = await get_minecraft_version_detail_by_version_id(core_version)
                version_id = version_details['id']
                download_info = version_details.get("downloads", {}).get("server", {})
                url, expected_sha1 = download_info.get('url'), download_info.get("sha1")
                if not expected_sha1:
                    raise HTTPException(500, f"Version {version_id} has no server download info.")
                dest_path = server_dir / server_jar
                vanilla_jar_task = task_manager.create_task(TaskType.DOWNLOAD)
                task_list.append(vanilla_jar_task)
                background_tasks.add_task(
                    background_download_jar,
                    url,
                    dest_path,
                    vanilla_jar_task,
                    sha1=expected_sha1
                )

            if is_fabric:
                vanilla_version, fabric_loader_version = get_fabric_jar_version(server_dir / launcher_jar)
                if (not all((vanilla_version, fabric_loader_version)) or fabric_loader_version !=
                        core_config.loader_version or vanilla_version != core_version):
                    fabric_loader_task = task_manager.create_task(TaskType.DOWNLOAD)
                    task_list.append(fabric_loader_task)
                    background_tasks.add_task(
                        background_install_fabric,
                        await get_fabric_version_meta(core_version, core_config.loader_version),
                        server_dir,
                        core_version,
                        core_config.loader_version,
                        fabric_loader_task,
                    )

            if len(task_list) > 1:
                combined_task = task_manager.create_task(TaskType.COMBINED)
                combined_task.ids = list(task.id for task in task_list)
                return {"status": "downloading", "task_id": combined_task.id}
            elif len(task_list) == 1:
                return {"status": "downloading", "task_id": task_list[0].id}
            else:
                return {"status": "success", "message": "Configuration saved"}

        elif server_type == 'velocity':
            try:
                server_parser.write_velocity_toml(server_dir / 'velocity.toml', velocity_toml)
            except AttributeError:
                ...
            jar_path = server_dir / launcher_jar
            current_sha256 = get_file_sha256(jar_path)

            if not current_sha256 or core_version != legacy_server_core_config.core_version:
                version_id = core_version
                version, build = version_id.split("#", 1)

                build = await get_velocity_version_detail(version, build)
                build_info = PaperBuild.model_validate(build)
                download_info = PaperBuildDownload.model_validate(list(build_info.downloads.values())[0])
                expected_sha256 = download_info.checksums.sha256
                url = download_info.url

                dest_path = server_dir / launcher_jar
                task = task_manager.create_task(TaskType.DOWNLOAD)
                background_tasks.add_task(
                    background_download_jar,
                    url,
                    dest_path,
                    task,
                    sha256=expected_sha256
                )
                return {"status": "downloading", "task_id": task.id}
        return {"status": "success", "message": "Configuration saved successfully."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        crud.update_server_core_config(db, payload.server_id, legacy_core_config)
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}")


@router.get("/servers/resource-usage")
async def get_servers_resource_usage(db: Session = Depends(get_db),
                                     _user: models.User = Depends(require_role(Role.GUEST))):
    # PERMISSION: GUEST
    usage_data = []
    for server_id, process in mcdr_manager.processes.items():
        if process.returncode is None and mcdr_manager.java_pid.get(server_id):
            try:
                p = psutil.Process(mcdr_manager.java_pid.get(server_id))
                info = crud.get_server_by_id(db, server_id)
                if info:
                    usage_data.append(
                        {
                            "id": server_id,
                            "name": info.name,
                            "cpu_percent": p.cpu_percent(interval=0.1),
                            "memory_mb": round(p.memory_info().rss / (1024 * 1024), 2)
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    return sorted(usage_data, key=lambda x: x['cpu_percent'], reverse=True)


@router.get("/servers/{server_id}/logs", response_model=List[str])
async def read_server_logs(
        server_id: int, line_limit: int = 200,
        db: Session = Depends(get_db),
        _user: models.User = Depends(require_role(Role.HELPER))
):
    # PERMISSION: HELPER
    server = crud.get_server_by_id(db, server_id=server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    historical_logs = await asyncio.to_thread(
        mcdr_manager.get_historical_logs, server, line_limit
    )
    return historical_logs


@router.get("/servers/{server_id}/config-file", response_class=Response)
async def get_config_file(
        server_id: int,
        file_type: str,
        db: Session = Depends(get_db),
        _user: models.User = Depends(require_role(Role.HELPER))
):
    # PERMISSION: HELPER
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server_path = Path(server.path)
    if file_type == 'mcdr_config':
        file_path = server_path / 'config.yml'
    elif file_type == 'mc_properties':
        file_path = server_path / 'server' / 'server.properties'
    elif file_type == 'velocity_toml':
        file_path = server_path / 'server' / 'velocity.toml'
    else:
        raise HTTPException(status_code=400, detail="Invalid file type specified.")
    if not file_path.exists():
        return Response(content="", media_type="text/plain")
    try:
        content = file_path.read_text(encoding='utf-8')
        return Response(content=content, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


@router.post("/servers/{server_id}/config-file")
async def save_config_file(
        server_id: int,
        payload: schemas.FileContentUpdate,
        db: Session = Depends(get_db),
        _user: models.User = Depends(require_role(Role.ADMIN))
):
    # PERMISSION: ADMIN
    server = crud.get_server_by_id(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server_path = Path(server.path)
    if payload.file_type == 'mcdr_config':
        file_path = server_path / 'config.yml'
    elif payload.file_type == 'mc_properties':
        file_path = server_path / 'server' / 'server.properties'
    elif payload.file_type == 'velocity_toml':  # [新增]
        file_path = server_path / 'server' / 'velocity.toml'
    else:
        raise HTTPException(status_code=400, detail="Invalid file type specified.")
    try:
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(payload.content, encoding='utf-8')
        return {"message": "File saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


@router.post('/servers/import', status_code=status.HTTP_201_CREATED)
async def api_import_server(server_data: schemas.ServerImport, background_tasks: BackgroundTasks,
                            db: Session = Depends(get_db), user: models.User = Depends(require_role(Role.ADMIN))):
    # PERMISSION: ADMIN
    task = task_manager.create_task(TaskType.IMPORT)
    background_tasks.add_task(server_service.import_server, server_data, db, user, task, task_manager)
    return {"task_id": task.id, "message": "已开始导入服务器任务"}
