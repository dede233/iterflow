from dataclasses import dataclass
from typing import ClassVar

from app.models.entities import Permission
from app.schemas.role import PermissionOut


@dataclass(frozen=True, slots=True)
class PermissionGroupDefinition:
    prefix: str
    label: str
    order: int


class PermissionCatalog:
    """Application-level presentation metadata for code-defined permissions."""

    GROUPS = (
        PermissionGroupDefinition("dashboard", "Dashboard / 首页", 0),
        PermissionGroupDefinition("rd.feedback", "Feedback / 反馈", 10),
        PermissionGroupDefinition("rd.requirement", "Requirement / 需求", 20),
        PermissionGroupDefinition("rd.version", "Version / 版本", 30),
        PermissionGroupDefinition("rd.release", "Release / 发布", 40),
        PermissionGroupDefinition("sys.user", "User / 用户管理", 50),
        PermissionGroupDefinition("sys.role", "Role / 角色权限", 60),
        PermissionGroupDefinition("sys.audit", "Audit / 审计", 70),
        PermissionGroupDefinition("sys.system", "System / 系统", 80),
        PermissionGroupDefinition("sys.file", "File / 文件", 90),
    )
    OTHER = PermissionGroupDefinition("other", "Other / 其他", 1_000)
    SENSITIVE_CODES = frozenset(
        {
            "rd.version.publish",
            "sys.user.status",
            "sys.user.role.assign",
            "sys.role.manage",
            "sys.file.delete",
        }
    )
    DEPRECATED_REPLACEMENTS: ClassVar[dict[str, str]] = {
        "sys.role.edit": "sys.role.manage",
        "rd.requirement.version.move": "rd.version.edit",
    }

    @classmethod
    def group_for(cls, code: str) -> PermissionGroupDefinition:
        return next(
            (
                group
                for group in cls.GROUPS
                if code == group.prefix or code.startswith(f"{group.prefix}.")
            ),
            cls.OTHER,
        )

    @classmethod
    def serialize(cls, permission: Permission) -> PermissionOut:
        group = cls.group_for(permission.code)
        replacement_code = cls.DEPRECATED_REPLACEMENTS.get(permission.code)
        return PermissionOut(
            id=permission.id,
            code=permission.code,
            name=permission.name,
            category=permission.category,
            group=group.label,
            sensitive=permission.code in cls.SENSITIVE_CODES,
            deprecated=replacement_code is not None,
            replacement_code=replacement_code,
        )

    @classmethod
    def serialize_all(cls, permissions: list[Permission]) -> list[PermissionOut]:
        return [
            cls.serialize(permission)
            for permission in sorted(
                permissions,
                key=lambda item: (cls.group_for(item.code).order, item.code),
            )
        ]
