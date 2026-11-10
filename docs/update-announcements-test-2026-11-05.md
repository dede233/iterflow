# 更新公告 TEST 部署记录（2026-11-05）

## 范围与当前状态
用户明确授权部署 TEST；正式环境保持不变，多目标发布仍仅方案。TEST 已恢复，公告功能在线验收和最终服务保护检查 PASS；等待用户验收。

冻结源码：8f4e7db498736778e790e10ff8f95ef92f03c55a。TEST 原版本676e9dd/mysql57_0013，目标mysql57_0014。正式5401215/mysql57_0012。

## 本地准备
- 开发测试见 update-announcements-2026-11-05.md：前端496、后端676、双MySQL与浏览器等通过。
- AMD64 API/Web 镜像构建通过，逐文件匹配Git冻结源码及本地Web产物，公开正式首页哈希未变。
- 追加迁移保护证明在本任务新建 MySQL 中实际运行1项通过：29张旧表全行/列/索引/外键、91个旧触发器及附件不变，只增加两张空表和6个触发器。
- 首次保护测试因新建MySQL尚未就绪连接断开，显式等到SELECT 1通过后重跑通过；未影响服务器。
- 离线归档SHA256：8764713d6f904dba553acde813c4f3878fd127d626c028c03644b0879d0052be，117329920字节。
- 包内不含任何运行时配置或凭据，采用宝塔文件管理正常上传，网页终端只执行短控制命令。
- 本轮未运行远端CI，不推送/合并。

## 升级及回退边界
先preflight，再TEST停写备份，隔离内部网络恢复备份并迁移，证明通过后真实TEST只执行一次迁移；应用健康及正式保护通过后开放。
DDL前失败仅在证明数据不变后恢复原应用。DDL开始后不自动回库或降级，停止TEST并前向修复。已存在公告/阅读历史时迁移自身拒绝有损降级。
正式容器、配置、数据库均不更新；演练SMTP禁用，现有TEST逐服务邮箱配置保持。

## 在线结果
- 正常文件上传成功，服务器原归档 SHA256 与本地一致。
- Docker Desktop 使用 OCI index 标识，服务器经典 Docker 使用 config digest；上传前已验证离线包全部23层及配置/标签/amd64平台一致。另上传校验元数据归档，SHA256 749202a4d4fb8496a82d20662247ed7ae8113e7eb71ad5086222e5fb6e783be4。原manifest另存，实际镜像内容不变。
- preflight PASS。首次尝试启动 backup 时浏览器被切换，复核无 backup 回执、无运行中的部署任务；TEST仍可用，尚未迁移。


## TEST 管理员恢复增量
在线普通测试账号读取用户列表确认现有管理员 acceptance-admin（id=1、role=8、ACTIVE）；普通账号读取角色接口返回403，未绕过该权限。用户明确表示忘记密码并要求重置TEST管理员。
准备单账号交互恢复工具，显式限制数据库iterflow_acceptance、用户id/username及启用内置SUPER_ADMIN资格，更新密码哈希和revision、撤销旧会话并写PASSWORD_RECOVERY审计，不改变角色/邮箱/业务数据。隔离MySQL实际验证1项PASS。
浏览器规则要求由用户亲自输入新凭据，工具只在TTY提示输入并二次确认，不在日志/命令行输出密码。脚本SHA256 b4fe51e30cbc1e72857df8bbb1e4c8b813609f9ac552f04bd1662e8d175832d5。用户亲自输入并确认后，终端返回 PASS（revision=3，撤销11个旧会话）；随后已观察到 TEST 系统管理员首页登录成功。未接触或记录新密码。

## 续跑检查
用户完成管理员恢复后，backup 与 rehearse 均返回 PASS（冻结8f4e7db），原数据与附件保留检查通过；演练数据库已停止，随后真实TEST已完成迁移至mysql57_0014，迁移后备份成功，但API就绪检查失败进入保护停写。


