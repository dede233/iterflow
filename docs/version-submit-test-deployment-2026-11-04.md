# 版本集中提交验收 TEST 部署（2026-11-04）

## 范围与基线

用户授权部署本次版本集中提交验收到保留TEST，供验证直接提验、人员补齐和验收流程，禁止修改正式环境。产品冻结`b9b2cc1088a2d8bc335c72153212ef31cb0dd5a1`；本地前端491项、PG659项（S3未配置1项跳过）、MySQL双配置各60项、文档契约22项、浏览器及Docker实际主链通过，详见[实现与验证](version-submit-acceptance-2026-11-04.md)。

切换前已只读核对Safari宝塔主机名及运行容器：TEST Web为`batch-guidance-8d12acf`，API/worker为`version-flow-test-c0f68e1`；正式API/worker/Web为`mail-notice-96ba96e`，运行服务健康。预检实际确认TEST为`mysql57_0012`；正式`mysql57_0011`沿用已核实基线，本轮不连接正式数据库。

- TEST：`https://sx-kc.xyz:8444`，项目`iterflow-acceptance-20261012-753ebd`。
- 本次仅更新TEST API/worker/Web；无数据库迁移、初始化或恢复，无业务版本发布，不推送/合并或创建tag/Release。
- 现有账号、会话、数据、附件、JWT、Redis、逐服务SMTP及恢复配置保留。API SMTP465与worker1465为既有分工，分别核对前后指纹，不统一端口。
- 仅通过正常文件上传传输包与脚本，网页终端只执行短控制命令。正式保护基线、未知残留任务、产物或配置出现漂移时停止。

## 执行计划

1. 固定已测试linux/amd64产品文件，补充镜像来源标签但不改变RootFS；离线核对归档和镜像身份。
2. 上传至独立受保护证据目录，校验SHA256；只读预检两环境、残留任务、TEST schema、配置及可用空间。
3. 不停服准备新镜像与旧应用/配置备份；短暂TEST维护隔离写入，停止写服务后备份TEST数据和附件并形成保护快照。
4. 使用原TEST项目和配置，`--no-deps`配套更新API/worker/Web，不拉起migrate/seed；确认数据保留、健康、逐服务邮件配置后恢复TEST代理。
5. 合成账号通过正常API和桌面/375px页面验证直接提验、补人重检、内容/设计/权限/revision门禁、独立验收及自动READY；未实际发布，保留验收数据。
6. 最终核验正式保护与TEST健康，记录实际结果和回退方式，再本地文档收口。

## 执行结果

