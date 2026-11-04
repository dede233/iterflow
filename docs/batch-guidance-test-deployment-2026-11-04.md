# 批量操作指引 TEST 部署（2026-11-04）

## 范围

用户明确授权部署本次批量操作与指引优化到保留 TEST，正式环境不变。冻结源码 `8d12acff1043d8ff0da3fa46e7c13552408be794`，相对现有 TEST `c0f68e1` 仅有前端批量组件、版本清单范围参数、测试及文档变更。只更新Web，不迁移数据库、不重建API/worker、不修改邮箱配置、不发布业务版本；不推送、合并或创建tag/Release。

本地产品验证：475单测、318合成API浏览器、27项最终批量专项、类型/构建/Bundle/生成类型一致性通过，见 [实现记录](batch-operation-guidance-2026-11-04.md)。本轮按冻结源码构建linux/amd64镜像，校验归档、镜像config及RootFS、源码标签和静态文件。

## 执行计划与保护

- 通过已登录Safari宝塔正常文件上传包；网页终端仅执行短控制命令，不传文件内容、Base64或长脚本。
- 预检服务器身份、残留任务、TEST与正式来源和健康；保存正式容器/配置/首页及TEST非Web容器/配置的保护快照。
- 备份旧TEST Web镜像及配置，仅修改WEB_IMAGE并以`--no-deps`重建Web，按既有规则重载独立TEST代理；失败只回退Web，不操作数据库。
- 只用既有TEST合成账号和本轮新建合成记录完成页面验证，保留数据供用户验收；不编辑已有业务记录、不改账号设置、不发送外部邮件。
- 验收后复核健康、实际产物与保护快照；正式仍为`96ba96e` / `mysql57_0011`，TEST后端与数据库仍为`c0f68e1` / `mysql57_0012`。

## 执行记录

部署及在线验收 **PASS，待用户验收**。证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-04/batch-guidance-test/`。

- Safari宝塔终端可用，服务器提示符hostname与此前一致；只读`docker ps`确认TEST API/worker/Web均为`version-flow-test-c0f68e1`，正式均为`mail-notice-96ba96e`，API/Web健康。
- 首次本地冻结解包因系统Python不支持`tarfile.extractall(filter=...)`参数停止，后续构建找不到上下文，未产生镜像或服务器操作。改为先校验归档全部路径与文件类型再解包，重新构建，首次日志保留为`web-image-build.log`。
- 新Web镜像本地启动、`nginx -t`、151静态文件HTTP读取及SHA256校验通过；临时验证容器已移除。镜像OCI index、平台manifest、config和全部RootFS链核验通过。
- 部署主控复查发现继承环境变量可能覆盖Compose镜像选择。上传前增加环境覆盖拒绝与每阶段实际Compose配置检查，16项离线保护测试及Python3.6语法检查通过。初版复查和修正证据保留，未发生服务器误切换。
- 通过Safari正常文件上传至`/opt/iterflow/upgrade-evidence/batch-guidance-8d12acf`；上传7秒内完成，服务器外包SHA256与本地一致。目录改为root:root/700，包为600，再解包；终端只输入短控制命令。
- `preflight → prepare → deploy → verify`逐步PASS。服务器备份旧Web镜像和5个配置文件，装载并校验新镜像151个静态文件，仅替换`WEB_IMAGE`，以`--no-deps --no-build --pull never`更新Web；健康后重载独立TEST代理。
- 切换记录：2026-11-04 **19:00:24–19:00:39（UTC+8）**，15秒为切换至检查PASS的记录窗口，不等同于实测不可用时长。无切换失败、无回退，无数据库命令。
- 在线验收后再次`verify`，**19:07:44 PASS**。正式容器身份/启动时间/配置/首页哈希不变，TEST API/worker/DB/Redis身份及运行配置不变。数据库版本沿用此前部署记录，本轮没有连接数据库读取或修改schema。

## 产物身份

| 项目 | 值 |
| --- | --- |
| 产品源码 | `8d12acff1043d8ff0da3fa46e7c13552408be794` |
| 新Web镜像 | `iterflow-web:batch-guidance-8d12acf` |
| 服务器实际config ID | `sha256:ffae92e5ff4516f3c440e60a66f009085600c7bc0f0ee88f18e6f1b6e713d282` |
| 新首页SHA256 | `0d71dc320dd52c16fd7bfe588aef0caf63c5adb32a94f478d46ff6a7de51bb68` |
| 外包 | `iterflow-batch-guidance-8d12acf.tar`，23,203,840 bytes |
| 外包SHA256 | `0c0a456c7b65ab33931c324a0203f502436af2bd929fd64ff44358b21269a7c8` |
| 镜像压缩归档SHA256 | `920d6e710ee970babe63a5a82ca7a8faa60b0448d160e0b6fe478ba7ad89fbd0` |
| 主控SHA256 | `3b17dab5d0f83ee876d1d5f4ca400358e5a3b843af1e61c009f606b671417164` |

TEST地址为`https://sx-kc.xyz:8444`。API/worker仍为`c0f68e131b5fd8232c70e4b237b78bfd93d8f72b`，数据库`mysql57_0012`；正式`8443`仍为`96ba96ef81f96a533e9bc912100651d368a6945f` / `mysql57_0011`。前后端源码不同是本次仅前端增量的预期结果。

