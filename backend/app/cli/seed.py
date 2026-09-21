from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.entities import Permission, Role, RolePermission, User, UserRole
from app.models.enums import DataScope

PERMISSIONS = {
    "dashboard.view": "首页查看",
    "rd.feedback.view": "反馈查看",
    "rd.feedback.create": "提交反馈",
    "rd.feedback.edit": "编辑反馈",
    "rd.feedback.convert": "反馈转需求",
    "rd.requirement.view": "需求查看",
    "rd.requirement.create": "新建需求",
    "rd.requirement.edit": "编辑需求",
    "rd.requirement.status": "需求状态",
    "rd.requirement.version.move": "调整版本",
    "rd.version.view": "版本查看",
    "rd.version.create": "新建版本",
    "rd.version.edit": "编辑版本",
    "rd.version.status": "版本状态",
    "rd.version.publish": "发布版本",
    "rd.release.view": "发布记录查看",
    "sys.user.view": "用户查看",
    "sys.user.create": "创建用户",
    "sys.user.status": "启停用户",
    "sys.role.view": "角色查看",
    "sys.role.edit": "角色权限编辑",
    "sys.system.view": "系统模块查看",
    "sys.audit.view": "审计日志查看",
    "sys.file.upload": "文件上传",
    "sys.file.download": "文件下载",
    "sys.file.delete": "文件删除",
}


@dataclass(frozen=True, slots=True)
class BaseRoleDefinition:
    name: str
    data_scope: DataScope
    permissions: frozenset[str]


BASE_ROLES = {
    "MEMBER": BaseRoleDefinition(
        name="普通成员",
        data_scope=DataScope.SELF,
        permissions=frozenset(
            {
                "dashboard.view",
                "rd.feedback.view",
                "rd.feedback.create",
                "rd.requirement.view",
                "rd.version.view",
                "rd.release.view",
            }
        ),
    ),
    "CUSTOMER_SERVICE_OPERATIONS": BaseRoleDefinition(
        name="客服/运营",
        data_scope=DataScope.SELF,
        permissions=frozenset(
            {
                "dashboard.view",
                "rd.feedback.view",
                "rd.feedback.create",
                "rd.feedback.edit",
                "rd.requirement.view",
                "rd.version.view",
                "rd.release.view",
            }
        ),
    ),
    "PRODUCT_MANAGER": BaseRoleDefinition(
        name="产品/项目负责人",
        data_scope=DataScope.SELF,
        permissions=frozenset(
            {
                "dashboard.view",
                "rd.feedback.view",
                "rd.feedback.create",
                "rd.feedback.edit",
                "rd.feedback.convert",
                "rd.requirement.view",
                "rd.requirement.create",
                "rd.requirement.edit",
                "rd.requirement.version.move",
                "rd.version.view",
                "rd.version.create",
                "rd.version.edit",
                "rd.release.view",
            }
        ),
    ),
    "DEVELOPMENT_LEAD": BaseRoleDefinition(
        name="研发负责人",
        data_scope=DataScope.SELF,
        permissions=frozenset(
            {
                "dashboard.view",
                "rd.feedback.view",
                "rd.requirement.view",
                "rd.requirement.edit",
                "rd.requirement.status",
                "rd.requirement.version.move",
                "rd.version.view",
                "rd.version.edit",
                "rd.version.status",
                "rd.release.view",
            }
        ),
    ),
    "TESTER": BaseRoleDefinition(
        name="测试",
        data_scope=DataScope.SELF,
        permissions=frozenset(
            {
                "dashboard.view",
                "rd.feedback.view",
                "rd.requirement.view",
                "rd.requirement.status",
                "rd.version.view",
                "rd.version.status",
                "rd.release.view",
            }
        ),
    ),
    "SUPER_ADMIN": BaseRoleDefinition(
        name="超级管理员",
        data_scope=DataScope.ALL,
        permissions=frozenset(PERMISSIONS),
    ),
}


def seed_database(db: Session, *, username: str, password: str) -> None:
    """Create or repair the V1.5 foundation roles, permissions, and administrator."""
    permissions = {
        item.code: item
        for item in db.scalars(select(Permission).where(Permission.code.in_(PERMISSIONS))).all()
    }
    for code, name in PERMISSIONS.items():
        permission = permissions.get(code)
        if permission is None:
            permission = Permission(code=code, name=name)
            db.add(permission)
            permissions[code] = permission
        else:
            permission.name = name
    db.flush()

    roles = {
        item.code: item for item in db.scalars(select(Role).where(Role.code.in_(BASE_ROLES))).all()
    }
    for code, definition in BASE_ROLES.items():
        role = roles.get(code)
        if role is None:
            role = Role(
                code=code,
                name=definition.name,
                data_scope=definition.data_scope,
            )
            db.add(role)
            roles[code] = role
        else:
            role.name = definition.name
            role.data_scope = definition.data_scope
            role.enabled = True
    db.flush()

    existing_role_permissions = {
        (item.role_id, item.permission_id) for item in db.scalars(select(RolePermission)).all()
    }
    for code, definition in BASE_ROLES.items():
        role = roles[code]
        for permission_code in definition.permissions:
            permission = permissions[permission_code]
            pair = (role.id, permission.id)
            if pair not in existing_role_permissions:
                db.add(RolePermission(role_id=role.id, permission_id=permission.id))
                existing_role_permissions.add(pair)

    admin_role = roles["SUPER_ADMIN"]
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        user = User(
            username=username,
            display_name="系统管理员",
            password_hash=hash_password(password),
            must_change_password=True,
        )
        db.add(user)
        db.flush()

    if db.get(UserRole, (user.id, admin_role.id)) is None:
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()


def main() -> None:
    settings = get_settings()
    username = settings.init_admin_username
    password = settings.init_admin_password
    if not username or password is None or not password.get_secret_value():
        raise RuntimeError(
            "INIT_ADMIN_USERNAME and INIT_ADMIN_PASSWORD must be explicitly configured"
        )
    plain_password = password.get_secret_value()
    db = SessionLocal()
    try:
        seed_database(db, username=username, password=plain_password)
        print(f"seed complete, admin={username}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
