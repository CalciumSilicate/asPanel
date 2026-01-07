# backend/routers/tools.py

import asyncio
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status, File, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from backend.core import crud, models, models as _models, schemas
from backend.core.auth import require_role
from backend.core.utils import to_local_iso, to_local_dt
from backend.core.database import get_db
from backend.core.schemas import Role, TaskType, TaskStatus
from backend.core.dependencies import task_manager
from backend.tools.flat_world_generator import generate_flat_level_dat, apply_level_dat_to_server
from backend.tools import prime_backup as pb
from backend.tools.litematic_parser import (
    generate_command_list,
    has_command_list_for,
    get_command_list_output_file_name_for,
)
from backend.core.constants import (
    UPLOADED_LITEMATIC_PATH,
    LITEMATIC_COMMAND_LIST_PATH,
)
from backend.core.database import SessionLocal

router = APIRouter(prefix="/api", tags=["Utils"])


@router.post("/tools/superflat/leveldat")
async def generate_level_dat_endpoint(payload: schemas.SuperFlatConfig, _user: models.User = Depends(require_role(Role.USER))):
    """生成 level.dat 并以二进制流返回（gzip NBT）。"""
    try:
        data = generate_flat_level_dat(payload.to_generator_payload())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"生成 level.dat 失败: {e}")
    headers = {"Content-Disposition": "attachment; filename=level.dat"}
    return StreamingResponse(iter([data]), media_type="application/octet-stream", headers=headers)


@router.post("/tools/superflat/apply")
async def apply_level_dat_endpoint(
    payload: schemas.ApplyRequest,
    db: Session = Depends(get_db),
    _user: models.User = Depends(require_role(Role.ADMIN)),
):
    """生成并应用 level.dat 到指定服务器。"""
    server = crud.get_server_by_id(db, payload.server_id)
    if not server:
        raise HTTPException(status_code=404, detail="服务器不存在")

    try:
        data = generate_flat_level_dat(payload.to_generator_payload())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"生成 level.dat 失败: {e}")

    try:
        out_path = apply_level_dat_to_server(server.path, data, overwrite=payload.overwrite)
    except FileExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"应用 level.dat 失败: {e}")

    return {"status": "success", "path": str(out_path)}


# ===================== Prime Backup =====================

from fastapi import BackgroundTasks, UploadFile, File, Query
from backend.core.auth import require_role
from backend.core.schemas import Role


