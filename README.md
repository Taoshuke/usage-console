# Usage Console

深色的多来源用量看板，用于 `usage.heibox.cc`。目前是设计预览，页面内置示例数据。

## 文件

- `src/index.template.html` 页面模板，`__SAMPLE__` 处嵌入示例数据。
- `public/` 部署的静态文件，由 `scripts/build.py` 生成并提交。`public/data/usage.json` 目前是示例数据。
- `wrangler.jsonc` Worker `usage` 的配置，绑定 `usage.heibox.cc`，关闭 workers.dev 与预览地址。
- `sample/claude-code.json` Claude Code 的示例数据，总量与 2026-10-24 的 `/stats` 一致，每日分布为示例。
- `sample/usage.json` 看板读取的示例数据，Codex CLI、Anthropic API、订阅额度均为示例。
- `scripts/` 生成示例数据和构建页面的脚本。

```bash
python3 scripts/gen_claude_code_sample.py
python3 scripts/gen_sample.py
python3 scripts/build.py
```

## 数据

页面先读取同目录下的 `data/usage.json`，格式不符或读取失败时改用内置示例数据，并在页面上标出“示例数据”。格式见 `sample/usage.json`。

- `sources` 来源列表，`kind` 为 `logs`（会话记录）或 `billing`（平台账单）。
- `rows` 每行是某一天、某个来源、某个模型的用量：`in`、`out`、`cr`、`cw` 四项 token，`sessions`、`requests`，账单类来源另有实际金额 `cost`。
- `prices` 各模型每百万 token 的单价，用来估算没有 `cost` 的行。`verified` 为 `false` 时页面标出“价格待核实”。
- `quotas` 订阅额度的已用比例和重置时间。
- `punch` 每个来源按星期与钟点统计的消息数，7 行 24 列，周一开头。

现有的采集脚本 `collect.py` 还不输出这个格式，需要另行改写。示例中的模型单价是占位值，尚未核实。

## 部署

推送到 `main` 后由 Cloudflare Workers Builds 自动部署，部署命令 `npx wrangler deploy`，不需要构建命令，`public/` 已提交在仓库里。站点由 Cloudflare Access 应用“用量统计”保护，只放行本人邮箱。
