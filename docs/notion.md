# Notion storage

By default the collector writes `public/data/usage.json` and you redeploy the site to publish it. With Notion
storage the collector writes to a Notion database instead, and the Worker reads it on each visit (cached
for a minute), so new usage shows up without a deploy. Notion also keeps days whose local logs have been
cleaned up. 中文步骤见下半部分。

## Set up

1. Create an internal integration at notion.so/profile/integrations and copy its token.
2. Create the database under a page you choose, after connecting the integration to that page
   (page menu → Connections):

   ```bash
   NOTION_TOKEN=... python3 collector/sinks/notion.py init <parent page id>
   ```

   It prints the database id. If you created the database another way, connect the integration to it.
   Usage rows are titled `date|source|model`; a few settings rows are titled `@key` and have no date, so a view
   filtered on "Date is not empty" shows only usage.
3. In `tokenboard.config.json` set `"storage": "notion"` and put the id in `"notion": {"database": "..."}`.
4. In `wrangler.jsonc` fill `NOTION_DB`, then store the token as a secret:

   ```bash
   npx wrangler secret put NOTION_TOKEN
   ```
5. Save the token for the collector as the environment variable `NOTION_TOKEN`, run
   `python3 collector/collect.py` once, then deploy the page with `./scripts/deploy.sh` (or `deploy.ps1`).
   From then on schedule `scripts/sync.ps1` / `sync.sh`; `schedule.ps1` picks it automatically.

The database is data, not a document: leave its rows to the collector. A database created before the
`Messages` or `Cache write 1h` columns existed needs those number columns added by hand. When a source marks its rows
complete through a day (Claude Code does, for the days its `/stats` cache covers), rows of that source up to
that day that are no longer produced are moved to the Notion trash.

---

# 用 Notion 存储数据

默认情况下，采集脚本生成 `public/data/usage.json`，要重新部署网站才能发布。改用 Notion 存储后，采集脚本把数据写进一个 Notion 数据库，Worker 在每次访问时读取（缓存一分钟），新数据不用部署就能显示。本机日志被清理掉的日子，Notion 里也会一直保留。

## 设置步骤

1. 在 notion.so/profile/integrations 创建一个内部集成，复制它的令牌。
2. 把集成连接到你选定的页面（页面菜单 → Connections），然后在该页面下创建数据库：

   ```bash
   NOTION_TOKEN=... python3 collector/sinks/notion.py init <父页面 id>
   ```

   命令会输出数据库的 id。如果数据库是用别的方式建的，要把集成连接到这个数据库。
   用量行的标题是 `日期|来源|模型`；另有几行标题以 `@` 开头的设置行，没有日期，所以视图按“Date 不为空”筛选后只显示用量。
3. 在 `tokenboard.config.json` 里设置 `"storage": "notion"`，并把 id 填进 `"notion": {"database": "..."}`。
4. 在 `wrangler.jsonc` 里填写 `NOTION_DB`，再把令牌存为密钥：

   ```bash
   npx wrangler secret put NOTION_TOKEN
   ```
5. 把令牌存为采集脚本用的环境变量 `NOTION_TOKEN`，运行一次 `python3 collector/collect.py`，再用 `./scripts/deploy.sh`（或 `deploy.ps1`）部署页面。之后定时运行 `scripts/sync.ps1` 或 `sync.sh` 即可；`schedule.ps1` 会自动选择。

这个数据库存的是数据，不是文档，行内容交给采集脚本维护，不要手动修改。在新增 `Messages`、`Cache write 1h` 列之前建的数据库，要手动加上这两个数字列。来源声明某天之前的数据已完整时（Claude Code 对 `/stats` 缓存覆盖的日期会这样声明），该来源在这一天及之前、本次没有再生成的行会被移到 Notion 的垃圾箱。
