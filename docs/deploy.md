# Deploy to Cloudflare

tokenboard is static files. These steps put it on your own subdomain as a Cloudflare Worker and lock it with
Cloudflare Access so only your email can open it. 中文步骤见下半部分。

## 1. Configure

```bash
cp wrangler.example.jsonc wrangler.jsonc          # set "name" and your domain under "routes"
cp tokenboard.config.example.json tokenboard.config.json
npm install                                       # installs the pinned wrangler
npx wrangler login
```

## 2. Protect it with Access first

In the Cloudflare dashboard open **Zero Trust → Access → Applications → Add an application → Self-hosted**, enter
the same domain as in `wrangler.jsonc`, and add a policy that allows only your email. Do this before the first deploy
so your data is never public. `workers_dev` and `preview_urls` stay `false` because those URLs are not covered by Access.

## 3. Deploy

```bash
./scripts/deploy.sh          # macOS / Linux: collect, build, deploy
pwsh scripts/deploy.ps1      # Windows
```

Open your domain; you should be asked to sign in through Access.

## 4. Keep it fresh

Scheduled runs have no browser to log in with, so create an API token (**My Profile → API Tokens**, permission
**Account → Workers Scripts → Edit**) and store it as the user environment variable `CLOUDFLARE_API_TOKEN`.

- Windows: `pwsh scripts/schedule.ps1 -At 21:30` registers a daily task (`-At 08:00,20:00` for twice a day,
  no arguments to show it, `-Remove` to delete it). Missed runs start when the computer is back on.
- macOS / Linux: add a cron entry, for example `30 21 * * * cd /path/to/tokenboard && ./scripts/deploy.sh`.

Do not connect the repository to Workers Builds for your personal deployment: the build machine cannot see your
usage, and your data must not be committed.

---

# 部署到 Cloudflare

## 1. 配置

```bash
cp wrangler.example.jsonc wrangler.jsonc          # 改 "name" 和 "routes" 里的域名
cp tokenboard.config.example.json tokenboard.config.json
npm install                                       # 安装锁定版本的 wrangler
npx wrangler login
```

## 2. 先用 Access 保护

在 Cloudflare 后台进入 **Zero Trust → Access → Applications → Add an application → Self-hosted**，填入和 `wrangler.jsonc` 相同的域名，添加一条只放行你邮箱的策略。要在第一次部署之前做，数据才不会公开。`workers_dev` 和 `preview_urls` 保持 `false`，因为这两个地址不受 Access 保护。

## 3. 部署

```bash
./scripts/deploy.sh          # macOS / Linux：采集、构建、部署
pwsh scripts/deploy.ps1      # Windows
```

打开你的域名，应该会先要求通过 Access 登录。

## 4. 定时更新

定时任务没有浏览器可以登录，所以要建一个 API 令牌（**My Profile → API Tokens**，权限 **Account → Workers Scripts → Edit**），存为用户环境变量 `CLOUDFLARE_API_TOKEN`。

- Windows：`pwsh scripts/schedule.ps1 -At 21:30` 注册每天运行的任务（`-At 08:00,20:00` 一天两次，不带参数查看，`-Remove` 删除）。错过的运行会在电脑重新开机后补上。
- macOS / Linux：加一条 cron，例如 `30 21 * * * cd /path/to/tokenboard && ./scripts/deploy.sh`。

个人部署不要把仓库连到 Workers Builds：构建机器读不到你的用量，你的数据也不能提交进仓库。
