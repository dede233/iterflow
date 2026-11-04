# 版本集中提交验收（2026-11-04）

## 已确认范围

用户希望在版本中集中推进需求并减少中间点击，进一步明确选择保留独立验收：已确认、实际已完成开发的需求可直接提交验收，之后仍由有效验收人确认通过。基线`57402f4`；仅本地开发测试，不部署、推送、合并或修改真实数据库。

- 版本需求清单提供集中“提交验收”，接受待开发/开发中；普通需求列表保留原相邻阶段操作。
- 待开发直接提验须说明实际开发已完成及未登记开始的原因；只记录实际待开发→待验收，不伪造开始开发历史。
- 后端强制当前内容确认、有效开发人员及验收人员、操作者资格与权限/范围、设计DONE或NOT_REQUIRED。需要设计时不能静默跳过；现有管理员代操作必须有原因。
- 缺人时有原人员编辑权限者可打开人员弹窗，保存成功后重新检查全部选择及最新revision，不自动提交；其他角色和已有人员保留，无权限者显示详情指引。
- 版本/需求revision及当前有效关联校验，已发布/取消版本拒绝。每条需求原子写入状态、步骤、通知与审计；部分失败不撤销已成功项，结果不确定时先核对，不自动重放。
- 版本继续自动汇总，验收确认与实际发布保留。无迁移、新权限或正式契约改动。

## 实施与验证计划

1. 开发契约先增加`POST /versions/{version_id}/requirements/submit-acceptance`和`VersionRequirementSubmitAcceptance`，实现专用服务与门禁。
2. 在原三步批量弹窗接入版本上下文、快捷说明和缺人补齐；保持普通列表兼容。
3. 在本任务新建PostgreSQL、MySQL5.7 standard/portable与Redis隔离实例验证主链、权限、并发、回滚和通知；前端组件及合成浏览器验证桌面/375px与错误恢复。
4. 复查、记录真实结果并本地提交，后续部署另行处理。

