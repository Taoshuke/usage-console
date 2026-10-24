// tokenboard Worker. Static files are served from public/ by the assets binding; this script only answers
// data/usage.json when the data lives in Notion (NOTION_TOKEN set). Without Notion it simply passes through.
const NOTION = 'https://api.notion.com/v1';
const VERSION = '2022-06-28';
const CACHE_SECONDS = 60;
const NUMBERS = [['in', 'Input'], ['out', 'Output'], ['cr', 'Cache read'], ['cw', 'Cache write'], ['cw1h', 'Cache write 1h'],
  ['sessions', 'Sessions'], ['messages', 'Messages'], ['requests', 'Requests'], ['cost', 'Cost']];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === '/data/usage.json' && env.NOTION_TOKEN) return usage(request, env, ctx);
    return env.ASSETS.fetch(request);
  },
};

async function usage(request, env, ctx) {
  const cache = caches.default, key = new Request(new URL('/data/usage.json', request.url).toString());
  const hit = await cache.match(key);
  if (hit) return hit;
  let body, status = 200;
  try {
    body = JSON.stringify(await fromNotion(env));
  } catch (err) {
    body = JSON.stringify({error: String(err.message || err)});
    status = 502;
  }
  const res = new Response(body, {status, headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': `private, max-age=0, s-maxage=${CACHE_SECONDS}`,
  }});
  if (status === 200) ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

async function queryAll(env, databaseId) {
  const pages = [];
  let cursor;
  do {
    const r = await fetch(`${NOTION}/databases/${databaseId}/query`, {
      method: 'POST',
      headers: {authorization: `Bearer ${env.NOTION_TOKEN}`, 'notion-version': VERSION, 'content-type': 'application/json'},
      body: JSON.stringify(cursor ? {page_size: 100, start_cursor: cursor} : {page_size: 100}),
    });
    if (!r.ok) throw new Error(`Notion ${r.status}: ${(await r.text()).slice(0, 200)}`);
    const j = await r.json();
    pages.push(...j.results);
    cursor = j.has_more ? j.next_cursor : null;
  } while (cursor);
  return pages;
}

const plain = (rich) => (rich || []).map(t => t.plain_text || '').join('');

async function fromNotion(env) {
  // Usage rows are titled date|source|model; settings rows are titled @key and carry JSON in Value.
  const settings = {}, rows = [];
  for (const p of await queryAll(env, env.NOTION_DB)) {
    const title = plain(p.properties.Key.title);
    if (title.startsWith('@')) {
      try { settings[title.slice(1)] = JSON.parse(plain(p.properties.Value && p.properties.Value.rich_text)); } catch { /* skip a hand-edited value */ }
      continue;
    }
    const parts = title.split('|');
    if (parts.length < 3) continue;
    const row = {d: parts[0], src: parts[1], model: parts.slice(2).join('|')};
    for (const [k, name] of NUMBERS) {
      const n = p.properties[name] && p.properties[name].number;
      if (n != null) row[k] = n;
    }
    rows.push(row);
  }
  rows.sort((a, b) => a.d < b.d ? -1 : a.d > b.d ? 1 : 0);
  return {
    version: 1,
    generated: settings.generated || new Date().toISOString(),
    timezone: settings.timezone || 'UTC',
    currency: settings.currency || 'USD',
    sources: settings.sources || [],
    prices: settings.prices || {verified: false, per_mtok: {}},
    quotas: settings.quotas || [],
    longest_session: settings.longest_session || null,
    punch: settings.punch || {},
    rows,
  };
}
