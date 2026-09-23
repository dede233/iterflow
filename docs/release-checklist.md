# 迭程 IterFlow 发布检查单

发布负责人逐项记录证据与执行时间；任一必需项失败不得标记发布就绪。

- [ ] Git 工作区 clean；目标 commit/tag、merge 方式及回滚 tag 已核对
- [ ] GitHub Actions 全部绿色：Backend、PostgreSQL 专项（0 skipped）、Frontend、Docker fresh smoke、S3、浏览器、备份恢复
- [ ] Backend pytest 与弃用警告严格门禁、Ruff、Format、Mypy、Compileall 通过
- [ ] OpenAPI runtime/static parity 与生成 TypeScript DTO drift 检查通过
- [ ] `alembic check` 无新升级操作；当前数据库 revision 与目标版本一致
- [ ] `npm audit` 完整依赖和生产依赖 moderate+ 均为 0
- [ ] `pip-audit -r backend/requirements.lock` 已知漏洞为 0
- [ ] Docker Compose config/build 成功，基础镜像 patch 版本与依赖锁可复现
- [ ] 空卷一键启动自动迁移、seed、API/Web 健康；初始管理员登录与 `/auth/me` 成功
- [ ] 真实 S3-compatible smoke：bucket、上传、读取、metadata、signed URL、删除、readiness
- [ ] Local Storage 备份恢复演练：数据库和附件恢复、SHA256 一致
- [ ] `/health`、`/ready`、Web 200；`build_sha` 与部署提交一致
- [ ] 浏览器 smoke：首次改密、Dashboard、反馈创建与列表、无严重控制台错误
- [ ] TLS 前置代理、Host 白名单、CORS、代理 IP 信任与安全响应头检查完成
- [ ] 升级前备份已完成并验证；S3 模式下对象恢复点已确认
- [ ] 回滚版本、数据库备份与附件/对象恢复点明确；维护窗口及值班负责人确认