证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-04/version-submit-acceptance/`。隔离资源前缀`iterflow-vsubmit-20261104`，测试连接配置保存在本任务证据目录600权限文件中，不读取仓库`.env`或既有Preview数据库；最终定点清理本任务资源。

交互沿用Vue/Element Plus及既有设计变量，使用ui-ux-pro-max的逐步反馈、错误恢复、字段说明与可访问性规则，不采用其与本工程不符的技术栈或整页风格建议。

## 执行结果

### 实现

- `VersionRequirementWorkflowService`按版本、需求顺序加锁，每项从新事务读取账号权限/范围、版本清单、有效人员与当前内容；一项成功提交后继续下一项。原普通状态/批量接口不接受待开发跳到待验收。
- `WorkflowService.submit_acceptance_locked`复用现有提验校验，仅写真实`STATUS_TESTING`、原阶段/目标阶段、实际操作者、说明、版本及快捷标记；状态与revision、步骤、审计、通知事件同项提交。
- `BatchActionsDialog`仅在版本上下文启用专用动作，检查最新版本及每条需求revision；缺人可按原权限补齐，成功后全量重新检查，不自动提交。版本切换、账号/权限变化使旧预检失效；提交中固定快照，结果不确定时不自动重放。
- 开发契约、生成类型、内置中文接口文档、状态机和用户/API手册同步；无迁移或新权限。

### 已完成验证

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 前端全量单测 | 491 PASS / 63文件 | `frontend-full.log` |
| 组件定向 | BatchActionsDialog及RequirementPeopleDialog 36 PASS | Agent执行记录；包含说明错误恢复、补人重检、上下文失效 |
| 生成类型/构建/Bundle | PASS，最终中文注释同步后类型一致性再次PASS | `frontend-types-final.log`、`frontend-build.log`、`frontend-bundle.log` |
| 新增合成浏览器 | 19 PASS，桌面与375px；选填说明修改后相关1项再验PASS | `browser-final.log`、`browser-optional-reason.log` |
| 原批量与版本进度浏览器回归 | 43 PASS | `browser-regression.log` |
| PG专项与参数校验 | 34实际数据库场景+10参数场景全部PASS | `backend-vsubmit-pg-final.log` |
| PG全量（DeprecationWarning作为错误） | 659 PASS，1项S3集成因未配置本轮对象存储端点跳过 | `backend-full-postgres-final.log` |
| MySQL5.7 standard/portable新增专项 | 各34 PASS | `backend-vsubmit-mysql-standard-first.log`、`backend-vsubmit-mysql-portable-first.log` |
| MySQL5.7 standard/portable相关回归 | 各26 PASS（各1迁移用例按范围排除），每配置合计60 PASS；覆盖协作、旧批量、版本派生进度、完整生命周期、并发发布与发布回滚 | `backend-vsubmit-mysql-standard-regression.log`、`backend-vsubmit-mysql-portable-regression.log` |
| 文档/契约/架构 | 22 PASS | `backend-vsubmit-doc-contract-final.log` |
| 后端静态检查 | app/tests/tests_mysql57 Ruff与格式、全app mypy及编译PASS | `backend-ruff.log`、`backend-format.log`、`backend-mypy.log`、`backend-compile.log` |
| Docker最终镜像与实际页面主链 | 构建、独立库迁移/seed、API健康/ready及Web均PASS；集中提验、独立验收、版本READY、Release=0 | `docker-health.json`、`docker-chain-result.json`、`docker-capture-result.json` |

数据库场景覆盖双revision冲突、权限/范围、当前有效关联、已取消/发布版本、内容失效、缺人/停用人员、设计未完成、非法源阶段、管理员说明、单项注入失败回滚、重复并发提交、等待锁期间移除验收人，以及批量中途撤销权限。成功项只有一次实际步骤、审计及通知事件，失败项不留业务写入。

### 发现、修正与复查

1. 首轮组件测试30/31通过，失败是测试变更权限后未等待Vue watcher关闭弹窗；修正夹具后定向与全量通过。
2. 浏览器视觉复查发现填写有效说明后仍显示旧“请填写”提示。拆分本地字段校验与请求错误，有效输入立即清除本地提示；同时使开发中需求的选填说明符合契约最少2字符。补组件与浏览器断言通过，服务端/未知结果提示保留。
3. PG首轮夹具试图制造被既有关系触发器禁止的孤立指针；改为真实有效迁移/移出。第二轮锁竞争夹具错把模型表名当作`requirements`，等待事件超时后线程池仍等待未释放的人员锁；定点中断该pytest，改用模型实际表名，并保证finally先释放锁再join。首次日志保留，修正后并发场景及全量通过。
4. 契约同步初检暴露200/404文案与生成器默认值差异。全量PG首轮另暴露中文打包文档与新schema标题未同步（656 PASS、3 FAIL、1 SKIP）；同步开发契约、字段中文标题、内置文档与生成类型后，22项文档检查与全量PG通过。
5. 自查及另一实现Agent交叉复查权限、锁顺序、CAS、事务、版本派生进度和前后端契约，未发现未解决阻塞项；这不是外部独立终审。桌面及375px截图复核通过。
6. Docker准备脚本首轮因并行构建写同一外部资源清单覆盖一个镜像条目，保护校验停止，尚未创建数据库、容器或网络。核验实际镜像ID并修复清单后，顺序准备与实际主链通过；`docker-prepare-first-failure.json`保留。首次READY截图早于加载结束，随后只读补截，未重放业务写入。
7. 最终本地资源清理首次调用系统Python3.9，导入`datetime.UTC`即失败，未执行资源操作；改用项目Python3.12后按精确容器ID、任务标签和卷名完成清理。

### 实际镜像与收口

- API镜像`sha256:91b6efc8f083dd4f6142010cc8a82dcd404a1a72e20f316b3d601875eba9cee2`，Web镜像`sha256:fccb132335d94eae7b2d92f06b55e6f4e3537c033705d190c45801a6ebbbbcde`。159个后端和128个前端产品文件与当前工作树哈希一致；生成类型注释最终同步后Web重新构建。
- 真实浏览器通过Web登录、修改合成初始密码，并创建独立验收账号。在版本清单把CONFIRMED需求集中提交到TESTING，只有实际STATUS_TESTING记录，没有伪造STATUS_DEVELOPING。提交者无理由代验收返回403，指定验收人确认后需求DONE、版本自动READY，实际Release数量仍为0。SMTP关闭，未发送真实邮件。
- 最终截图为`docker-chain-submitted-1440.png`、`docker-chain-ready-final-1440.png`及`docker-chain-ready-final-375.png`；截图修正记录与原始文件保留。
- 已停止本次Vite进程，按任务清单定点删除Docker验收API/Web/网络/uploads/独立数据库，以及原新建PG、Redis、MySQL双配置容器及对应4卷；临时数据库凭据删除。清理见`docker-cleanup.json`、`local-cleanup.json`。未使用全局prune，未操作既有Preview或线上资源。
- 所有计划验证与复查完成，无未解决阻塞或规格冲突。此次仅本地实现与提交；不推送、合并、部署或修改真实数据库。TEST仍为Web`8d12acf`、API/worker`c0f68e1`/`mysql57_0012`，正式仍为`96ba96e`/`mysql57_0011`（沿用此前已核实基线，本轮不访问线上）。
