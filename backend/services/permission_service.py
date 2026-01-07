"""权限服务层 - 统一处理用户权限和服务器访问控制

权限层级:
- OWNER: 超级管理员，可控制一切，包括设置 is_admin
- ADMIN: 平台管理员，可控制除 is_owner/is_admin 外的一切（系统设置、所有服务器）
- 组 ADMIN: 只能管理自己所属组的一切
- 组 HELPER: 只能在组内执行操作（插件、配置等）
- 组 USER: 只能查看组内的内容

组之间完全隔离，用户只能看到自己有权限的组。
"""
import json
from enum import Enum
from typing import List, Optional, Callable, Union, Set
from sqlalchemy.orm import Session
from fastapi import Depends, HTTPException, status, Path

from backend.core import models, crud, schemas
from backend.core.database import get_db


class GroupAction(str, Enum):
    """组内权限动作"""
    VIEW = "VIEW"      # 查看（USER+）
    MANAGE = "MANAGE"  # 管理操作（HELPER+）
    ADMIN = "ADMIN"    # 管理员操作（组ADMIN）


# 动作所需的最低组角色
ACTION_REQUIRED_ROLE = {
    GroupAction.VIEW: schemas.GroupRole.USER,
    GroupAction.MANAGE: schemas.GroupRole.HELPER,
    GroupAction.ADMIN: schemas.GroupRole.ADMIN,
}


