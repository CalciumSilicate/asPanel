"""
数据迁移脚本：将 ServerLinkGroup.server_ids 和 data_source_ids JSON 字段迁移到关联表
运行方式: python -m backend.migrations.migrate_group_servers
"""
import json
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from backend.core.database import SessionLocal, engine
from backend.core import models


def migrate():
    """执行迁移"""
    print("开始迁移 ServerLinkGroup 关联数据...")
    
    # 创建新表（如果不存在）
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 获取所有服务器组
        groups = db.query(models.ServerLinkGroup).all()
        
        migrated_servers = 0
        migrated_datasources = 0
        
        for group in groups:
            # 迁移 server_ids
            try:
                server_ids = json.loads(group.server_ids or "[]")
                for server_id in server_ids:
                    # 检查是否已存在
                    existing = db.query(models.GroupServer).filter(
                        models.GroupServer.group_id == group.id,
                        models.GroupServer.server_id == server_id
                    ).first()
                    if not existing:
                        # 验证服务器存在
                        server = db.query(models.Server).filter(models.Server.id == server_id).first()
                        if server:
                            db.add(models.GroupServer(group_id=group.id, server_id=server_id))
                            migrated_servers += 1
            except (json.JSONDecodeError, TypeError):
                print(f"  警告: 组 {group.id} 的 server_ids 解析失败，跳过")
            
            # 迁移 data_source_ids
            try:
                ds_ids = json.loads(group.data_source_ids or "[]")
                for ds_id in ds_ids:
                    existing = db.query(models.GroupDataSource).filter(
                        models.GroupDataSource.group_id == group.id,
                        models.GroupDataSource.data_source_id == ds_id
                    ).first()
                    if not existing:
                        db.add(models.GroupDataSource(group_id=group.id, data_source_id=ds_id))
                        migrated_datasources += 1
            except (json.JSONDecodeError, TypeError):
                print(f"  警告: 组 {group.id} 的 data_source_ids 解析失败，跳过")
        
        db.commit()
        print(f"迁移完成: {migrated_servers} 个服务器关联, {migrated_datasources} 个数据源关联")
        
    except Exception as e:
        db.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        db.close()


def verify():
    """验证迁移结果"""
    print("\n验证迁移结果...")
    db = SessionLocal()
    try:
        groups = db.query(models.ServerLinkGroup).all()
        all_ok = True
        
        for group in groups:
            # 对比 JSON 和关联表
            try:
                json_server_ids = set(json.loads(group.server_ids or "[]"))
            except:
                json_server_ids = set()
            
            table_server_ids = set(
                r.server_id for r in 
                db.query(models.GroupServer).filter(models.GroupServer.group_id == group.id).all()
            )
            
            # 只检查关联表包含了 JSON 中存在且服务器还在的 ID
            valid_json_ids = set()
            for sid in json_server_ids:
                if db.query(models.Server).filter(models.Server.id == sid).first():
                    valid_json_ids.add(sid)
            
            if valid_json_ids != table_server_ids:
                print(f"  组 {group.id} ({group.name}): JSON={valid_json_ids}, 表={table_server_ids}")
                all_ok = False
        
        if all_ok:
            print("所有数据验证通过！")
        else:
            print("存在不一致的数据，请检查")
            
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
    verify()
