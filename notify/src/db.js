// データベースの薄い共通口。{ all(sql, params) → 行の配列, run(sql, params) → 変更行数 }
//   fromD1   … Worker 内(env.DB)
//   fromRest … GitHub Actions の値下がりチェック(Cloudflare の D1 HTTP API)
//   テストでは node:sqlite で同じ口を作る(test/helpers.js)

export function fromD1(d1) {
  return {
    async all(sql, params = []) {
      return (
        await d1
          .prepare(sql)
          .bind(...params)
          .all()
      ).results;
    },
    async run(sql, params = []) {
      return (
        await d1
          .prepare(sql)
          .bind(...params)
          .run()
      ).meta.changes;
    },
  };
}

const CF_API = "https://api.cloudflare.com/client/v4";

async function cfFetch(fetchImpl, token, path, init = {}) {
  const res = await fetchImpl(`${CF_API}${path}`, {
    ...init,
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok || !body?.success) {
    const msg = body?.errors?.map((e) => e.message).join("; ") || `HTTP ${res.status}`;
    throw new Error(`Cloudflare API ${path}: ${msg}`);
  }
  return body.result;
}

export function fromRest({ accountId, databaseId, token, fetchImpl = fetch }) {
  const query = (sql, params) =>
    cfFetch(fetchImpl, token, `/accounts/${accountId}/d1/database/${databaseId}/query`, {
      method: "POST",
      body: JSON.stringify({ sql, params }),
    });
  return {
    async all(sql, params = []) {
      return (await query(sql, params))[0].results;
    },
    async run(sql, params = []) {
      return (await query(sql, params))[0].meta?.changes ?? 0;
    },
  };
}

// 名前でD1データベースを探す(create=true なら無ければ作る)。ID を返す
export async function findDatabase({ accountId, token, name, create = false, fetchImpl = fetch }) {
  const list = await cfFetch(
    fetchImpl,
    token,
    `/accounts/${accountId}/d1/database?name=${encodeURIComponent(name)}`,
  );
  const found = list.find((d) => d.name === name);
  if (found) return found.uuid;
  if (!create) throw new Error(`D1 database "${name}" not found (deploy first)`);
  const made = await cfFetch(fetchImpl, token, `/accounts/${accountId}/d1/database`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  return made.uuid;
}