## 就绪失败与前向修复
- 首次deploy在2026-11-05 19:23启动新API后，持续/ready=503，于19:26保护停止TEST应用。没有重复迁移、降级或恢复数据库。
- 定位结果：Redis、附件存储正常；运行账号accept_runtime@%无法看到sys_announcement/sys_announcement_read，触发严格表集合检查。迁移账号检查通过不能替代运行账号检查。
- 修正交付模板deploy/mysql57/runtime-grants.sql，仅补两张公告表的SELECT/INSERT/UPDATE/DELETE，不增加DDL/TRIGGER/GRANT或整库权限。
- 新增真实MySQL回归用例：旧授权重现失败→新授权通过→确认权限精确且无整库授权，1项PASS（4.87秒）。首轮测试提取SQL时误匹配注释中的GRANT已修正并保留失败日志。
- 用户暂停时尚未执行授权，TEST保持保护停写；用户随后明确授权继续补权限、恢复并验收。
- 恢复工具第一版在写授权前因独立客户端没有数据库socket停止；业务/附件快照及正式保护核对通过，未写授权。修正版改用TEST数据库容器内既有/run/secrets/root-client.cnf，未复制或修改凭据。
- 修正版恢复脚本SHA256：6f572539c1c51b083c85fc7b2aebe4bd707d8fb2536ecd5dd3cbbdb7cda4ee20。正常文件上传后校验一致；所有既有冻结文件与失败证据保留。

- 第二次恢复已完成精确表级授权、运行账号readiness及API/Web/worker健康检查。随后systemctl start后立即reload引发两个autorecovery进程竞争review-nginx.pending.conf，日志确认FileNotFoundError；保护再次停止TEST应用。修正为串行启动并等待HTTPS就绪，不紧接重载，既有代理脚本及配置未改。

## 最终恢复及验收结论

- 补齐运行账号两张公告表的精确 DML 权限，前后权限差异仅为这两张表共8项权限，无整库、DDL或转授权权限。`runtime-grants-before.json`、`runtime-grants-after.json`、`runtime-ready.json`留存服务端。
- 代理冲突后重新核对完整快照与`migration-after.json`相等、正式保护基线通过，再启动API/Web/worker，观察`APPS_READY`及健康门禁通过后恢复原代理模板，只执行一次代理启动，不紧接reload。`resume-verify.log`及业务验收后的`final-verify.log`均返回PASS；`recovery-completed.json`记录实际完成，不覆盖原失败记录。
- 当前TEST API/worker/Web源码8f4e7db、数据库mysql57_0014。既有业务数据、附件与SMTP配置保留；恢复阶段未重跑迁移、恢复或降级数据库。正式5401215/mysql57_0012容器与配置、公开首页哈希保持原基线，未连接正式数据库。
- 本轮只在TEST由既有管理员通过正常页面创建、发布并修正合成公告id=1（TEST-20261105），上传一张合成测试图片；保留供用户查看。普通合成账号ceshi002进行正常登录、知晓及阅读。为验证提示排队，该账号也点击了已有邮件引导的“我已知晓”。未修改真实业务需求或版本。

| 在线场景 | 实际结果 |
| --- | --- |
| 管理员创建草稿、上传图片及发布 | PASS；草稿仅管理员可见，发布后普通账号可见 |
| 普通账号草稿详情与管理/创建/编辑/发布越权 | PASS；草稿404，管理及写接口403 |
| 普通账号未读计数与重要提醒 | PASS；发布后未读1，邮件引导处理后显示重要公告弹窗 |
| 我已知晓与刷新不再提醒 | PASS；未读清零，刷新无重要公告弹窗 |
| 独立登录会话已读同步及重复确认 | PASS；read_at相同，重复确认不改变首次阅读时间 |
| 已发布公告修正 | PASS；revision加1，published_at/read_at不变，不重新标未读 |
| 图片与响应式 | PASS；普通账号图片成功加载，点击大图480px；375px页面宽度与内容宽度均375，无横向溢出 |
| 最终服务/正式保护 | PASS；API/Web/worker健康，MySQL preflight、TEST新首页及正式原首页哈希通过 |

本地回归新增MySQL权限用例1项PASS；本轮未再次运行完整八项远端CI，未推送、合并、tag/Release。原完整开发测试见`docs/update-announcements-2026-11-05.md`。部署授权仅TEST，不表示正式上线已获授权。

## 证据位置及后续约束

服务器证据目录：`/opt/iterflow/upgrade-evidence/announcements-test-20261105`。本地验收JSON和截图目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-05/announcements`，包括`online-draft-qa.json`、`online-published-qa.json`、`online-read-qa.json`、`online-after-edit-qa.json`、`TEST-important-notice.png`、`TEST-announcement-desktop.png`、`TEST-announcement-mobile.png`。

后续升级必须在开放流量前用实际runtime账号验证新表权限及readiness；代理未运行时启动并等待就绪，运行时才单独reload，禁止启动与reload重叠。本次未修改既有autorecovery脚本或systemd单元。已有公告和阅读历史，不得把恢复旧应用等同于允许删表降级；遇到问题保持数据并前向修复，数据库恢复需另行明确授权。