class PermissionService:
    """权限服务"""
    
    @staticmethod
    def is_owner(user: models.User) -> bool:
        """检查用户是否是 OWNER"""
        return user.is_owner
    
    @staticmethod
    def is_platform_admin(user: models.User) -> bool:
        """检查用户是否是平台管理员（OWNER 或 ADMIN）
        
        平台管理员可以访问系统设置、所有服务器等，但 ADMIN 不能修改权限字段
        """
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
    def get_user_groups(db: Session, user: models.User) -> List[int]:
        """获取用户所属的所有组ID"""
        user_perms = crud.get_user_group_permissions(db, user.id)
        return [p.group_id for p in user_perms]
    
    @staticmethod
    def check_group_permission(
        db: Session, 
        user: models.User, 
        group_id: int, 
        action: GroupAction = GroupAction.VIEW
    ) -> bool:
        """检查用户在指定组是否有执行某动作的权限
        
        注意：OWNER/ADMIN 不再自动拥有组权限，组之间完全隔离！
        只有 OWNER 可以绕过组隔离访问所有组。
        """
        # 只有 OWNER 可以绕过组隔离
        if user.is_owner:
            return True
        
        # ADMIN 只能访问系统级功能，不能自动访问任意组
        # ADMIN 如果要访问某个组，必须被加入该组
        
        required_role = ACTION_REQUIRED_ROLE.get(action, schemas.GroupRole.USER)
        user_level = PermissionService.get_user_group_role_level(db, user, group_id)
        required_level = schemas.GROUP_ROLE_HIERARCHY.get(required_role, 0)
        
        return user_level >= required_level
    
    @staticmethod
    def check_group_role(
        db: Session, 
        user: models.User, 
        group_id: int, 
        required_role: schemas.GroupRole
    ) -> bool:
        """检查用户在指定组是否具有指定角色权限（兼容旧接口）"""
        # 只有 OWNER 可以绕过组隔离
        if user.is_owner:
            return True
        
        user_level = PermissionService.get_user_group_role_level(db, user, group_id)
        required_level = schemas.GROUP_ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level
    
    @staticmethod
    def can_access_server(db: Session, user: models.User, server_id: int) -> bool:
        """检查用户是否可以访问指定服务器
        
        - OWNER: 可访问所有服务器
        - ADMIN: 可访问所有服务器（平台管理员权限）
        - 其他用户: 必须在包含该服务器的组中有权限
        """
        # 平台管理员可访问所有服务器
        if user.is_owner or user.is_admin:
            return True
        
        # 获取服务器所属的组
        server = crud.get_server_by_id(db, server_id)
        if not server:
            return False
        
        # 获取用户所属的组
        user_group_ids = set(PermissionService.get_user_groups(db, user))
        if not user_group_ids:
            return False
        
        # 获取服务器所属的组（使用关联表）
        server_group_ids = set(crud.get_server_link_groups_for_servers_v2(db, [server_id]))
        if not server_group_ids:
            # 如果服务器不属于任何组，回退到 JSON 字段
            server_group_ids = set(crud.get_server_link_groups_for_servers(db, [server_id]))
        
        # 检查是否有交集
        return bool(server_group_ids & user_group_ids)
    
    @staticmethod
    def can_manage_server(
        db: Session, 
        user: models.User, 
        server_id: int, 
        action: GroupAction = GroupAction.MANAGE
    ) -> bool:
        """检查用户是否可以管理指定服务器（需要 HELPER+ 权限）
        
        - OWNER: 可管理所有服务器
        - ADMIN: 可管理所有服务器
        - 组 ADMIN: 可管理组内服务器
        - 组 HELPER: 可执行管理操作（插件、配置等）
        - 组 USER: 只能查看
        """
        # 平台管理员可管理所有服务器
        if user.is_owner or user.is_admin:
            return True
        
        # 获取服务器所属的组
        server = crud.get_server_by_id(db, server_id)
        if not server:
            return False
        
        # 获取服务器所属的组
        server_group_ids = set(crud.get_server_link_groups_for_servers_v2(db, [server_id]))
        if not server_group_ids:
            server_group_ids = set(crud.get_server_link_groups_for_servers(db, [server_id]))
        
        if not server_group_ids:
            return False
        
        # 检查用户在任一服务器所属组中是否有足够权限
        required_role = ACTION_REQUIRED_ROLE.get(action, schemas.GroupRole.HELPER)
        required_level = schemas.GROUP_ROLE_HIERARCHY.get(required_role, 0)
        
        for group_id in server_group_ids:
            user_level = PermissionService.get_user_group_role_level(db, user, group_id)
            if user_level >= required_level:
                return True
        
        return False
    
    @staticmethod
    def get_accessible_servers(db: Session, user: models.User) -> List[int]:
        """获取用户可访问的服务器ID列表"""
        # OWNER/ADMIN 可访问所有
        if user.is_owner or user.is_admin:
            servers = crud.get_all_servers(db)
            return [s.id for s in servers]
        
        # 获取用户的组权限
        user_group_ids = PermissionService.get_user_groups(db, user)
        
        if not user_group_ids:
            return []
        
        # 使用关联表查询服务器（更高效）
        server_ids: Set[int] = set()
        for group_id in user_group_ids:
            ids = crud.get_servers_in_group(db, group_id)
            server_ids.update(ids)
        
        # 如果关联表为空，回退到 JSON 字段
        if not server_ids:
            for group_id in user_group_ids:
                group = db.query(models.ServerLinkGroup).filter(
                    models.ServerLinkGroup.id == group_id
                ).first()
                if group and group.server_ids:
                    try:
                        ids = json.loads(group.server_ids)
                        server_ids.update(ids)
                    except json.JSONDecodeError:
                        pass
        
        return list(server_ids)
    
    @staticmethod
    def get_accessible_groups(db: Session, user: models.User) -> List[int]:
        """获取用户可访问的组ID列表"""
        # OWNER 可访问所有组
        if user.is_owner:
            groups = crud.list_server_link_groups(db)
            return [g.id for g in groups]
        
        # ADMIN 也可以访问所有组（用于管理目的）
        if user.is_admin:
            groups = crud.list_server_link_groups(db)
            return [g.id for g in groups]
        
        # 普通用户只能访问自己所属的组
        return PermissionService.get_user_groups(db, user)
    
    @staticmethod
    def filter_servers_by_groups(
        db: Session, 
        user: models.User, 
        group_ids: List[int]
    ) -> List[int]:
        """获取用户在指定组内可访问的服务器ID列表
        
        这是"组上下文"功能的核心：用户选择一个组后，只能看到该组的服务器
        """
        if not group_ids:
            return []
        
        # OWNER 可以看到指定组的所有服务器
        if user.is_owner:
            pass
        # ADMIN 也可以看到所有组的服务器
        elif user.is_admin:
            pass
        else:
            # 普通用户只能看到自己有权限的组
            user_group_ids = set(PermissionService.get_user_groups(db, user))
            group_ids = [g for g in group_ids if g in user_group_ids]
        
        if not group_ids:
            return []
        
        server_ids: Set[int] = set()
        for group_id in group_ids:
            ids = crud.get_servers_in_group(db, group_id)
            server_ids.update(ids)
            
            # 回退到 JSON
            if not ids:
                ids = crud.get_servers_in_group_legacy(db, group_id)
                server_ids.update(ids)
        
        return list(server_ids)
    
    @staticmethod
    def can_modify_user(actor: models.User, target: models.User) -> bool:
        """检查 actor 是否可以修改 target 用户（非权限字段）"""
        # OWNER 可以修改任何人
        if actor.is_owner:
            return True
        # ADMIN 可以修改非 OWNER/非 ADMIN
        if actor.is_admin:
            return not (target.is_owner or target.is_admin)
        # 其他人只能修改自己
        return actor.id == target.id
    
    @staticmethod
    def can_change_global_permission(actor: models.User, target: models.User) -> bool:
        """检查 actor 是否可以修改 target 的全局权限（is_owner/is_admin）
        
        只有 OWNER 可以修改全局权限
        """
        # 只有 OWNER 可以修改全局权限
        if not actor.is_owner:
            return False
        # OWNER 不能降级自己
        if actor.id == target.id:
            return False
        return True
    
    @staticmethod
    def can_change_group_permission(
        actor: models.User, 
        target: models.User, 
        db: Session = None,
        group_id: int = None
    ) -> bool:
        """检查 actor 是否可以修改 target 的组权限
        
        - OWNER 可以修改任何人的任何组权限
        - ADMIN 可以修改非 OWNER 用户的组权限
        - 组 ADMIN 只能修改自己组内的权限（TODO: 需要 group_id 参数）
        """
        # OWNER 可以修改任何人的组权限
        if actor.is_owner:
            return True
        # ADMIN 可以修改非 OWNER 用户的组权限
        if actor.is_admin and not target.is_owner:
            return True
        # 组 ADMIN 可以修改自己组内的权限
        if db and group_id:
            actor_level = PermissionService.get_user_group_role_level(db, actor, group_id)
            if actor_level >= schemas.GROUP_ROLE_HIERARCHY.get(schemas.GroupRole.ADMIN, 3):
                # 不能修改 OWNER/ADMIN 的组权限
                if not (target.is_owner or target.is_admin):
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


