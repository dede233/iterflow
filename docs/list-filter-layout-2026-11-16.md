# 列表筛选布局修复（2026-11-16）

## 范围与版本

- 修复需求高级筛选中标签贴近前一控件、版本和参与人搜索提示截断的问题。共享组件同时检查反馈、需求、版本及发布记录四个消费者。
- 执行：6.1 Sol / xhigh；主协调者对组件差异和关键截图独立审查。采用 `ui-ux-pro-max` 的可见关联标签、8px 以上间距及响应式无横向溢出原则，沿用项目样式 token。
- 基线 HEAD：`db4c27a7a30e085dd6454ab028d18fcfdd584521`。下述开发验证结果对应此基线加当时未提交工作区改动，此基线本身不包含本次修复。
- 本次产品改动仅 `frontend/src/components/ui/ListFilterPanel.vue`；新增 `frontend/e2e/list-filter-layout.spec.ts` 一个布局回归和本文。未修改消费者、接口、业务、数据库及已有文档清理/部署记录。
- 本文记录布局修复开发阶段，当时未提交、推送、部署或保存真实业务数据；后续本地冻结和 TEST 部署另见 [TEST 部署记录](list-filter-test-deployment-2026-11-16.md)。

## 结果

用户反馈“还是不上置了吧”后，当前交付改为桌面/平板左侧同排标签，移动抽屉保留原有上方标签。基础与高级字段使用网格，查询、重置及更多筛选保持独立动作区。字段之间保持 16px 网格间隔，普通标签列为 72px（含右侧 8px 留白），网格目标最小宽度 280px，控件填满剩余空间；1440px 下需求高级筛选自然排列为 3+2 列，版本及参与人提示完整显示。按面板自身宽度调整动作区并自然换行，不强行凑五列。日期字段使用 100px 标签列及 380px 的目标最小网格宽度，避免挤压日期范围。

产品文件 SHA-256：`dec1d88f819d50ecc7963306ec5db132014504bdca8ce21ba9e6a10e3f6321b3`。
新增测试 SHA-256：`db02504d776d5c19f0ab5b07b0c681e44620a38a2be5ce10205f8fe47ea49d7c`。

## 验证

当前左侧标签证据目录：`/Users/xiaweiyi/Developer/deliverables/iterflow/2026-11-16/list-filter-layout/inline-labels/`。上一轮已替换的上置方案证据保留在父目录，未覆盖。以下命令在 `frontend/` 执行，浏览器使用本任务独立 Vite `127.0.0.1:5186`，API 全部由 Playwright Mock；未访问真实后端、保留数据库或远端环境。

| 层级 | 命令/范围 | 结果 | 日志 |
| --- | --- | --- | --- |
| 单测 / Mock（上一轮结果） | `npm test -- --maxWorkers=2 src/views/listProductivity.component.spec.ts src/views/listWorkspaceFilters.spec.ts src/components/ListEntityFilterSelect.spec.ts src/utils/listQuery.spec.ts src/utils/appliedListFilters.spec.ts src/composables/useListQuery.spec.ts src/api/filterOptions.spec.ts src/views/release/ReleaseListView.spec.ts` | 上一轮 8 文件、75 项通过；本轮无脚本/逻辑变更，复用该结果，未重跑 | `../unit.log` |
| 静态（本轮） | `npm run build`（包含 `vue-tsc --noEmit`） | 通过，退出 0 | `build.log` |
| 静态（上一轮结果） | `npm run check:api-types` | 上一轮通过，退出 0；本轮无接口/类型变更，未重跑 | `../api-types.log` |
| 静态（上一轮结果） | `npm run check:bundle` | 上一轮通过，最大 JS chunk 为富文本编辑器 400.0 KiB；本轮未重跑 | `../bundle.log` |
| 浏览器 / Mock（本轮） | `ITERFLOW_FILTER_LAYOUT_EVIDENCE_ROOT=<证据目录> npx playwright test --config=<证据目录>/playwright-gallery.config.ts --output=<证据目录>/gallery-artifacts --reporter=line` | 四个列表 × 1440/900/375px，12 项通过，退出 0 | `gallery-layout.log` |
| 浏览器 / Mock（本轮） | `ITERFLOW_WEB_URL=http://127.0.0.1:5186 npx playwright test e2e/list-productivity.spec.ts e2e/list-filter-options.spec.ts e2e/list-filter-layout.spec.ts --workers=1 --output=<证据目录>/regression-artifacts --reporter=line` | 25 项通过，退出 0；查询/重置、分页、URL 回填、远程候选及日期范围交互通过 | `browser-regression.log` |

