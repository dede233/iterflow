import os
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.entities import User, Role, Permission, UserRole, RolePermission

PERMISSIONS={
"dashboard.view":"首页查看","rd.feedback.view":"反馈查看","rd.feedback.create":"提交反馈","rd.feedback.edit":"编辑反馈","rd.feedback.convert":"反馈转需求","rd.requirement.view":"需求查看","rd.requirement.create":"新建需求","rd.requirement.edit":"编辑需求","rd.requirement.status":"需求状态","rd.requirement.version.move":"调整版本","rd.version.view":"版本查看","rd.version.create":"新建版本","rd.version.edit":"编辑版本","rd.version.status":"版本状态","rd.version.publish":"发布版本","rd.release.view":"发布记录查看","sys.user.view":"用户查看","sys.user.create":"创建用户","sys.user.status":"启停用户","sys.role.view":"角色查看","sys.role.edit":"角色权限编辑","sys.system.view":"系统模块查看","sys.audit.view":"审计日志查看"
}

def main():
    db=SessionLocal()
    try:
        for code,name in PERMISSIONS.items():
            if not db.scalar(select(Permission).where(Permission.code==code)): db.add(Permission(code=code,name=name))
        db.flush()
        admin_role=db.scalar(select(Role).where(Role.code=="SUPER_ADMIN"))
        if not admin_role:
            admin_role=Role(code="SUPER_ADMIN",name="超级管理员",data_scope="ALL");db.add(admin_role);db.flush()
        all_p=db.scalars(select(Permission)).all()
        existing={x.permission_id for x in db.scalars(select(RolePermission).where(RolePermission.role_id==admin_role.id)).all()}
        for p in all_p:
            if p.id not in existing: db.add(RolePermission(role_id=admin_role.id,permission_id=p.id))
        username=os.getenv("INIT_ADMIN_USERNAME","admin")
        password=os.getenv("INIT_ADMIN_PASSWORD","ChangeMe123!")
        user=db.scalar(select(User).where(User.username==username))
        if not user:
            user=User(username=username,display_name="系统管理员",password_hash=hash_password(password),must_change_password=True);db.add(user);db.flush();db.add(UserRole(user_id=user.id,role_id=admin_role.id))
        db.commit(); print(f"seed complete, admin={username}")
    finally: db.close()

if __name__=="__main__": main()