# ============ FastAPI 依赖工厂 ============

def require_server_access() -> Callable:
    """FastAPI 依赖，检查用户是否有权访问指定服务器"""
    from backend.core.auth import get_current_user
    
    async def dependency(
        server_id: int = Path(...),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
    ) -> models.User:
        if not PermissionService.can_access_server(db, current_user, server_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限访问此服务器"
            )
        return current_user
    
    return dependency


def require_server_manage(action: GroupAction = GroupAction.MANAGE) -> Callable:
    """FastAPI 依赖工厂，检查用户是否有权管理指定服务器"""
    from backend.core.auth import get_current_user
    
    async def dependency(
        server_id: int = Path(...),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
    ) -> models.User:
        if not PermissionService.can_manage_server(db, current_user, server_id, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您没有权限执行此操作（需要 {action.value} 权限）"
            )
        return current_user
    
    return dependency


def require_group_permission(
    action: GroupAction = GroupAction.VIEW
) -> Callable:
    """FastAPI 依赖工厂，检查用户在指定组是否有指定权限"""
    from backend.core.auth import get_current_user
    
    async def dependency(
        group_id: int = Path(...),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
    ) -> models.User:
        if not PermissionService.check_group_permission(db, current_user, group_id, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您在该组没有 {action.value} 权限"
            )
        return current_user
    
    return dependency


def require_group_role(
    required_role: schemas.GroupRole = schemas.GroupRole.USER
) -> Callable:
    """FastAPI 依赖工厂，检查用户在指定组是否有指定角色权限（兼容旧接口）"""
    from backend.core.auth import get_current_user
    
    async def dependency(
        group_id: int = Path(...),
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user)
    ) -> models.User:
        if not PermissionService.check_group_role(db, current_user, group_id, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"您在该组没有 {required_role.value} 或更高权限"
            )
        return current_user
    
    return dependency


# 单例实例
permission_service = PermissionService()