临时 gallery 脚本及配置仅保存在证据目录，未固化为仓库内 12 项重复回归。它实际展开高级筛选/移动抽屉，检查桌面/平板标签文字处于控件左侧且至少间隔 8px、标签垂直中心与控件偏差不超过 2px；移动抽屉继续检查上方标签。同时验证全部字段至少 8px 间隔、搜索提示完整宽度、控件及页面无横向越界；版本及发布记录另检查日期范围宽度和日期面板打开。

主要截图（证据目录内）：

- `requirements-1440-expanded.png`：3+2 列高级筛选，左侧标签和搜索提示完整。
- `requirements-1440-collapsed.png`：基础三项与动作同一行。
- `requirements-900-expanded.png`：平板左侧标签，字段自然换行。
- `requirements-375-expanded.png`：手机完整抽屉。
- `versions-1440-expanded.png`、`versions-900-expanded.png`、`versions-375-expanded.png`：日期范围及负责人。
- `feedbacks-{1440,900,375}-expanded.png`、`releases-{1440,900,375}-expanded.png`：其余消费者兼容。

## 本轮首次问题与修正

左侧标签首次几何断言误用整个标签盒子的右沿，盒内已包含 8px 右侧留白，因此盒子与控件起点相接，断言要求盒外再留白导致失败（`initial-layout.log`、`initial-artifacts/`）。实际截图标签可读且未贴靠控件。改为测量标签文字 Range 的右沿，继续要求文字与控件至少 8px 距离，保留垂直居中和全部越界断言；随后 12 项 gallery 全部通过。未改产品来迎合错误的盒模型断言。

## 上一轮已替换设计历史

以下为用户要求恢复左侧标签之前的上置方案执行记录，证据均在当前目录的父目录，仅作历史，不代表当前交付设计：

1. 旧版 1440px 需求新增布局断言失败：标签与控件仍在同排，未满足清晰上下关联。见 `baseline-layout.log`、`baseline-artifacts/` 和 `requirements-1440-before-expanded.png`；修复后首次单项执行通过（`initial-layout.log`）。
2. 临时 gallery 首轮 6 项通过、6 项失败（`gallery-layout.log`）。其中反馈页期望标题误写“反馈管理”，实际为“反馈中心”；375px 采集到抽屉滑入动画的中间帧，几何坐标尚在视口外。保留原始日志及 `gallery-artifacts/`，修正脚本标题并显式等待进行中的动画结束，未放宽间距或越界断言；随后 12 项全部通过。
3. 首版高级网格最小列宽为 220px，1440px 下产生 4+1 列。独立视觉审查建议减少空白后改为 208px，五列提示仍完整；最终脚本和已有回归均针对这一版执行。

## 审查、限制与资源

主协调者已独立查看本轮 1440px 需求及 900px 需求/版本截图并审查组件差异，确认左侧同排、间距、日期标签宽度和移动模板。执行代理已实际 `view_image` 查看本轮 1440px/900px 需求及版本、375px 需求截图，确认标签位置、完整提示、换行及抽屉显示。

本轮为静态与 Mock 浏览器证据，未跑真实后端主链、数据库、Docker、S3、备份恢复、MySQL 双矩阵或完整 CI；这些不属于此次局部前端布局变更的执行范围。浏览器串行运行。`git diff --check` 通过（`diff-check.log`），组件差异保存在 `product.diff`。本轮 5186 为核对空闲后新建的独占 Vite 服务；已核对 PID 88852、启动命令及仓库目录，验证结束后仅向此进程发送 SIGTERM，进程退出 143，5186 已无监听（`resource-cleanup.log`）。其他已有端口、进程和数据保持不动。
