# 2026-11-02 验证码布局与重新验证入口测试部署

用户授权仅部署测试环境。已于 2026-11-02 12:05:43 +08:00 完成，入口 https://sx-kc.xyz:8444/#/profile 。源码为 `1923a224e4a4436f0d9c9c1f3148226e3813907b`。

## 部署范围与保留核验

- 仅替换 TEST project `iterflow-acceptance-20261012-753ebd` 的 Web 为 `iterflow-web:mail-layout-1923a22`；使用 linux/amd64 无网络构建，镜像 config 为 `sha256:1d62c7a41a9cf75a704b11e470fd25a828cc6c238122580722511dfab6d94f64`。
- 压缩镜像包 SHA-256：`5e2a945af8f3570e824a7cbe330ca9a6905623755bfb274325030889648d4df1`。服务器导入后核验 config、架构与源码标签。
- `images.env` 只更新 WEB_IMAGE；API、worker 与 BUILD_SHA 保持 cd1f7ee。Compose 使用 `--no-deps --no-build --pull never`，仅启动 Web；只 reload 测试 Nginx。
- 前后比较正式容器 ID／镜像／启动时间／挂载／重启策略、正式 Nginx 配置摘要，全部相同。测试 API、worker、数据库及 Redis 容器也保持不变。
- SMTP 所在运行配置、迁移与数据库配置、root-client、Compose、acceptance、自动恢复文件摘要全部相同。不执行数据库迁移、数据写入、恢复或账号变更。
- 保留原 Web `iterflow-web:multi-accept-cd1f7ee` 及 images.env 备份，可只回退 Web。部署脚本包含失败时的 Web 回退；本次成功，无需触发。

## 验证结果

- API／Web healthy、API ready、worker 运行检查 PASS，HTTPS 8444 返回 200。
- 公网 index.html 与本地部署产物 SHA-256 一致：`696200227460908821832a20df644feb55412479c67488faaaf78a1393bec11c`。
- 浏览器以既有已验证邮箱账号刷新个人中心：默认隐藏验证码行、显示“重新验证”；点击后展开输入框及“发送验证码”，输入框在左、按钮在右；刷新重新收起，PASS。
- 375px 手机宽度：外层输入框与发送按钮均为 44px 高、同一 y 坐标，左右顺序正确、页面无横向溢出，PASS。首次几何读取选中了内部原生 input（30px）而非 44px 可见外框，改为测量 Element Plus 外框后确认对齐；不涉及代码修改。
- 本次没有点击发送验证码、提交邮箱验证或修改邮件偏好，未发送真实邮件。验证成功后的收起及未验证邮箱交互沿用本地 mock 验证；此前组件 5 PASS、浏览器 profile 2 PASS、类型与生产构建 PASS，见开发执行记录。本部署轮未重跑业务主链或远端 CI。
- Fresh Self-Review：部署脚本限定测试 Web，镜像/公共产物一致，受保护配置与其他容器无变化，无未解决部署问题。

服务端证据：`/opt/iterflow/upgrade-evidence/mail-layout-1923a22`，包括 before、配置摘要、commands.log、images.env.before 与 deployed.json。本地证据：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-02/mail-layout-deployment-1923a22`，包括构建日志、manifest、脚本、服务器成功截图、已验证收起／展开截图及手机几何记录。未推送、合并、创建 tag/Release 或操作正式环境。
