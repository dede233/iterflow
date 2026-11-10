# 本地运行与目录约定

`local-start.py` 用于 macOS / ServBay 下运行当前工作目录的 IterFlow。
从仓库根目录执行：

```bash
backend/.venv/bin/python tools/local-start.py api
backend/.venv/bin/python tools/local-start.py web
backend/.venv/bin/python tools/local-start.py status
```

API 监听 `127.0.0.1:8000`，Vite 监听 `127.0.0.1:5173`。脚本读取根目录
`.env`，沿用本机已建立的 `iterflow_v150_local` PostgreSQL schema、
Redis DB 14 及该 schema 对应的 JWT 配置；它不创建或迁移数据库。
Web 使用 ServBay 的 `/Applications/ServBay/package/node/current/bin/node`。

先在 ServBay 启动 PostgreSQL 17 和 Redis 7。本机数据库连接必须为回环地址；
API 启动时核对专用 schema、当前代码的 Alembic head 和 Redis 连通性。
数据库版本落后时先备份并完成隔离恢复升级演练，再显式升级该本机 schema；
启动脚本不会自动迁移，也不要通过删除版本检查绕过不兼容。
本地启动固定关闭 SMTP，避免合成验收发送真实邮件。

`.env` 中的初始化管理员密码只适用于首次建号，修改密码后不会自动重置账号。
密码遗忘应单独执行已授权的本机恢复，并撤销旧会话、记录审计，凭据保存在
仓库外且权限为 `0600`。2026-11-10 的恢复及验证见
`docs/local-login-repair-2026-11-10.md`。

仓库根目录由脚本自身路径解析，上传文件统一保存到 `data/uploads/`。
`.env`、上传文件和 Python 缓存由根目录 `.gitignore` 排除，不提交到仓库。
迁移已有上传文件时必须先备份、检查同名文件冲突、逐个校验内容，再更新启动项。

本机推荐布局：

```text
~/Developer/
├── work/iterflow/                  # 主项目
│   ├── tools/local-start.py
│   └── data/uploads/
├── worktrees/iterflow/             # 人工创建的临时 worktree
└── backups/iterflow/               # 项目备份与验收证据
```

临时目录使用 `git worktree add` / `move` / `remove` 管理；清理目录时保留
仍有价值的分支和验收提交，另行备份被 Git 忽略的本地文件。Codex 管理的
`~/.codex/worktrees/` 保持由应用管理，Cloudflare Preview 使用自己的容器卷。
备份可能包含敏感数据，目录应仅允许本机用户访问。

本机 LaunchAgent 的 `ProgramArguments` 应使用当前仓库虚拟环境的 Python、
`tools/local-start.py` 的绝对路径和 `api` / `web` 参数。修改 plist 后需要
重新加载服务，再验证 `/health`、`/ready`、Web 和附件上传下载。
