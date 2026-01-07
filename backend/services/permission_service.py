"""权限服务层 - 统一处理用户权限和服务器访问控制"""
import json
from typing import List, Optional, Callable
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status

from backend.core import models, crud, schemas
from backend.core.database import get_db


class PermissionService:
    """权限服务"""
    
    @staticmethod
    def get_user_role_level(role: str) -> int:
        """获取角色等级"""
        # 支持字符串和 Role 枚举
        if isinstance(role, schemas.Role):
            return schemas.ROLE_HIERARCHY.get(role, -1)
        try:
            role_enum = schemas.Role(role)
            return schemas.ROLE_HIERARCHY.get(role_enum, -1)
        except ValueError:
            return -1
    
    @staticmethod
    def get_user_group_role_level(db: Session, user: models.User, group_id: int) -> int:
        """获取用户在特定组的角色等级"""
        user_perms = crud.get_user_group_permissions(db, user.id)
        for perm in user_perms:
            if perm.group_id == group_id:
                return PermissionService.get_user_role_level(perm.role)
        return -1
    
    @staticmethod
    def get_effective_role_level(db: Session, user: models.User, server_id: Optional[int] = None) -> int:
        """获取有效权限等级（全局和组权限取高）"""
        global_level = PermissionService.get_user_role_level(user.role)
        
        if server_id is None:
            return global_level
        
        # 获取服务器所属的组
        server_groups = crud.get_server_link_groups_for_servers(db, [server_id])
        if not server_groups:
            return global_level
        
        # 获取用户在这些组中的最高权限
        user_perms = crud.get_user_group_permissions(db, user.id)
        max_group_level = -1
        for perm in user_perms:
            if perm.group_id in server_groups:
                level = PermissionService.get_user_role_level(perm.role)
                if level > max_group_level:
                    max_group_level = level
        
        return max(global_level, max_group_level)
    
    @staticmethod
    def check_role(user: models.User, required_role: schemas.Role) -> bool:
        """检查用户是否具有指定角色权限"""
        user_level = PermissionService.get_user_role_level(user.role)
        required_level = schemas.ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level
    
    @staticmethod
    def assert_role(user: models.User, required_role: schemas.Role):
        """断言用户具有指定角色，否则抛出403"""
        if not PermissionService.check_role(user, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 '{required_role.value}' 或更高权限"
            )
    
    @staticmethod
    def can_access_server(db: Session, user: models.User, server_id: int) -> bool:
        """检查用户是否可以访问指定服务器"""
        # OWNER 可访问所有
        if user.role == "OWNER":
            return True
        
        # ADMIN 可访问所有
        if user.role == "ADMIN":
            return True
        
        # 获取服务器所属的组
        server = crud.get_server_by_id(db, server_id)
        if not server:
            return False
        
        # 检查用户是否有该服务器所在组的权限（且组内角色 >= GUEST）
        user_perms = crud.get_user_group_permissions(db, user.id)
        user_group_ids = {p.group_id for p in user_perms if PermissionService.get_user_role_level(p.role) >= 0}
        
        # 获取服务器所属的组
        server_groups = crud.get_server_link_groups_for_servers(db, [server_id])
        
        # 检查是否有交集
        return bool(set(server_groups) & user_group_ids)
    
    @staticmethod
    def get_accessible_servers(db: Session, user: models.User) -> List[int]:
        """获取用户可访问的服务器ID列表"""
        # OWNER/ADMIN 可访问所有
        if user.role in ("OWNER", "ADMIN"):
            servers = crud.get_all_servers(db)
            return [s.id for s in servers]
        
        # 获取用户的组权限
        user_perms = crud.get_user_group_permissions(db, user.id)
        user_group_ids = [p.group_id for p in user_perms]
        
        if not user_group_ids:
            return []
        
        # 获取这些组关联的服务器
        server_ids = set()
        for group_id in user_group_ids:
            group = db.query(models.ServerLinkGroup).filter(
                models.ServerLinkGroup.id == group_id
            ).first()
            if group and group.server_ids:
                try:
                    ids = json.loads(group.server_ids)
                    server_ids.update(ids)
                except:
                    pass
        
        return list(server_ids)
    
    @staticmethod
    def can_modify_user(actor: models.User, target: models.User) -> bool:
        """检查 actor 是否可以修改 target 用户"""
        actor_level = PermissionService.get_user_role_level(actor.role)
        target_level = PermissionService.get_user_role_level(target.role)
        
        # 不能修改比自己权限高或相同的用户（除非是 OWNER）
        if actor.role != "OWNER" and target_level >= actor_level:
            return False
        
        return True
    
    @staticmethod
    def can_change_role(actor: models.User, target: models.User, new_role: str) -> bool:
        """检查 actor 是否可以将 target 的角色改为 new_role"""
        actor_level = PermissionService.get_user_role_level(actor.role)
        target_level = PermissionService.get_user_role_level(target.role)
        new_level = PermissionService.get_user_role_level(new_role)
        
        # OWNER 可以设置任何角色（但不能降级自己）
        if actor.role == "OWNER":
            if actor.id == target.id and new_level < actor_level:
                return False  # OWNER 不能降级自己
            return True
        
        # ADMIN 只能设置比自己低的角色
        if actor.role == "ADMIN":
            if target_level >= actor_level:
                return False  # 不能修改同级或更高
            if new_level >= actor_level:
                return False  # 不能提升到同级或更高
            return True
        
        return False
    
    @staticmethod
    def increment_token_version(db: Session, user: models.User) -> int:
        """增加用户的 token_version，使所有现有 token 失效"""
        user.token_version = (user.token_version or 0) + 1
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.token_version


def require_server_access(server_id_param: str = "server_id") -> Callable:
    """FastAPI 依赖工厂函数，检查用户是否有权访问指定服务器"""
    from backend.core.auth import get_current_user
    
    def server_access_checker(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        **kwargs
    ) -> models.User:
        # 从路径参数或查询参数获取 server_id
        server_id = kwargs.get(server_id_param)
        if server_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"缺少 {server_id_param} 参数"
            )
        
        if not PermissionService.can_access_server(db, current_user, int(server_id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此服务器"
            )
        return current_user
    
    return server_access_checker


# 单例实例
permission_service = PermissionService()
