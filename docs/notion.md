# Notion storage

By default the collector writes `public/data/usage.json` and you redeploy the site to publish it. With Notion
storage the collector writes to two Notion databases instead, and the Worker reads them on each visit (cached
for a minute), so new usage shows up without a deploy. Notion also keeps days whose local logs have been
cleaned up. 中文步骤见下半部分。

## Set up

1. Create an internal integration at notion.so/profile/integrations and copy its token.
2. Create the databases under a page you choose, after connecting the integration to that page
   (page menu → Connections):

   ```bash
   NOTION_TOKEN=... python3 collector/sinks/notion.py init <parent page id>
   ```

   It prints the two database ids. If you created the databases another way, connect the integration to each.
3. In `tokenboard.config.json` set `"storage": "notion"` and fill `"notion"` with the two ids.
4. In `wrangler.jsonc` fill `NOTION_USAGE_DB` and `NOTION_SETTINGS_DB`, then store the token as a secret:

   ```bash
   npx wrangler secret put NOTION_TOKEN
   ```
5. Save the token for the collector as the environment variable `NOTION_TOKEN`, run
   `python3 collector/collect.py` once, then deploy the page with `./scripts/deploy.sh` (or `deploy.ps1`).
   From then on schedule `scripts/sync.ps1` / `sync.sh`; `schedule.ps1` picks it automatically.

The databases are data, not documents: leave their rows to the collector.

---

# 用 Notion 存储数据

默认情况下，采集脚本生成 `public/data/usage.json`，要重新部署网站才能发布。改用 Notion 存储后，采集脚本把数据写进两个 Notion 数据库，Worker 在每次访问时读取（缓存一分钟），新数据不用部署就能显示。本机日志被清理掉的日子，Notion 里也会一直保留。

## 设置步骤

1. 在 notion.so/profile/integrations 创建一个内部集成，复制它的令牌。
2. 把集成连接到你选定的页面（页面菜单 → Connections），然后在该页面下创建数据库：

   ```bash
   NOTION_TOKEN=... python3 collector/sinks/notion.py init <父页面 id>
   ```

   命令会输出两个数据库的 id。如果数据库是用别的方式建的，要把集成分别连接到这两个数据库。
3. 在 `tokenboard.config.json` 里设置 `"storage": "notion"`，并在 `"notion"` 里填入两个 id。
4. 在 `wrangler.jsonc` 里填写 `NOTION_USAGE_DB` 和 `NOTION_SETTINGS_DB`，再把令牌存为密钥：

   ```bash
   npx wrangler secret put NOTION_TOKEN
   ```
5. 把令牌存为采集脚本用的环境变量 `NOTION_TOKEN`，运行一次 `python3 collector/collect.py`，再用 `./scripts/deploy.sh`（或 `deploy.ps1`）部署页面。之后定时运行 `scripts/sync.ps1` 或 `sync.sh` 即可；`schedule.ps1` 会自动选择。

这两个数据库存的是数据，不是文档，行内容交给采集脚本维护，不要手动修改。
