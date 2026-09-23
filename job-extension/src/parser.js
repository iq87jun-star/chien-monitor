// 求人の給与・勤務時間の文章から年収目安・時給換算・固定残業代を読み取る(純粋関数・DOM非依存)。
// content script(クラシックスクリプト)と node:test の両方から読み込むため、
// export は使わず globalThis.JobParser に公開する。
// 金額はすべて円。解析できない項目は null にし、推測で埋めない。
(() => {
  // 年間休日の記載がない時の月平均労働日数(年間休日120日 → (365-120)/12 ≒ 20.4日)
  const DEFAULT_WORKDAYS_PER_MONTH = 20.4;
  // 実働時間の記載がない時の1日の労働時間
  const DEFAULT_HOURS_PER_DAY = 8;

  const toHalf = (s) => String(s ?? "").normalize("NFKC");

  // 「30万4,240円」「24万2000円」「23.85万円」「300,000円」→ 円
  function parseYen(s) {
    const t = toHalf(s).replace(/,/g, "");
    const m = t.match(/(\d+(?:\.\d+)?)\s*万\s*(\d+)?\s*円?|(\d+(?:\.\d+)?)\s*円/);
    if (!m) return null;
    if (m[1] != null) return Math.round(Number(m[1]) * 10000 + Number(m[2] ?? 0));
    return Math.round(Number(m[3]));
  }

  // 金額の表記(万円・円)にマッチする正規表現の部品
  const YEN = String.raw`\d+(?:[.,]\d+)*\s*万\s*(?:\d+(?:,\d+)*\s*)?円?|\d+(?:,\d+)*\s*円`;
  // 「〜」の表記揺れ
  const TILDE = String.raw`\s*[~〜～\-－ー]\s*`;

  // 「月給30万円～40万円」のような 種類+金額(範囲) を探す。gap は種類と金額の間に許す文字数
  function findRange(text, kinds, gap = 6) {
    const re = new RegExp(`(${kinds})[^\\d]{0,${gap}}(${YEN})(?:${TILDE}(${YEN}))?`);
    const m = text.match(re);
    if (!m) return null;
    const min = parseYen(m[2]);
    const max = m[3] ? parseYen(m[3]) : null;
    if (min == null) return null;
    const validMax = max != null && max >= min ? max : null;
    // 「月給30万円～」のように上限なしの幅で書かれているか(単独の金額とは表示を分ける)
    const open = validMax == null && /^\s*[~〜～]/.test(text.slice(m.index + m[0].length));
    return { kind: m[1], min, max: validMax, open };
  }

  // 賞与の月数「賞与（4.65ヶ月分）」「賞与年2回（昨年度実績：6.2ヶ月分）」
  function findBonusMonths(text) {
    const m = text.match(/賞与[^。\n]{0,30}?(\d+(?:\.\d+)?)\s*[ヶヵかカケ箇]?\s*月分/);
    return m ? Number(m[1]) : null;
  }

  // 固定残業代・みなし残業代。「みなし残業はありません」等の否定は検出しない
  function findFixedOvertime(text) {
    if (/(固定残業|みなし残業)[^。\n]{0,10}(ありません|なし|無し|ございません)/.test(text)) {
      return null;
    }
    const idx = text.search(/固定残業|みなし残業/);
    if (idx < 0) return null;
    const seg = text.slice(idx, idx + 80);
    const hours = seg.match(/(\d+(?:\.\d+)?)\s*時間/);
    const amount = seg.match(new RegExp(YEN));
    return {
      hours: hours ? Number(hours[1]) : null,
      amount: amount ? parseYen(amount[0]) : null,
    };
  }

  // 1日の実働時間「実働7時間45分」「実働7.5時間」「所定労働時間：7時間45分」
  function findHoursPerDay(text) {
    const m = text.match(
      /(?:実働|所定労働時間|労働時間)[^\d]{0,4}(\d+(?:\.\d+)?)\s*時間\s*(?:(\d+)\s*分)?/,
    );
    if (!m) return null;
    const h = Number(m[1]) + (m[2] ? Number(m[2]) / 60 : 0);
    return h > 0 && h <= 12 ? h : null;
  }

  // 年間休日「年間休日120日以上」
  function findHolidays(text) {
    const m = text.match(/年間休日[^\d]{0,4}(\d{2,3})\s*日/);
    const n = m ? Number(m[1]) : null;
    return n != null && n >= 50 && n <= 200 ? n : null;
  }

  // 記載されている年収。この求人の年収に近いものから優先する
  // (「平均年収」は会社全体の平均なので、他に記載が無い時だけ使い、companyAverage を立てる)。
  // 「年収例 <入社初年度の年収イメージ> ■首都圏：478万円」のように語と金額が離れることがある
  const STATED_KINDS = ["想定年収", "年収例", "(?<!平均)年収", "平均年収"];
  function findStatedAnnual(text) {
    for (const kind of STATED_KINDS) {
      const r = findRange(text, kind, 25);
      if (r && r.min >= 1_000_000) return { ...r, companyAverage: kind === "平均年収" };
    }
    return null;
  }

  // 求人の給与関連の文章をまとめて解析する。
  // salaryText: 「給与」欄など、workText: 「勤務時間」「休日」欄など(無ければ空でよい)
  function analyze(salaryText, workText = "") {
    const salary = toHalf(salaryText);
    const work = toHalf(workText);
    const all = `${salary}\n${work}`;

    const monthly = findRange(salary, "月給|月収|基本給|月額");
    const hourly = findRange(salary, "時給");
    const daily = findRange(salary, "日給");
    const yearly = findRange(salary, "年俸");
    const stated = findStatedAnnual(salary);
    const bonusMonths = findBonusMonths(salary);
    const fixedOvertime = findFixedOvertime(all);
    const hoursPerDay = findHoursPerDay(work) ?? findHoursPerDay(salary);
    const holidays = findHolidays(all);

    const workdays = holidays != null ? (365 - holidays) / 12 : DEFAULT_WORKDAYS_PER_MONTH;
    const hours = hoursPerDay ?? DEFAULT_HOURS_PER_DAY;
    const monthlyHours = workdays * hours;
    const assumptions = [];
    if (holidays == null) assumptions.push("年間休日120日");
    if (hoursPerDay == null) assumptions.push("1日8時間");

    // 月額の基準(月給が無ければ日給・時給から月額に直す)
    let base = null;
    let basis = null;
    if (monthly) {
      base = monthly;
      basis = monthly.kind; // 月給・月収・基本給・月額(記載の語をそのまま示す)
    } else if (daily) {
      base = {
        min: daily.min * workdays,
        max: daily.max && daily.max * workdays,
        open: daily.open,
      };
      basis = "日給";
    } else if (hourly) {
      base = {
        min: hourly.min * monthlyHours,
        max: hourly.max && hourly.max * monthlyHours,
        open: hourly.open,
      };
      basis = "時給";
    }

    // 年収目安: 年俸があればそれ、なければ月額×12+賞与(月額×月数で概算)
    let annual = null;
    if (yearly && yearly.min >= 1_000_000) {
      annual = {
        min: yearly.min,
        max: yearly.max,
        open: yearly.open,
        bonusIncluded: true,
        from: "年俸",
      };
    } else if (base) {
      const months = 12 + (bonusMonths ?? 0);
      annual = {
        min: Math.round(base.min * months),
        max: base.max ? Math.round(base.max * months) : null,
        open: Boolean(base.open),
        bonusIncluded: bonusMonths != null,
        from: basis,
      };
    }

    // 時給換算(月額÷月の労働時間)。固定残業代があれば、その分を除いた基本部分の時給も出す
    let hourlyEquivalent = null;
    if (base && basis !== "時給") {
      hourlyEquivalent = {
        min: Math.round(base.min / monthlyHours),
        max: base.max ? Math.round(base.max / monthlyHours) : null,
      };
    }
    let baseWithoutOvertime = null;
    if (base && fixedOvertime?.amount && fixedOvertime.amount < base.min) {
      baseWithoutOvertime = {
        monthly: base.min - fixedOvertime.amount,
        hourly: Math.round((base.min - fixedOvertime.amount) / monthlyHours),
      };
    }

    const found = Boolean(annual || stated);
    return {
      found,
      basis,
      monthly: base && { min: Math.round(base.min), max: base.max ? Math.round(base.max) : null },
      bonusMonths,
      annual,
      stated,
      hourlyEquivalent,
      fixedOvertime,
      baseWithoutOvertime,
      hoursPerDay,
      holidays,
      assumptions,
    };
  }

  globalThis.JobParser = { parseYen, analyze };
})();
