"""权限服务层 - 统一处理用户权限和服务器访问控制"""
import json
from typing import List, Optional, Callable, Union
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status

from backend.core import models, crud, schemas
from backend.core.database import get_db


class PermissionService:
    """权限服务"""
    
    @staticmethod
    def is_super_user(user: models.User) -> bool:
        """检查用户是否是超级用户（OWNER 或 ADMIN）"""
        return user.is_owner or user.is_admin
    
    @staticmethod
    def get_group_role_level(role: Union[str, schemas.GroupRole]) -> int:
        """获取组角色等级"""
        if isinstance(role, schemas.GroupRole):
            return schemas.GROUP_ROLE_HIERARCHY.get(role, 0)
        try:
            role_enum = schemas.GroupRole(role)
            return schemas.GROUP_ROLE_HIERARCHY.get(role_enum, 0)
        except ValueError:
            return 0
    
    @staticmethod
    def get_user_group_role(db: Session, user: models.User, group_id: int) -> Optional[str]:
        """获取用户在特定组的角色"""
        user_perms = crud.get_user_group_permissions(db, user.id)
        for perm in user_perms:
            if perm.group_id == group_id:
                return perm.role
        return None
    
    @staticmethod
    def get_user_group_role_level(db: Session, user: models.User, group_id: int) -> int:
        """获取用户在特定组的角色等级"""
        role = PermissionService.get_user_group_role(db, user, group_id)
        if role:
            return PermissionService.get_group_role_level(role)
        return 0
    
    @staticmethod
    def check_group_role(db: Session, user: models.User, group_id: int, required_role: schemas.GroupRole) -> bool:
        """检查用户在指定组是否具有指定角色权限"""
        # OWNER/ADMIN 在所有组都有最高权限
        if user.is_owner or user.is_admin:
            return True
        
        user_level = PermissionService.get_user_group_role_level(db, user, group_id)
        required_level = schemas.GROUP_ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level
    
    @staticmethod
    def can_access_server(db: Session, user: models.User, server_id: int) -> bool:
        """检查用户是否可以访问指定服务器"""
        # OWNER/ADMIN 可访问所有
        if user.is_owner or user.is_admin:
            return True
        
        # 获取服务器所属的组
        server = crud.get_server_by_id(db, server_id)
        if not server:
            return False
        
        # 检查用户是否有该服务器所在组的权限
        user_perms = crud.get_user_group_permissions(db, user.id)
        user_group_ids = {p.group_id for p in user_perms}
        
        # 获取服务器所属的组
        server_groups = crud.get_server_link_groups_for_servers(db, [server_id])
        
        # 检查是否有交集
        return bool(set(server_groups) & user_group_ids)
    
    @staticmethod
    def get_accessible_servers(db: Session, user: models.User) -> List[int]:
        """获取用户可访问的服务器ID列表"""
        # OWNER/ADMIN 可访问所有
        if user.is_owner or user.is_admin:
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
        # 只有 OWNER 可以修改其他用户的全局权限
        if not actor.is_owner:
            # ADMIN 可以修改组权限，但不能修改全局权限
            if target.is_owner:
                return False  # 非 OWNER 不能修改 OWNER
        return True
    
    @staticmethod
    def can_change_global_permission(actor: models.User, target: models.User) -> bool:
        """检查 actor 是否可以修改 target 的全局权限（is_owner/is_admin）"""
        # 只有 OWNER 可以修改全局权限
        if not actor.is_owner:
            return False
        # OWNER 不能降级自己
        if actor.id == target.id:
            return False
        return True
    
    @staticmethod
    def can_change_group_permission(actor: models.User, target: models.User) -> bool:
        """检查 actor 是否可以修改 target 的组权限"""
        # OWNER 可以修改任何人的组权限
        if actor.is_owner:
            return True
        # ADMIN 可以修改非 OWNER 用户的组权限
        if actor.is_admin and not target.is_owner:
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
    
    # DEPRECATED: 保留用于向后兼容
    @staticmethod
    def get_user_role_level(role: str) -> int:
        """DEPRECATED: 获取旧版角色等级"""
        if isinstance(role, schemas.Role):
            return schemas.ROLE_HIERARCHY.get(role, -1)
        try:
            role_enum = schemas.Role(role)
            return schemas.ROLE_HIERARCHY.get(role_enum, -1)
        except ValueError:
            return -1


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


def require_group_role(group_id_param: str = "group_id", required_role: schemas.GroupRole = schemas.GroupRole.USER) -> Callable:
    """FastAPI 依赖工厂函数，检查用户在指定组是否有指定权限"""
    from backend.core.auth import get_current_user
    
    def group_role_checker(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
        **kwargs
    ) -> models.User:
        group_id = kwargs.get(group_id_param)
        if group_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"缺少 {group_id_param} 参数"
            )
        
        if not PermissionService.check_group_role(db, current_user, int(group_id), required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您在该组没有 {required_role.value} 或更高权限"
            )
        return current_user
    
    return group_role_checker


# 单例实例
permission_service = PermissionService()
