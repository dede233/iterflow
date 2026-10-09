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