## 在线验收

仅使用已有合成账号`ceshi002`（用户3，未绑定通知邮箱），通过正常TEST API新建2条需求、2条反馈、1个版本；随后在真实页面执行批量操作。前后核对邮箱状态/邮件偏好相同，未修改账号知晓设置，也未绑定邮箱或发送外部邮件。合成数据保留，搜索关键词：`TEST 批量指引 20261104-110105`。

| 验收项 | 实际结果 |
| --- | --- |
| 需求列表范围 | 筛选2条，默认未选动作/记录，明确当前页范围及0/50；选择后进入检查，不直接提交 |
| 需求确认混合结果 | 需求25符合资格，需求26缺确认人；核对页明确1可执行/1跳过及详情入口，执行结果1成功/1跳过/0失败 |
| revision与确认记录 | 需求25 DRAFT→CONFIRMED，revision2→3，仅1条确认记录；需求26仍DRAFT/revision1、0确认记录 |
| 反馈受理 | 反馈22由指定接收人3受理，NEW→ACCEPTED，revision1→2，accepted_by/handler_id均3 |
| 关闭原因 | 空原因停在核对页并显示至少2字符提示；填入合成验收原因后反馈23 NEW→CLOSED，revision1→2，结果1成功 |
| 版本清单范围 | 版本24只显示关联需求25，文案为“当前版本清单的筛选结果”，选择按钮为“选择当前清单” |
| 无可执行项 | 对需求25检查开始开发，缺开发人员，0可执行/1跳过，显示设置人员指引；没有执行按钮，返回调整保留选择；未实际开始开发 |
| 版本边界 | 版本24仍PLANNING/revision2，仅关联需求25，无发布记录 |
| 响应式 | 桌面核对/结果页及375×812手机选择/检查/结果页通过；手机页面和弹窗宽375，无横向溢出，内容滚动且底部按钮保持可见 |

在线回读证据：`online-qa/fixtures.json`、`after-requirement.json`、`final-api-verification.json`。fixture创建脚本有逐步一次性日志，防止未知结果重放；只读核对脚本仅登录和GET已记录ID。两类脚本7项/9项离线测试通过。截图包括`requirement-review.png`、`requirement-result.png`、`version-scope.png`、`feedback-result.png`及4张手机截图。

页面自动化过程中有一次误用全角标题的等待超时，读取实际页面后恢复；另一次原生checkbox定位点击未生效，核对仍未勾选后点击可见标签成功。没有重复提交业务请求，未发现产品故障。验收未在真实环境刻意制造网络中断/并发失败；此类分支仍由此前合成浏览器用例覆盖，不将其称为在线实测。

## 回退与证据保留

本次无需数据库回退。旧Web为`iterflow-web:version-flow-test-c0f68e1`，config ID `sha256:225f551c84d550737a2e796f676c495427437a03b38887dc1e71257ec76d7bb9`，旧首页SHA256 `f9a0d110c8a8079e09966afae630a88bb6004b0d290868e9aa18e13aea0cd7cd`。

服务器证据目录保留`old-web-image.tar`及其在`prepared.json`中的哈希、`images.env.before`和4份Compose/代理配置备份、`preserved.json`、`web-before.json`、各阶段JSON/日志。备份和原始保护快照不覆盖；不将配置原文写入仓库。完整阶段证据仍在服务器，本地另有上传包、离线测试、镜像校验和`deploy-terminal.png`、`final-server-verification.png`截图。

需要回退时，先确认无其他部署任务、当前正式/TEST非Web保护基线无漂移及旧镜像身份正确；仅将TEST的`WEB_IMAGE`恢复旧值（其余配置必须与备份一致，不能覆盖后续改动），使用同项目、同配置的Compose `up -d --no-deps --no-build --pull never --wait --wait-timeout 180 web`，健康后`systemctl reload iterflow-test-nginx`，再核对旧首页哈希、正式及TEST非Web保护快照。若保护基线漂移则停止，不盲目恢复。部署主控只在本次切换失败时尝试该受保护Web回退，本次未触发；正常部署完成后不要重跑`deploy`。

正式环境不变；未推送、合并或创建tag/Release。文档收尾提交不会改变已冻结部署的产品源码。
