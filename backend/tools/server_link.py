# backend/tools/server_link.py

from sqlalchemy.orm import Session
from typing import List

from backend.core import crud, schemas


def _validate_server_ids(db: Session, server_ids: List[int]) -> List[int]:
    """验证 server_ids 均存在，不存在的将被过滤并抛出异常。

    当前策略：若有不存在的 ID，直接抛出 ValueError；也可改为静默过滤。
    """
    if not server_ids:
        return []
    valid_ids: List[int] = []
    missing: List[int] = []
    for sid in server_ids:
        if crud.get_server_by_id(db, int(sid)):
            valid_ids.append(int(sid))
        else:
            missing.append(int(sid))
    if missing:
        raise ValueError(f"以下服务器ID不存在: {missing}")
    return valid_ids


async def sl_list_groups(db: Session) -> List[schemas.ServerLinkGroup]:
    rows = crud.list_server_link_groups(db)
    return [schemas.ServerLinkGroup.model_validate(r) for r in rows]


async def sl_create_group(db: Session, payload: schemas.ServerLinkGroupCreate) -> schemas.ServerLinkGroup:
    payload.server_ids = _validate_server_ids(db, payload.server_ids)
    if payload.data_source_ids:
        payload.data_source_ids = _validate_server_ids(db, payload.data_source_ids)
    rec = crud.create_server_link_group(db, payload)
    return schemas.ServerLinkGroup.model_validate(rec)


async def sl_update_group(db: Session, group_id: int, payload: schemas.ServerLinkGroupUpdate) -> schemas.ServerLinkGroup:
    if payload.server_ids is not None:
        payload.server_ids = _validate_server_ids(db, payload.server_ids)
    if payload.data_source_ids is not None:
        payload.data_source_ids = _validate_server_ids(db, payload.data_source_ids)
    rec = crud.update_server_link_group(db, group_id, payload)
    if not rec:
        raise ValueError("服务器组不存在")
    return schemas.ServerLinkGroup.model_validate(rec)


async def sl_delete_group(db: Session, group_id: int) -> bool:
    rec = crud.delete_server_link_group(db, group_id)
    return rec is not None
