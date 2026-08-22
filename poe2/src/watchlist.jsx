import { useEffect, useState } from "react";

// ウォッチリスト + 前回閲覧時からの差分表示(端末内localStorageに保存)
// 同一オリジン(game-souba.com)で複数サイトを配信しているため、キーはサイト名で分ける

const load = (key, fallback) => {
  try {
    const v = JSON.parse(localStorage.getItem(key));
    return v ?? fallback;
  } catch {
    return fallback;
  }
};
const save = (key, v) => {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* プライベートモード等では保存しない */
  }
};

export const currencyKey = (c) => `c:${c.id}`;
export const uniqueKey = (u) => `u:${u.name}|${u.baseType}`;

export function useWatchlist(site) {
  const KEY = `${site}:watchlist`;
  const [items, setItems] = useState(() => load(KEY, []));
  const has = (key) => items.some((i) => i.key === key);
  const toggle = (entry) => {
    setItems((prev) => {
      const next = prev.some((i) => i.key === entry.key)
        ? prev.filter((i) => i.key !== entry.key)
        : [...prev, entry];
      save(KEY, next);
      return next;
    });
  };
  return { items, has, toggle };
}

// 前回閲覧時のデータとの比較。データ更新(generatedAt変化)があった場合のみ
// 前回比を返し、スナップショットを現在のデータで置き換える。
// 同じデータのうちに再訪した場合は基準を保持する(0%だらけの表示を避ける)。
export function usePrevDiff(site, economy, rateOf) {
  const KEY = `${site}:snapshot`;
  const [prev] = useState(() => load(KEY, null));
  useEffect(() => {
    if (prev && prev.generatedAt === economy.generatedAt) return;
    const values = {};
    for (const c of economy.currencies) values[currencyKey(c)] = rateOf(c);
    for (const u of [...economy.gainers, ...economy.losers, ...economy.expensive])
      values[uniqueKey(u)] = u.value;
    save(KEY, { generatedAt: economy.generatedAt, values });
    // 初回マウント時に一度だけ実行すればよい
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!prev || prev.generatedAt === economy.generatedAt)
    return { prevAt: null, diffOf: () => null };
  return {
    prevAt: prev.generatedAt,
    diffOf: (key, current) => {
      const old = prev.values?.[key];
      if (typeof old !== "number" || !(old > 0) || typeof current !== "number") return null;
      return ((current - old) / old) * 100;
    },
  };
}

export function WatchStar({ watched, onToggle, T }) {
  return (
    <button
      onClick={onToggle}
      aria-label={watched ? "ウォッチ解除" : "ウォッチする"}
      title={watched ? "ウォッチ解除" : "ウォッチリストに追加"}
      style={{
        background: "none",
        border: "none",
        cursor: "pointer",
        fontSize: 15,
        lineHeight: 1,
        padding: "2px 4px",
        color: watched ? T.goldLight : T.textLow,
        flexShrink: 0,
      }}
    >
      {watched ? "★" : "☆"}
    </button>
  );
}

function PrevDiff({ pct, T }) {
  if (pct === null) return null;
  const color = pct > 0.05 ? T.up : pct < -0.05 ? T.down : T.textLow;
  const sign = pct > 0.05 ? "▲" : pct < -0.05 ? "▼" : "―";
  return (
    <div style={{ fontSize: 10, color, whiteSpace: "nowrap" }}>
      前回比 {sign} {Math.abs(pct).toFixed(1)}%
    </div>
  );
}

export function WatchlistCard({
  id,
  T,
  economy,
  rateOf,
  unit,
  watch,
  diff,
  Card,
  Sparkline,
  Change,
  fmtRate,
  fmtDate,
}) {
  const resolve = (entry) => {
    if (entry.type === "currency") {
      const c = economy.currencies.find((x) => currencyKey(x) === entry.key);
      return c ? { value: rateOf(c), change7d: c.change7d, spark: c.spark } : null;
    }
    const pool = [...economy.gainers, ...economy.losers, ...economy.expensive];
    const u = pool.find((x) => uniqueKey(x) === entry.key);
    return u ? { value: u.value, change7d: u.change7d, spark: u.spark } : null;
  };

  return (
    <Card
      id={id}
      title="⭐ ウォッチリスト"
      sub={
        watch.items.length === 0
          ? "各一覧の ☆ をタップすると、気になる通貨・アイテムをここに固定表示できます(この端末にだけ保存されます)"
          : diff.prevAt
            ? `「前回比」は前回閲覧時(${fmtDate(diff.prevAt)}時点のデータ)との比較`
            : "データが更新されると、前回閲覧時との差分がここに表示されます"
      }
    >
      {watch.items.length > 0 && (
        <div>
          {watch.items.map((entry) => {
            const res = resolve(entry);
            const d = diff.diffOf(entry.key, res?.value);
            return (
              <div
                key={entry.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "7px 4px",
                  borderBottom: `1px solid ${T.outline}`,
                }}
              >
                <WatchStar watched onToggle={() => watch.toggle(entry)} T={T} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: T.text,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {entry.name}
                  </div>
                  {entry.baseType && (
                    <div style={{ fontSize: 11, color: T.textLow }}>{entry.baseType}</div>
                  )}
                </div>
                {res ? (
                  <>
                    <Sparkline data={res.spark} color={res.change7d >= 0 ? T.up : T.down} />
                    <div style={{ textAlign: "right" }}>
                      <div style={{ fontSize: 13, color: T.text, fontWeight: 600 }}>
                        {fmtRate(res.value)}{" "}
                        <span style={{ fontSize: 10, color: T.textLow }}>{unit}</span>
                      </div>
                      <Change pct={res.change7d} />
                      <PrevDiff pct={d} T={T} />
                    </div>
                  </>
                ) : (
                  <span style={{ fontSize: 11, color: T.textLow }}>
                    現在ランキング圏外
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}