@router.get("/tools/pb/{server_id}/usage", response_model=schemas.PBUsage)
async def get_pb_usage(server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    return await pb.pb_usage(db, server_id)


@router.get("/tools/pb/usage/total", response_model=schemas.PBUsage)
async def get_pb_usage_total(db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    return await pb.pb_usage_total(db)


@router.get("/tools/pb/{server_id}/overview", response_model=schemas.PBOverview)
async def get_pb_overview(server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    return await pb.pb_overview(db, server_id)


@router.get("/tools/pb/{server_id}/list", response_model=list[schemas.PBBackupItem])
async def get_pb_list(server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    return await pb.pb_list(db, server_id)


@router.get("/tools/pb/{server_id}/show", response_model=str)
async def get_pb_show(server_id: int, id: int = Query(..., description="backup id"), db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    return await pb.pb_show(db, server_id, id)


@router.post("/tools/pb/{server_id}/export")
async def post_pb_export(server_id: int, payload: schemas.PBExportPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    return await pb.pb_export(db, server_id, payload.id, background_tasks)


@router.post("/tools/pb/{server_id}/extract")
async def post_pb_extract(server_id: int, payload: schemas.PBExtractPayload, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    return await pb.pb_extract(db, server_id, payload)


@router.post("/tools/pb/{server_id}/import")
async def post_pb_import(server_id: int, file: UploadFile = File(...), auto_meta: bool = Query(False), db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    return await pb.pb_import(db, server_id, file, auto_meta)


@router.post("/tools/pb/{server_id}/migrate_db")
async def post_pb_migrate_db(server_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    return await pb.pb_migrate(db, server_id)


@router.post("/tools/pb/{server_id}/fuse")
async def post_pb_fuse(server_id: int, mount_path: str, _user=Depends(require_role(Role.ADMIN))):
    # 目前环境可能不具备 fuse 条件，返回 501 占位
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="fuse not implemented on server")


@router.post("/tools/pb/{server_id}/restore")
async def post_pb_restore(server_id: int, payload: schemas.PBRestorePayload, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    return await pb.pb_restore(db, server_id, payload.id, payload.target_server_id)


# ===================== Litematic 工具集 =====================

from sqlalchemy import desc, or_


def _query_latest_download_by_name_and_url(db: Session, file_name: str, url_marker: str) -> models.Download | None:
    return (
        db.query(models.Download)
        .filter(models.Download.file_name == file_name)
        .filter(models.Download.url == url_marker)
        .order_by(desc(models.Download.created_at))
        .first()
    )


def _query_latest_by_url(db: Session, url_marker: str) -> models.Download | None:
    return (
        db.query(models.Download)
        .filter(models.Download.url == url_marker)
        .order_by(desc(models.Download.created_at))
        .first()
    )


@router.post("/tools/litematic/upload")
async def litematic_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    """上传 .litematic 文件：以 UUID 作为本地文件名，数据库记录原始文件名。

    - 物理路径：backend/core/constants.py → UPLOADED_LITEMATIC_PATH
    - DB 表：models.Download（url 字段固定为 'litematic-upload'）
    """
    if not file.filename or not file.filename.lower().endswith(".litematic"):
        raise HTTPException(status_code=400, detail="仅支持 .litematic 文件")

    UPLOADED_LITEMATIC_PATH.mkdir(parents=True, exist_ok=True)
    uuid_name = f"{uuid.uuid4().hex}.litematic"
    target_path = UPLOADED_LITEMATIC_PATH / uuid_name
    try:
        contents = await file.read()
        target_path.write_bytes(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存文件失败: {e}")

    # 记录到 Download 表
    db_file = models.Download(
        url="litematic-upload",
        path=str(target_path.resolve()),
        file_name=file.filename,
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return {
        "message": "上传成功",
        "file_name": db_file.file_name,
        "stored_path": db_file.path,
        "id": db_file.id,
    }


@router.delete("/tools/litematic/delete/{file_name}", status_code=status.HTTP_204_NO_CONTENT)
async def litematic_delete(file_name: str, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """删除一条 litematic（根据原始文件名匹配最新一条记录）。"""
    rec = _query_latest_download_by_name_and_url(db, file_name, url_marker="litematic-upload")
    if not rec:
        raise HTTPException(status_code=404, detail="未找到指定 litematic 记录")
    # 删除物理文件
    try:
        p = Path(rec.path)
        if p.exists():
            p.unlink()
    except Exception:
        # 文件删除失败不阻塞 DB 清理
        pass
    # 删除 DB 记录
    db.delete(rec)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tools/litematic/rename/{file_name}/{new_file_name}")
async def litematic_rename(file_name: str, new_file_name: str, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """重命名 litematic 的“显示名”（DB 内 file_name 字段）。
    仅修改数据库记录，不改动物理文件（物理名为 UUID）。
    """
    rec = _query_latest_download_by_name_and_url(db, file_name, url_marker="litematic-upload")
    if not rec:
        raise HTTPException(status_code=404, detail="未找到指定 litematic 记录")
    rec.file_name = new_file_name
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"message": "重命名成功", "file_name": rec.file_name}


@router.get("/tools/litematic/download/{file_name}")
async def litematic_download(file_name: str, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """下载指定 litematic（按原始文件名匹配最新一条记录）。"""
    rec = _query_latest_download_by_name_and_url(db, file_name, url_marker="litematic-upload")
    if not rec:
        raise HTTPException(status_code=404, detail="未找到指定 litematic 记录")
    p = Path(rec.path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="文件不存在或已被删除")
    return FileResponse(path=str(p), filename=Path(rec.file_name).name, media_type="application/octet-stream")


@router.post("/tools/litematic/generate_cl/{file_name}")
async def litematic_generate_cl(
    file_name: str,
    db: Session = Depends(get_db),
    _user=Depends(require_role(Role.USER)),
):
    """
    根据指定 litematic 生成命令清单（command list），返回任务 ID 供前端跟踪进度。
    - 输入：按原始文件名匹配（选最新一条）
    - 输出：LITEMATIC_COMMAND_LIST_PATH / '<litematic-uuid>.mccl.txt'
    """
    rec = _query_latest_download_by_name_and_url(db, file_name, url_marker="litematic-upload")
    if not rec:
        raise HTTPException(status_code=404, detail="未找到指定 litematic 记录")

    src_path = Path(rec.path)
    if not src_path.is_file():
        raise HTTPException(status_code=404, detail="源 litematic 文件不存在")

    try:
        uuid_stem = src_path.stem
    except Exception:
        uuid_stem = uuid.uuid4().hex

    LITEMATIC_COMMAND_LIST_PATH.mkdir(parents=True, exist_ok=True)
    out_path = LITEMATIC_COMMAND_LIST_PATH / f"{uuid_stem}.mccl.txt"
    display_name = f"{Path(rec.file_name).stem}.mccl.txt"
    rec_id = rec.id

    task = task_manager.create_task(
        TaskType.LITEMATIC_GENERATE,
        name=f"生成命令清单：{file_name}",
        message="准备生成..."
    )

    async def _runner():
        task.status = TaskStatus.RUNNING
        task.progress = 0
        task.message = "正在解析投影文件..."

        try:
            task.progress = 10
            task.message = "正在生成命令..."

            await asyncio.to_thread(generate_command_list, src_path, out_path)

            task.progress = 90
            task.message = "正在保存到数据库..."

            with SessionLocal() as db_session:
                db_rec = db_session.query(models.Download).filter(
                    models.Download.path == str(out_path.resolve())
                ).first()
                if db_rec is None:
                    db_rec = models.Download(
                        url="litematic-command-list",
                        path=str(out_path.resolve()),
                        file_name=display_name
                    )
                    db_session.add(db_rec)
                else:
                    db_rec.file_name = display_name
                db_session.commit()

            task.status = TaskStatus.SUCCESS
            task.progress = 100
            task.message = f"命令清单生成完成：{display_name}"

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.message = f"生成命令清单失败"

        finally:
            try:
                task_manager.clear_finished_task(task.id)
            except Exception:
                pass

    asyncio.create_task(_runner())
    return {"message": "生成任务已启动", "task_id": task.id, "file_name": display_name}


@router.get("/tools/litematic/list")
async def litematic_list(db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """列出所有上传的 litematic 及其命令清单状态。"""
    rows: list[models.Download] = (
        db.query(models.Download)
        .filter(models.Download.url == "litematic-upload")
        .order_by(desc(models.Download.created_at))
        .all()
    )
    result: list[dict] = []
    for r in rows:
        try:
            src = Path(r.path)
            info = {
                "file_name": r.file_name,
                "created_at": to_local_iso(r.created_at) if r.created_at else None,
                "cl_generated": has_command_list_for(src),
                "cl_file_path": get_command_list_output_file_name_for(src)
            }
        except Exception:
            info = {
                "file_name": r.file_name,
                "created_at": to_local_iso(r.created_at) if r.created_at else None,
                "cl_generated": False,
                "cl_file_path": None
            }
        result.append(info)
    return result


@router.delete("/tools/litematic/delete_cl/{litematic_file_name}", status_code=status.HTTP_204_NO_CONTENT)
async def litematic_delete_cl(litematic_file_name: str, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """删除指定 litematic 对应的 command list。

    若不存在 litematic_file_name 对应的 command list，则返回 404 提示。
    """
    ltm_rec = _query_latest_download_by_name_and_url(db, litematic_file_name, url_marker="litematic-upload")
    if not ltm_rec:
        raise HTTPException(status_code=404, detail="未找到指定 litematic 记录")

    uuid_stem = Path(ltm_rec.path).stem
    out_path = LITEMATIC_COMMAND_LIST_PATH / f"{uuid_stem}.mccl.txt"

    cl_rec: models.Download | None = (
        db.query(models.Download)
        .filter(models.Download.url == "litematic-command-list")
        .filter(models.Download.path == str(out_path.resolve()))
        .first()
    )
    if not cl_rec or not out_path.exists():
        raise HTTPException(status_code=404, detail="对应的 command list 不存在")

    try:
        out_path.unlink(missing_ok=True)
    except Exception:
        pass

    db.delete(cl_rec)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tools/litematic/download_cl/{litematic_file_name}")
async def litematic_download_cl(litematic_file_name: str, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """下载指定 litematic 对应的 command list；若不存在则先生成后下载。"""
    ltm_rec = _query_latest_download_by_name_and_url(db, litematic_file_name, url_marker="litematic-upload")
    if not ltm_rec:
        raise HTTPException(status_code=404, detail="未找到指定 litematic 记录")

    src_path = Path(ltm_rec.path)
    if not src_path.is_file():
        raise HTTPException(status_code=404, detail="源 litematic 文件不存在")

    uuid_stem = src_path.stem
    LITEMATIC_COMMAND_LIST_PATH.mkdir(parents=True, exist_ok=True)
    out_path = LITEMATIC_COMMAND_LIST_PATH / f"{uuid_stem}.mccl.txt"
    display_name = f"{Path(ltm_rec.file_name).stem}.mccl.txt"

    # 若不存在则生成
    if not out_path.exists():
        try:
            generate_command_list(src_path, out_path)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"生成命令清单失败: {e}")

    # upsert DB 记录
    cl_rec: models.Download | None = (
        db.query(models.Download)
        .filter(models.Download.url == "litematic-command-list")
        .filter(models.Download.path == str(out_path.resolve()))
        .first()
    )
    if cl_rec is None:
        cl_rec = models.Download(url="litematic-command-list", path=str(out_path.resolve()), file_name=display_name)
        db.add(cl_rec)
    else:
        cl_rec.file_name = display_name
    db.commit()
    db.refresh(cl_rec)

    return FileResponse(path=str(out_path), filename=display_name, media_type="text/plain; charset=utf-8")


# ===================== Server Link（服务器组） =====================
from backend.tools import server_link as sl
from backend.services.ws import broadcast_server_link_update, broadcast_chat_to_plugins
from pathlib import Path
from backend.core.ws import sio
from backend.services import onebot


@router.get("/tools/server-link/groups", response_model=list[schemas.ServerLinkGroup])
async def sl_groups_list(db: Session = Depends(get_db), current_user: _models.User = Depends(require_role(Role.USER))):
    all_groups = await sl.sl_list_groups(db)
    
    # HELPER 及以上返回所有组
    role_level = {'GUEST': 0, 'USER': 1, 'HELPER': 2, 'ADMIN': 3, 'OWNER': 4}
    if role_level.get(current_user.role, 0) >= role_level['HELPER']:
        return all_groups
    
    # USER 只返回其有权限的组
    try:
        user_group_ids = json.loads(current_user.server_link_group_ids or '[]')
    except Exception:
        user_group_ids = []
    
    return [g for g in all_groups if g.id in user_group_ids]


@router.post("/tools/server-link/groups", response_model=schemas.ServerLinkGroup)
async def sl_groups_create(payload: schemas.ServerLinkGroupCreate, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    try:
        created = await sl.sl_create_group(db, payload)
        # 推送到相关服务器
        for sid in (payload.server_ids or []):
            s = crud.get_server_by_id(db, sid)
            if s:
                server_name = Path(s.path).name
                # 计算该服务器当前所有分组名称
                names = [g.name for g in crud.list_server_link_groups(db) if sid in (g and __import__('json').loads(getattr(g, 'server_ids', '[]')))]
                await broadcast_server_link_update(server_name, names)
        await onebot.refresh_bindings()
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/tools/server-link/groups/{group_id}", response_model=schemas.ServerLinkGroup)
async def sl_groups_update(group_id: int, payload: schemas.ServerLinkGroupUpdate, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    try:
        # 更新前后比对 server_ids，推送给变化涉及的服务器
        before = crud.get_server_link_group_by_id(db, group_id)
        before_ids = []
        if before:
            try:
                import json as _json
                before_ids = list(map(int, _json.loads(before.server_ids or '[]')))
            except Exception:
                before_ids = []
        updated = await sl.sl_update_group(db, group_id, payload)
        after_ids = payload.server_ids if payload.server_ids is not None else before_ids
        affected = set(before_ids) | set(after_ids)
        # 逐个服务器推送其当前分组列表
        import json as _json
        all_groups = crud.list_server_link_groups(db)
        for sid in affected:
            s = crud.get_server_by_id(db, sid)
            if not s:
                continue
            names = []
            for g in all_groups:
                try:
                    ids = list(map(int, _json.loads(g.server_ids or '[]')))
                except Exception:
                    ids = []
                if sid in ids:
                    names.append(g.name)
            await broadcast_server_link_update(Path(s.path).name, names)
        await onebot.refresh_bindings()
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/tools/server-link/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def sl_groups_delete(group_id: int, db: Session = Depends(get_db), _user=Depends(require_role(Role.ADMIN))):
    # 删除前计算受影响服务器
    rec = crud.get_server_link_group_by_id(db, group_id)
    import json as _json
    affected = []
    try:
        affected = list(map(int, _json.loads(rec.server_ids or '[]'))) if rec else []
    except Exception:
        affected = []
    ok = await sl.sl_delete_group(db, group_id)
    if not ok:
        raise HTTPException(status_code=404, detail="服务器组不存在")
    else:
        # 删除该组的所有聊天记录（不包含 ALERT/None）
        try:
            crud.delete_chat_messages_by_group(db, group_id)
        except Exception:
            pass
        # 受影响服务器重新推送其当前分组（此时已无该组）
        all_groups = crud.list_server_link_groups(db)
        for sid in affected:
            s = crud.get_server_by_id(db, sid)
            if not s:
                continue
            names = []
            for g in all_groups:
                try:
                    ids = list(map(int, _json.loads(g.server_ids or '[]')))
                except Exception:
                    ids = []
                if sid in ids:
                    names.append(g.name)
            await broadcast_server_link_update(Path(s.path).name, names)
    await onebot.refresh_bindings()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tools/server-link/groups/by-server", response_model=list[schemas.ServerLinkGroup])
async def sl_groups_by_server(server_name: Optional[str] = None, server_id: Optional[int] = None, db: Session = Depends(get_db), _user=Depends(require_role(Role.USER))):
    """按服务器（目录名或 id）获取其所在的所有组。"""
    if not server_name and not server_id:
        raise HTTPException(status_code=400, detail="必须提供 server_name 或 server_id")
    target = None
    if server_id:
        target = crud.get_server_by_id(db, int(server_id))
    if not target and server_name:
        # 通过目录名匹配 path 尾段
        for s in crud.get_all_servers(db):
            try:
                if Path(s.path).name == server_name:
                    target = s
                    break
            except Exception:
                continue
    if not target:
        return []
    import json as _json
    res = []
    for g in crud.list_server_link_groups(db):
        try:
            ids = list(map(int, _json.loads(g.server_ids or '[]')))
        except Exception:
            ids = []
        if target.id in ids:
            res.append(g)
    return [schemas.ServerLinkGroup.model_validate(x) for x in res]


# ===================== Chat =====================

def _user_can_access_group(user: _models.User, group_id: int) -> bool:
    """检查用户是否有权限访问指定的服务器组"""
    role_level = {'GUEST': 0, 'USER': 1, 'HELPER': 2, 'ADMIN': 3, 'OWNER': 4}
    # HELPER 及以上可以访问所有组
    if role_level.get(user.role, 0) >= role_level['HELPER']:
        return True
    # USER 只能访问其 server_link_group_ids 中的组
    try:
        user_group_ids = json.loads(user.server_link_group_ids or '[]')
    except Exception:
        user_group_ids = []
    return group_id in user_group_ids


@router.get("/tools/chat/history", response_model=list[schemas.ChatMessageOut])
async def chat_history(group_id: int, limit: int = 200, offset: int = 0, db: Session = Depends(get_db), current_user: _models.User = Depends(require_role(Role.USER))):
    # 权限验证
    if not _user_can_access_group(current_user, group_id):
        raise HTTPException(status_code=403, detail="无权限访问该服务器组")
    
    # 历史需要包含当前组内 NORMAL 消息 + 全局 ALERT 消息
    q = (
        db.query(models.ChatMessage)
        .filter(or_(models.ChatMessage.group_id == group_id, models.ChatMessage.level == 'ALERT'))
        .order_by(models.ChatMessage.created_at.desc())
    )
    if offset and offset > 0:
        q = q.offset(int(offset))
    rows = q.limit(limit).all()
    # 运行时补充 sender_avatar（不再持久化该字段）
    result: list[schemas.ChatMessageOut] = []
    for r in reversed(rows):
        out = schemas.ChatMessageOut.model_validate(r)
        # 统一时区
        try:
            if out.created_at:
                out = out.model_copy(update={"created_at": to_local_dt(out.created_at)})
        except Exception:
            pass
        avatar = None
        try:
            if r.source == 'web' and r.sender_user_id:
                u = crud.get_user_by_id(db, int(r.sender_user_id))
                avatar = u.avatar_url if u else None
        except Exception:
            avatar = None
        out = out.model_copy(update={"sender_avatar": avatar})
        result.append(out)
    return result


@router.post("/tools/chat/send", response_model=schemas.ChatMessageOut)
async def chat_send(payload: schemas.ChatSendPayload, db: Session = Depends(get_db), current_user: _models.User = Depends(require_role(Role.USER))):
    level = payload.level or "NORMAL"
    if level == "NORMAL" and not payload.group_id:
        raise HTTPException(status_code=400, detail="NORMAL 级别需要提供 group_id")
    
    # 权限验证
    if level == "NORMAL" and payload.group_id:
        if not _user_can_access_group(current_user, payload.group_id):
            raise HTTPException(status_code=403, detail="无权限访问该服务器组")
    
    # ALERT 消息只有 HELPER 及以上才能发送
    if level == "ALERT":
        role_level = {'GUEST': 0, 'USER': 1, 'HELPER': 2, 'ADMIN': 3, 'OWNER': 4}
        if role_level.get(current_user.role, 0) < role_level['HELPER']:
            raise HTTPException(status_code=403, detail="无权限发送全局消息")
    
    # 保存消息（不再持久化 sender_avatar）
    msg = models.ChatMessage(
        group_id=payload.group_id if level != "ALERT" else None,
        level=level,
        source="web",
        content=payload.message,
        sender_user_id=current_user.id,
        sender_username=current_user.username,
    )
    msg = crud.create_chat_message(db, msg)
    # 运行时补充 sender_avatar 用于响应与广播
    out = schemas.ChatMessageOut.model_validate(msg).model_copy(update={
        "sender_avatar": current_user.avatar_url,
        "created_at": to_local_dt(msg.created_at) if getattr(msg, 'created_at', None) else None,
    })
    # 广播给 Web 前端
    await sio.emit("chat_message", out.model_dump(mode='json'))
    # 广播给插件端 / QQ
    await broadcast_chat_to_plugins(
        level=level,
        group_id=payload.group_id,
        user=current_user.username,
        message=payload.message,
        source="web",
        avatar=current_user.avatar_url,
    )
    if payload.group_id:
        try:
            await onebot.relay_web_message_to_qq(payload.group_id, current_user.username, payload.message)
        except Exception:
            pass
    return out
