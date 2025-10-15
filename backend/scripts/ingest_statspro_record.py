#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 StatsPro 预存目录导入数据到 asPanel 主库（对齐到 10 分钟）。

数据目录结构：
  {record_root}/{YYYY-MM-DD-HH-mm-ss}/{UUID}.json

JSON 内容格式与 MC 原版 stats 相同，示例：
{
  "stats": {
    "minecraft:custom": {
      "minecraft:play_time": 12345,
      "minecraft:play_one_minute": 12345
    },
    "minecraft:used": {
      "minecraft:diamond_pickaxe": 12
    }
  }
}

使用方式：
  python backend/scripts/ingest_statspro_record.py \
    --server-id 1 \
    --record-root /home/arch/assX/asPanel/storages/mcdr-server/Survival/config/StatsPro/record \
    [--namespace minecraft] [--dry-run]

注意：
- 本脚本按快照目录时间升序导入，并将快照时间对齐到 10 分钟边界（floor）。
- 对每个 (server, player, metric, ts) 执行 upsert：如已存在则更新 total/delta；否则插入。
- delta 计算规则与后端一致：delta = curr_total - prev_total（可能为负，保持原样）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import select, func

# 复用后端 ORM 与会话
from backend.database import SessionLocal
from backend import models


STEP = 600  # 10min


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest StatsPro record snapshots into asPanel DB (10min aligned)")
    p.add_argument("--server-id", type=int, required=True, help="目标服务器 ID（asPanel 数据库内 server_id）")
    p.add_argument("--record-root", type=str, required=True, help="StatsPro record 目录根路径")
    p.add_argument("--namespace", type=str, default="minecraft", help="命名空间，默认 minecraft")
    p.add_argument("--dry-run", action="store_true", help="试运行：仅打印概要，不写入数据库")
    return p.parse_args()


def align_10min(ts: int) -> int:
    return ts - (ts % STEP)


def parse_snapshot_ts(name: str) -> Optional[int]:
    """将目录名 YYYY-MM-DD-HH-mm-ss 解析为时间戳（秒）。"""
    try:
        dt_obj = dt.datetime.strptime(name, "%Y-%m-%d-%H-%M-%S")
        return int(dt_obj.timestamp())
    except Exception:
        return None


def iter_snapshot_dirs(root: Path) -> List[Tuple[int, Path]]:
    out: List[Tuple[int, Path]] = []
    for p in root.iterdir():
        if not p.is_dir():
            continue
        ts = parse_snapshot_ts(p.name)
        if ts is None:
            continue
        out.append((ts, p))
    out.sort(key=lambda x: x[0])
    return out


def _metric_pairs_from_json(js: dict, namespace: str) -> List[Tuple[str, str, int]]:
    """从 JSON stats 提取 (category_key, item_key, value) 列表。

    返回：[("minecraft:custom", "minecraft:play_time", 123), ...]
    仅保留命名空间与 namespace 一致的键。
    """
    out: List[Tuple[str, str, int]] = []
    stats = js.get("stats", {}) or {}
    for cat_ns, items in stats.items():
        if not isinstance(items, dict):
            continue
        try:
            ns1, cat = str(cat_ns).split(":", 1)
        except ValueError:
            continue
        if ns1 != namespace:
            continue
        for item_ns, val in items.items():
            try:
                ns2, item = str(item_ns).split(":", 1)
            except ValueError:
                continue
            if ns2 != namespace:
                continue
            try:
                v = int(val or 0)
            except Exception:
                v = 0
            out.append((f"{namespace}:{cat}", f"{namespace}:{item}", v))
    return out


def ensure_metric_ids(db, pairs: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], int]:
    """确保一组 (category_key, item_key) 在 MetricsDim 中存在，返回映射。"""
    out: Dict[Tuple[str, str], int] = {}
    for cat_key, item_key in pairs:
        m_id = db.scalar(
            select(models.MetricsDim.metric_id)
            .where(models.MetricsDim.category == cat_key, models.MetricsDim.item == item_key)
        )
        if m_id is None:
            obj = models.MetricsDim(category=cat_key, item=item_key)
            db.add(obj)
            db.flush()
            m_id = obj.metric_id
        out[(cat_key, item_key)] = int(m_id)
    return out


