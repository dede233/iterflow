# IterFlow v0.6.2 架构评审报告

版本：v0.6.2

基线： - master: `7fa7a5c30a8d3f57760427f2d087bd5a26412806` - tag:
`v0.6.2-phase6.2`

## 一、项目定位

IterFlow 是一个独立部署的需求与版本协作管理系统。

核心闭环：

    Feedback
      ↓
    Requirement
      ↓
    Version
      ↓
    Publish
      ↓
    Release

## 二、技术架构

后端：

-   Python 3.12
-   FastAPI
-   SQLAlchemy
-   Alembic
-   PostgreSQL
-   Redis

固定 Python：

`/Users/xiaweiyi/Developer/work/iterflow/backend/.venv/bin/python`

版本：

`3.12.13`

前端：

-   Vue 3
-   TypeScript
-   Vite
-   Element Plus
-   Pinia
-   Vue Router
-   Vitest

## 三、核心领域模型

核心实体：

-   Feedback
-   Requirement
-   Version
-   Release

禁止随意改变四核心实体关系。

## 四、业务链路

    Feedback
       |
       | convert
       ↓
    Requirement
       |
       | version planning
       ↓
    Version
       |
       | publish
       ↓
    Release

## 五、核心设计原则

### Feedback

负责外部输入、问题收集、建议记录、需求转换。

### Requirement

正式研发需求。

禁止未经评审增加：

-   工时
-   Story Point
-   开发时间
-   预计完成时间

### Version

发布规划单元。

需求关联必须通过：

`VersionRequirement`

禁止 Requirement 直接绑定 Version。

### Release

发布历史记录。

Release 不是工作流。

禁止：

-   Release 状态机
-   DRAFT
-   READY
-   RELEASING
-   CANCELED
-   Release workflow

## 六、状态机原则

Version：

    PLANNING
    DEVELOPING
    TESTING
    READY
    RELEASED

只有：

`VersionService.publish()`

可以：

    READY → RELEASED

Requirement 的 ONLINE 只能由发布事务产生。

Feedback 发布后：

    REQUIREMENT_LINKED → ONLINE

## 七、发布体系

唯一发布入口：

`VersionService.publish()`

流程：

    BEGIN

    锁定 Version

    PublishCheckService 检查

    Version READY → RELEASED

    Requirement DONE → ONLINE

    Feedback REQUIREMENT_LINKED → ONLINE

    创建 Release SUCCESS

    写 Audit

    COMMIT

失败全部回滚。

## 八、PublishCheck

v0.6.2 引入：

`PublishCheckService`

当前检查：

-   Version 状态检查
-   Requirement 完成检查
-   权限检查

未来可扩展：

-   测试检查
-   风险检查
-   业务确认

## 九、权限与数据范围

角色：

-   SUPER_ADMIN
-   PRODUCT_MANAGER
-   DEVELOPMENT_LEAD
-   TESTER
-   CUSTOMER_SERVICE_OPERATIONS
-   MEMBER

核心权限：

-   `rd.version.publish`
-   `rd.release.view`

数据范围：

-   SELF
-   ALL

预留：

-   TEAM

## 十、审计

支持：

Feedback：

-   CREATE
-   UPDATE
-   STATUS_CHANGE
-   COMMENT_CREATE
-   CONVERT_REQUIREMENT

Requirement：

-   CREATE
-   UPDATE
-   STATUS_CHANGE

Version：

-   CREATE
-   UPDATE
-   STATUS_CHANGE
-   VERSION_PUBLISH

Release：

-   RELEASE_CREATE

禁止记录：

-   token
-   password
-   secret

## 十一、API原则

业务规则由后端控制。

状态错误：

HTTP 409

无权限或不存在：

HTTP 404

参数错误：

HTTP 422

## 十二、测试基线

Backend：

`142 passed`

Frontend：

`37 passed`

质量检查：

-   ruff
-   format
-   mypy
-   compileall
-   alembic check

全部通过。

## 十三、当前技术债

### TD-001 PublishService 拆分

未来考虑：

    PublishService
        |
    PublishTransactionService

### TD-002 状态机统一

未来考虑统一状态机注册中心。

### TD-003 Audit 查询中心

增加审计查询能力。

### TD-004 权限颗粒度

未来考虑：

-   version.publish
-   version.requirement.manage
-   release.view

## 十四、未来 Agent 开发约束

禁止：

1.  修改四核心实体关系。
2.  给 Release 增加状态机。
3.  让 Requirement 直接关联 Version。
4.  绕过 Service 修改状态。
5.  前端决定权限。
6.  删除 revision 乐观锁。
7.  删除 Audit。

## 十五、结论

截至：

`v0.6.2-phase6.2`

IterFlow 已完成：

    反馈
     ↓
    需求
     ↓
    版本
     ↓
    发布
     ↓
    历史

第一版完整业务闭环。

后续开发应优先保持领域模型稳定，再扩展能力。