TEST切换、在线功能验收与最终保护复核全部PASS，保留供用户验收。证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-04/version-submit-test/`。

- 正常上传归档`iterflow-version-submit-test-b9b2cc1.tar`，116,930,560字节；服务器SHA256与本地一致：`093e914ebcf2ed36c02d8e421fc879b130db0f482df87fdc19bf924f64fcec25`。归档仅5个普通文件；上传目录随后收紧为root:root/700，归档600。
- 服务器证据目录：`/opt/iterflow/upgrade-evidence/version-submit-b9b2cc1`。预检于23:01:06（北京时间）PASS；prepare旧应用与配置备份、新镜像文件/依赖/身份核对PASS。控制器离线24项通过。
- 维护尝试开始23:05:30，部署最终保护回执23:06:29 PASS，维护尝试至部署PASS记录窗口约59秒（不是实测不可用时长）。只更新TEST API/worker/Web为`version-submit-b9b2cc1`，源码均为上述冻结SHA。
- 新应用启动后、worker恢复前，30张表的完整行内容（含刷新会话）、schema/索引/FK/触发器/例程及附件与停写快照一致；账号、会话、附件与逐服务SMTP保留。无migration、seed、恢复或回退。
- 数据与附件备份：`/opt/iterflow/backups/version-submit-pre-20261104T150540Z`；旧应用镜像在服务器证据目录`old-app-images.tar`，原配置在`configuration-before/`，均受保护留存，不下载敏感内容。
- 正式容器身份、配置及首页摘要在预检及部署后未变；正式服务健康。TEST DB/Redis未重建。
- 操作记录：prepare命令首次粘贴遇到本机剪贴板冲突，已在回车前发现并清除错误输入，核对正确命令后执行；未运行错误命令。未通过网页终端传输文件或脚本内容。

服务器5份成功回执已通过宝塔正常下载至本地`server-receipts/`，归档`safe-receipts-final.tar` SHA256核验一致：`82b1369fb05e625b577a3be0919c6afdfa71af78d0980a0de1604368391a422b`。只含阶段结果，不含配置、数据库行或会话内容。服务器经典镜像config ID为API`c231f4f3b5c4496d5b3defba4ab040809c644427717738eb4d45080787d8b3b4`、Web`c623b482c92cd03445223ac2b31cb913e297b82330e81ef98994fba054a7200e`，已按包内OCI manifest/config链及RootFS核验。

## 在线验收结果

现有合成账号`ceshi002 / P7 A`负责确认及开发，`ceshi003 / P7 B`负责验收。只通过正常API和页面新增本轮2个版本、5条需求；保留关键词`TEST 集中提验 20261104-150738`供复验。

| 验收项 | 实际结果 |
| --- | --- |
| 缺开发/验收人员 | 需求28在检查页提示缺人；补齐后保留确认人，revision +1，全部重新检查，不自动提交 |
| 待开发直接提验 | 原因为空时阻止提交；填写说明后需求27/28由CONFIRMED直接进入TESTING，记录实际操作者与快捷来源，不伪造DEVELOPING记录 |
| 内容/设计门禁 | 需求29修改后未重新确认、30设计PENDING；375px页面检查及后端均阻止，状态/revision不变 |
| 并发门禁 | 版本26检查后修改版本，旧version_revision返回逐项409；需求31不变、无静默重放 |
| 独立验收 | 开发账号验收返回403；指定验收账号页面确认27/28后均DONE，实际验收人记录正确 |
| 版本自动汇总 | 版本25随提验进入TESTING，全部验收后自动READY；版本26仍PLANNING |
| 发布及邮件边界 | 两版本均Release=0、released_at=null；两账号无有效通知邮箱、邮件偏好不变，无真实邮件验证 |
| 页面 | 桌面1440px与移动375px关键过程通过，无横向溢出或未预期页面错误；8张截图留存 |

主链[版本25](https://sx-kc.xyz:8444/#/versions/25)中需求27/28最终为DONE（revision5/6）；[阻塞案例版本26](https://sx-kc.xyz:8444/#/versions/26)保留需求29/30/31为CONFIRMED（revision4/4/3），分别可复验内容、设计及直接提验场景。

首轮自动化因未可靠收起开发人员多选下拉、遮挡下一字段而STOPPED，未保存人员或提交验收。保留`online-qa-journal.json`及失败截图；只读核对全部已知写入回执、revision与关联后，仅续跑未执行步骤。普通点击弹窗标题即可关闭下拉，未强制点击、重复创建或修改产品。最终`online-qa-resumed.json`、`online-final-summary.json`均PASS。

23:12:54（北京时间）最终`verify` PASS：正式容器/配置保护不变、TEST健康、源码与首页摘要正确、逐服务SMTP保留，schema/索引/FK/触发器/例程和全部原附件摘要与切换前一致。开放后正常验收与worker允许产生业务行变化；不把开放后行摘要差异误判为数据丢失。

本轮未运行新的远端CI、未推送/合并、未创建tag/Release，未部署正式环境或连接正式数据库。最终待用户验收，无未解决功能阻断或规格冲突。

## 回退边界

本次无schema变化，新数据仍采用既有TESTING/DONE阶段、STATUS_TESTING事件及JSON步骤信息。回退仅恢复本轮切换前Web`8d12acf`及API/worker`c0f68e1`，保留已正常产生的业务与通知记录；不得回退到不兼容0012的`f879eaa`，不得恢复或降级数据库。部署控制器只在本次切换失败时自动回旧应用，先封闭TEST入口并核对保护基线；worker恢复前要求全量数据与切换前一致，恢复过worker后则保留当前有效数据。回退失败或镜像、配置、正式保护基线校验失败时保留维护与现场并停止。最终verify另行核对完整schema、索引、FK、触发器和例程摘要。

验收后的人工回退须重新检查当前数据和保护基线，并核对schema/索引/FK/触发器/例程与本轮`data-before.json`一致；出现漂移须先停止调查。随后再按上述旧镜像和受保护原配置配套恢复应用；控制器没有独立`rollback`入口，不得盲重跑`deploy`或覆盖当前业务数据。旧镜像与配置备份位置见执行结果。
