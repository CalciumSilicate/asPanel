"""
数据迁移脚本：将旧的 role 字段迁移到新的 is_owner/is_admin 字段
运行方式: python -m backend.migrations.migrate_user_permissions
"""
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
    print("开始迁移用户权限...")
    
    # 创建新列（如果不存在）
    models.Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # 获取所有用户
        users = db.query(models.User).all()
        
        migrated = 0
        for user in users:
            old_role = getattr(user, 'role', None)
            if old_role is None:
                continue
                
            # 根据旧的 role 设置新的布尔字段
            if old_role == 'OWNER':
                user.is_owner = True
                user.is_admin = False
                migrated += 1
            elif old_role == 'ADMIN':
                user.is_owner = False
                user.is_admin = True
                migrated += 1
            else:
                # GUEST, USER, HELPER 都是普通用户
                user.is_owner = False
                user.is_admin = False
            
            # 清除旧的 role 字段
            user.role = None
        
        db.commit()
        print(f"迁移完成: {migrated} 个管理员用户已迁移")
        
    except Exception as e:
        db.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        db.close()


def migrate_group_permissions():
    """迁移组权限：移除 GUEST 和 OWNER，转换为 USER 和 ADMIN"""
    print("\n开始迁移组权限...")
    
    db = SessionLocal()
    try:
        perms = db.query(models.UserGroupPermission).all()
        
        migrated = 0
        for perm in perms:
            old_role = perm.role
            if old_role == 'GUEST':
                perm.role = 'USER'
                migrated += 1
            elif old_role == 'OWNER':
                perm.role = 'ADMIN'
                migrated += 1
        
        db.commit()
        print(f"组权限迁移完成: {migrated} 条记录已更新")
        
    except Exception as e:
        db.rollback()
        print(f"组权限迁移失败: {e}")
        raise
    finally:
        db.close()


def verify():
    """验证迁移结果"""
    print("\n验证迁移结果...")
    db = SessionLocal()
    try:
        # 检查用户
        owners = db.query(models.User).filter(models.User.is_owner == True).count()
        admins = db.query(models.User).filter(models.User.is_admin == True).count()
        total = db.query(models.User).count()
        
        print(f"用户统计: 总数={total}, OWNER={owners}, ADMIN={admins}, 普通用户={total - owners - admins}")
        
        # 检查是否有遗留的旧 role 值
        with_role = db.query(models.User).filter(models.User.role.isnot(None)).count()
        if with_role > 0:
            print(f"警告: 还有 {with_role} 个用户有未清理的 role 字段")
        else:
            print("所有用户的 role 字段已清理")
        
        # 检查组权限
        guest_perms = db.query(models.UserGroupPermission).filter(
            models.UserGroupPermission.role == 'GUEST'
        ).count()
        owner_perms = db.query(models.UserGroupPermission).filter(
            models.UserGroupPermission.role == 'OWNER'
        ).count()
        
        if guest_perms > 0 or owner_perms > 0:
            print(f"警告: 组权限中还有 GUEST={guest_perms}, OWNER={owner_perms} 条记录未迁移")
        else:
            print("组权限迁移验证通过")
            
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
    migrate_group_permissions()
    verify()
