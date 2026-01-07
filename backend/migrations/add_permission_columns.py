"""
数据库迁移脚本：添加 is_owner 和 is_admin 列，以及 UserGroupPermission 唯一约束
运行方式: python -m backend.migrations.add_permission_columns
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect
from backend.core.database import SessionLocal, engine
from backend.core import models


def add_columns():
    """添加 is_owner 和 is_admin 列到 users 表"""
    print("检查并添加 is_owner/is_admin 列...")
    
    inspector = inspect(engine)
    existing_columns = [col['name'] for col in inspector.get_columns('users')]
    
    with engine.connect() as conn:
        # 添加 is_owner 列
        if 'is_owner' not in existing_columns:
            print("  添加 is_owner 列...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_owner BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
            print("  ✓ is_owner 列已添加")
        else:
            print("  - is_owner 列已存在")
        
        # 添加 is_admin 列
        if 'is_admin' not in existing_columns:
            print("  添加 is_admin 列...")
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
            print("  ✓ is_admin 列已添加")
        else:
            print("  - is_admin 列已存在")
        
        # 添加 token_version 列
        if 'token_version' not in existing_columns:
            print("  添加 token_version 列...")
            conn.execute(text("ALTER TABLE users ADD COLUMN token_version INTEGER DEFAULT 0 NOT NULL"))
            conn.commit()
            print("  ✓ token_version 列已添加")
        else:
            print("  - token_version 列已存在")


def migrate_roles():
    """从旧的 role 字段迁移到新的 is_owner/is_admin 字段"""
    print("\n迁移用户权限...")
    
    # 使用原生 SQL 避免 ORM 约束问题
    with engine.connect() as conn:
        # 检查 role 列是否存在
        inspector = inspect(engine)
        existing_columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'role' not in existing_columns:
            print("  - role 列不存在，跳过迁移")
            return
        
        # 获取所有用户的角色
        result = conn.execute(text("SELECT id, username, role FROM users WHERE role IS NOT NULL"))
        users = result.fetchall()
        
        migrated = 0
        for user_id, username, old_role in users:
            if old_role == 'OWNER':
                conn.execute(text("UPDATE users SET is_owner = 1, is_admin = 0 WHERE id = :id"), {"id": user_id})
                migrated += 1
                print(f"  用户 {username}: OWNER -> is_owner=True")
            elif old_role == 'ADMIN':
                conn.execute(text("UPDATE users SET is_owner = 0, is_admin = 1 WHERE id = :id"), {"id": user_id})
                migrated += 1
                print(f"  用户 {username}: ADMIN -> is_admin=True")
            else:
                conn.execute(text("UPDATE users SET is_owner = 0, is_admin = 0 WHERE id = :id"), {"id": user_id})
        
        conn.commit()
        print(f"  ✓ 迁移完成: {migrated} 个管理员用户已迁移")
    
    # 尝试移除 role 列的 NOT NULL 约束（SQLite 需要重建表，这里跳过）
    print("  注意: role 列保留但不再使用，可手动清理")


def ensure_first_owner():
    """确保至少有一个 OWNER"""
    print("\n检查 OWNER 用户...")
    
    db = SessionLocal()
    try:
        owner_count = db.query(models.User).filter(models.User.is_owner == True).count()
        
        if owner_count == 0:
            # 查找第一个用户并设为 OWNER
            first_user = db.query(models.User).order_by(models.User.id.asc()).first()
            if first_user:
                first_user.is_owner = True
                db.commit()
                print(f"  ✓ 已将用户 {first_user.username} 设置为 OWNER")
            else:
                print("  - 没有用户，跳过")
        else:
            print(f"  - 已有 {owner_count} 个 OWNER 用户")
    finally:
        db.close()


def create_user_group_permissions_table():
    """创建 user_group_permissions 表（如果不存在）"""
    print("\n检查 user_group_permissions 表...")
    
    inspector = inspect(engine)
    if 'user_group_permissions' not in inspector.get_table_names():
        print("  创建 user_group_permissions 表...")
        models.UserGroupPermission.__table__.create(engine)
        print("  ✓ 表已创建")
    else:
        print("  - 表已存在")


def verify():
    """验证迁移结果"""
    print("\n验证迁移结果...")
    db = SessionLocal()
    try:
        owners = db.query(models.User).filter(models.User.is_owner == True).count()
        admins = db.query(models.User).filter(models.User.is_admin == True).count()
        total = db.query(models.User).count()
        
        print(f"  用户统计: 总数={total}, OWNER={owners}, ADMIN={admins}, 普通用户={total - owners - admins}")
        
        # 检查是否有遗留的旧 role 值
        with_role = db.query(models.User).filter(models.User.role.isnot(None)).count()
        if with_role > 0:
            print(f"  ⚠ 还有 {with_role} 个用户有未清理的 role 字段")
        else:
            print("  ✓ 所有用户的 role 字段已清理")
        
        if owners == 0:
            print("  ⚠ 警告: 没有 OWNER 用户！")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("权限系统数据库迁移")
    print("=" * 50)
    
    add_columns()
    create_user_group_permissions_table()
    migrate_roles()
    ensure_first_owner()
    verify()
    
    print("\n" + "=" * 50)
    print("迁移完成！")
    print("=" * 50)