def ensure_player_id(db, uuid: str) -> int:
    pid = db.scalar(select(models.Player.id).where(models.Player.uuid == uuid))
    if pid is not None:
        return int(pid)
    obj = models.Player(uuid=uuid, player_name=None, play_time="{}", is_offline=True)
    db.add(obj)
    db.flush()
    return int(obj.id)


def upsert_metrics_for_snapshot(db, *, server_id: int, ts: int, uuid: str, metrics: List[Tuple[str, str, int]]):
    """对单个玩家的一个快照进行 upsert。

    metrics: [(cat_key, item_key, total_value), ...]
    """
    pid = ensure_player_id(db, uuid)

    # 预备 metric_id
    key_pairs = [(ck, ik) for (ck, ik, _v) in metrics]
    mid_map = ensure_metric_ids(db, key_pairs)

    # 查询上一时刻 total（<= ts-1）
    metric_ids = [mid_map[(ck, ik)] for (ck, ik, _v) in metrics]
    if not metric_ids:
        return 0
    sub = (
        select(models.PlayerMetrics.metric_id, func.max(models.PlayerMetrics.ts).label("mts"))
        .where(
            models.PlayerMetrics.server_id == server_id,
            models.PlayerMetrics.player_id == pid,
            models.PlayerMetrics.metric_id.in_(metric_ids),
            models.PlayerMetrics.ts <= ts - 1,
        )
        .group_by(models.PlayerMetrics.metric_id)
        .subquery()
    )
    prev_rows = db.execute(
        select(models.PlayerMetrics.metric_id, models.PlayerMetrics.total)
        .join(sub, (models.PlayerMetrics.metric_id == sub.c.metric_id) & (models.PlayerMetrics.ts == sub.c.mts))
        .where(models.PlayerMetrics.server_id == server_id, models.PlayerMetrics.player_id == pid)
    ).all()
    prev_map = {int(mid): int(t or 0) for (mid, t) in prev_rows}

    # upsert
    affected = 0
    for cat_key, item_key, curr_total in metrics:
        mid = mid_map[(cat_key, item_key)]
        prev_total = prev_map.get(mid)
        delta = int(curr_total) - int(prev_total or 0) if prev_total is not None else 0

        existing = db.execute(
            select(models.PlayerMetrics)
            .where(
                models.PlayerMetrics.server_id == server_id,
                models.PlayerMetrics.player_id == pid,
                models.PlayerMetrics.metric_id == mid,
                models.PlayerMetrics.ts == ts,
            )
        ).scalar_one_or_none()
        if existing is None:
            obj = models.PlayerMetrics(
                ts=ts, server_id=server_id, player_id=pid, metric_id=mid, total=int(curr_total), delta=int(delta)
            )
            db.add(obj)
        else:
            existing.total = int(curr_total)
            existing.delta = int(delta)
            db.add(existing)
        affected += 1
    return affected


def ingest_record_root(server_id: int, record_root: Path, namespace: str = "minecraft", dry_run: bool = False) -> int:
    snaps = iter_snapshot_dirs(record_root)
    if not snaps:
        print(f"[WARN] 未在 {record_root} 发现快照目录")
        return 0

    total_rows = 0
    with SessionLocal() as db:
        for raw_ts, snap_dir in snaps:
            ts = align_10min(raw_ts)
            files = sorted(snap_dir.glob("*.json"))
            if not files:
                continue
            batch_rows = 0
            for fp in files:
                uuid = fp.stem
                try:
                    js = json.loads(fp.read_text(encoding="utf-8"))
                except Exception:
                    print(f"[WARN] 解析失败，跳过: {fp}")
                    continue
                pairs = _metric_pairs_from_json(js, namespace)
                if not pairs:
                    continue
                if not dry_run:
                    n = upsert_metrics_for_snapshot(db, server_id=server_id, ts=ts, uuid=uuid, metrics=pairs)
                else:
                    n = len(pairs)
                batch_rows += int(n or 0)
            if not dry_run:
                db.commit()
            print(f"[INFO] 导入快照 {snap_dir.name} (ts={ts}) | 写入行数={batch_rows}")
            total_rows += batch_rows
    return total_rows


def main():
    args = parse_args()
    root = Path(args.record_root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"record-root 不存在或不可读: {root}")
    rows = ingest_record_root(args.server_id, root, namespace=args.namespace, dry_run=args.dry_run)
    print(f"[DONE] 导入完成，累计写入行数={rows} (dry_run={args.dry_run})")


if __name__ == "__main__":
    main()

