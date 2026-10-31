# 受保护的接口文档入口

2026-10-08 用户授权在现有线上 Preview 提供接口文档，仅超级管理员和研发负责人可查看。

## 访问规则

- 桌面：系统设置 → 接口文档；移动端：我的 → 接口文档。
- 页面：`/#/admin/api-docs`；数据接口：`GET /api/v1/docs/openapi`。
- 后端每次请求检查当前有效用户和数据库角色：仅启用的系统角色 `SUPER_ADMIN` 或 `DEVELOPMENT_LEAD` 通过。角色名称、ALL 数据范围或 `*` 权限均不能代替此校验。
- 未登录 / 停用账号返回 401；其他角色、角色停用及首次改密限制返回 403。角色移除或停用后，旧 Access Token 也不能继续读取文档。
- `AuthMe.can_view_api_docs` 是可选资格标记，用于入口与路由控制；前端不会把它作为后端授权替代。
- 文档响应 `Cache-Control: private, no-store`，按 Authorization 区分响应；读取行为记入审计，审计不包含 token 或密码。
- 生产环境始终关闭未经角色校验的 `/docs`、`/redoc`、`/openapi.json`，即使误设 `ENABLE_API_DOCS=true` 也不开放。已有本地开发工具仍由该开关控制。

## 页面与契约

页面以中文为主，显示模块、操作说明、路径 / 方法、参数、请求正文、状态码和响应字段，支持搜索及下载 OpenAPI。所有加载通过同源带身份请求完成，不把 token 放入 URL，不依赖外部 CDN，不在页面自动执行业务写接口。

2026-10-09 修复响应字段中文名称缺失：开发契约的 397 个模型字段增加中文 title；文档生成与读取只覆盖 title / description，不更改字段名、类型、required、枚举、引用或任何业务响应结构。契约同步工具保留这些说明，避免下次生成时丢失。历史发布契约保持不变。页面同时展示英文字段名和中文名称；分页 items、顶层数组、可为空的引用对象支持逐层查看子字段，递归深度有限且保留完整结构查看。

本次修复的本地门禁：后端 warnings-as-errors 338 passed / 38 环境依赖项 skipped，独立 PostgreSQL 门禁交由 CI；前端 320 passed / 47 files，类型 / 生产构建 / bundle 通过；文档浏览器 5 项通过。真实本地 API / 页面 10 项检查通过，375px / 1440px 分页响应子字段显示中文，搜索 / 下载与原账号登录正常。同一 Agent 的 Fresh Self-Review 验证了运行时 OpenAPI 缓存不被修改、下载及显示标签一致、契约生成不丢说明、剔除文档注释后响应 shape 不变、角色检查保持原样和递归终止；并非外部独立终审。此提交时 branch / master / Preview CI 和线上部署待执行，实际结果记录到独立备份证据目录。

`spec/openapi-development.yaml` 是当前未发布开发快照。以下描述是接口文档入口初次增量的历史记录；当前还包含已授权的阶段分工、DESIGNING、本人开发确认及 DONE/发布门禁，见 [当前接口指南](api-guide.md) 和 [操作手册](user-manual.md)。初次入口增量相对已发布的 `spec/openapi-v1.8.1.yaml`，仅增加文档读取路径和 AuthMe 可选资格字段；主链、revision、状态机、数据范围和各业务权限保持原样。后端 parity / 同步脚本与前端类型生成入口统一指向开发快照。测试验证剔除这两项增量后，快照与 V1.8.1 完全相同。没有创建新 Release / Tag，也没有新增角色、permission 或 migration。

中文说明从开发契约生成到 `backend/app/core/api_documentation.json` 并随 API 包 / 镜像安装；线上返回真实运行时 OpenAPI 结构，只覆盖中文说明，避免文档接口结构与实现脱节。更新契约后运行：

```bash
cd backend
../.venv/bin/python -m scripts.sync_openapi
../.venv/bin/python -m scripts.build_api_documentation
cd ../frontend
npm run generate:api-types
```

## 验证与部署

新增后端测试覆盖准确角色、普通账号、通配权限绕过、自定义同名角色、停用角色、停用账号、强制改密、同 token 撤销后的拒绝、响应缓存与审计、中文说明一致性和生产公共文档关闭。前端覆盖菜单 / 路由资格、375px / 1440px 展示、搜索、下载、撤销后拒绝以及资格变更后丢弃在途文档。

本地完整后端测试的 PostgreSQL-only 项仅在独立测试数据库配置下运行；CI 配置独立 PostgreSQL / Redis 和一次性 Compose，必须通过全部六项门禁与真实浏览器主链。现有试用数据库不用于 destructive smoke 或 restore。

更新线上按已授权流程：功能分支六项 CI → master 无漂移检查 / no-ff merge / 新 master 六项 CI → 合入 Preview，产品 tree 与 master 一致且基础设施补丁保留 → Preview 六项 CI → 已校验的独立 pre-backup → 保留账号和数据卷升级 → 公网登录 / 文档正负访问 / 主链页面回归 → api / web / cloudflared restart persistence → 独立 post-backup 校验。保留首次失败证据，正式历史 tag 不变；实际 CI、部署 SHA 和备份路径写入最终验收证据。

### 本地门禁与 Fresh Self-Review

- 后端完整 warnings-as-errors：337 passed / 38 PostgreSQL-only 等环境依赖项 skipped；独立 PG / 实际 Compose 门禁交由六项 CI 执行，不对真实试用卷执行 smoke / restore。
- 后端 Ruff check / format、Mypy、compileall 通过；文档 / Auth / 契约目标测试全部通过。
- 前端 Vitest：318 passed / 46 files；类型生成一致性、TypeScript / 生产构建、bundle 门禁通过（最大 JS chunk 273.7 KiB）。
- 静态构建本地 mocked 浏览器回归：159 passed。两项需要一次性 Compose / CI 凭据的真实主链测试没有连接真实本地或 Preview 数据库，留给 CI 全量执行。
- 同一 Agent 的 Fresh Self-Review 检查了角色查询、可选资格标记、直接 URL、403 / 401、停用 / 移除角色后旧 token、在途请求与缓存、生产公共文档关闭、镜像包中文元数据以及冻结业务契约。该复查不是外部独立终审。
- 首次开发验证的失败已保留在本机 `/tmp/iterflow-docs-*` 日志：修正了 CORS 追加 Vary 后的断言、契约同步元数据；浏览器改用静态构建，等待账号恢复完成并提供完整模拟登录凭据，避免 Vite 新依赖优化重载干扰；完整静态回归通过。
- 分支 / master / Preview CI 与公网验收在提交此记录时待执行，不提前记录 PASS 或部署 SHA。
