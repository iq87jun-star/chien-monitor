// 物件ページの項目(賃料・価格・面積・管理費・利回り等)から単価・月額・利回りを計算する(純粋関数)。
// content script(クラシックスクリプト)と node:test の両方から読み込むため、
// export は使わず globalThis.RealtyParser に公開する。
// 金額はすべて円、面積は㎡。読めない項目は null にし、推測で埋めない。
(() => {
  const TSUBO_PER_M2 = 0.3025; // 1㎡ = 0.3025坪
  const toHalf = (s) => String(s ?? "").normalize("NFKC");

  // 「14万円」「7.5万円」「10000円」「1万4800円」「3,230万円」「1億2000万円」「1億円」→ 円
  function parseYen(s) {
    const t = toHalf(s).replace(/,/g, "");
    const m = t.match(/(?:(\d+(?:\.\d+)?)\s*億)?\s*(?:(\d+(?:\.\d+)?)\s*万)?\s*(\d+)?\s*円/);
    if (!m || (m[1] == null && m[2] == null && m[3] == null)) return null;
    return Math.round(Number(m[1] ?? 0) * 1e8 + Number(m[2] ?? 0) * 1e4 + Number(m[3] ?? 0));
  }

  // 「20m2」「56.88m²」「51.58㎡(壁芯)」→ ㎡。「12.3坪」は㎡に直す
  function parseArea(s) {
    const t = toHalf(s).replace(/,/g, "");
    const m2 = t.match(/(\d+(?:\.\d+)?)\s*(?:m2|m²|㎡|平米|平方メートル)/i);
    if (m2) return Number(m2[1]);
    const tsubo = t.match(/(\d+(?:\.\d+)?)\s*坪/);
    return tsubo ? Number(tsubo[1]) / TSUBO_PER_M2 : null;
  }

  // 「5.05%」「5.05％」→ 0.0505
  function parsePercent(s) {
    const m = toHalf(s).match(/(\d+(?:\.\d+)?)\s*%/);
    return m ? Number(m[1]) / 100 : null;
  }

  // 敷金・礼金は「14万円」のほか「1ヶ月」「1ヵ月」(賃料の何ヶ月分)や「-」「なし」で書かれる
  function parseMonthsOrYen(s, rent) {
    const t = toHalf(s).trim();
    if (!t || /^[-ー―]$|なし|無し/.test(t)) return 0;
    const months = t.match(/(\d+(?:\.\d+)?)\s*[ヶヵかカケ箇]?\s*月/);
    if (months && !/円/.test(t)) return rent != null ? Math.round(Number(months[1]) * rent) : null;
    return parseYen(t);
  }

  // 元利均等返済の毎月返済額
  function monthlyPayment(principal, annualRate, years) {
    const n = years * 12;
    const r = annualRate / 12;
    if (r === 0) return principal / n;
    return (principal * r) / (1 - (1 + r) ** -n);
  }

  // fields: content.js がページから集めた { 項目名: 本文 }(項目名は下の KEYS のどれか)
  // options: { loanRate, loanYears }(購入時の返済試算の条件)
  function analyze(fields, options = {}) {
    const { loanRate = 0.01, loanYears = 35 } = options;
    const f = (k) => fields[k] ?? null;
    const area = f("area") != null ? parseArea(f("area")) : null;
    const tsubo = area != null ? area * TSUBO_PER_M2 : null;
    const assumptions = [];

    // --- 賃貸 ---
    const rent = f("rent") != null ? parseYen(f("rent")) : null;
    if (rent != null && rent > 0 && rent < 10_000_000) {
      const fee = f("fee") != null ? (parseYen(f("fee")) ?? 0) : 0;
      const monthly = rent + fee;
      // 「14万円 / 14万円」のように敷金・礼金がまとめて書かれることが多い
      let deposit = null;
      let keyMoney = null;
      if (f("depositKey") != null) {
        const [d, k] = toHalf(f("depositKey")).split(/[/／]/);
        deposit = parseMonthsOrYen(d, rent);
        keyMoney = k != null ? parseMonthsOrYen(k, rent) : null;
      }
      if (f("deposit") != null) deposit = parseMonthsOrYen(f("deposit"), rent);
      if (f("keyMoney") != null) keyMoney = parseMonthsOrYen(f("keyMoney"), rent);

      // 初期費用の最低限の目安: 敷金+礼金+仲介手数料(賃料1ヶ月+税)+前家賃1ヶ月
      let initialCost = null;
      if (deposit != null && keyMoney != null) {
        initialCost = Math.round(deposit + keyMoney + rent * 1.1 + monthly);
        assumptions.push("仲介手数料は賃料1ヶ月分+税、前家賃1ヶ月分で計算");
      }
      return {
        kind: "rent",
        rent,
        fee,
        monthly,
        area,
        perM2: area ? Math.round(monthly / area) : null,
        perTsubo: tsubo ? Math.round(monthly / tsubo) : null,
        deposit,
        keyMoney,
        initialCost,
        assumptions,
      };
    }

    // --- 売買(投資物件を含む) ---
    const price = f("price") != null ? parseYen(f("price")) : null;
    if (price == null || price < 1_000_000) return null;

    // 管理費・修繕積立金は別欄のことも「6,000円 / 8,870円」のようにまとめて書かれることもある
    let fee = null;
    let repair = null;
    if (f("feeRepair") != null) {
      const [a, b] = toHalf(f("feeRepair")).split(/[/／]/);
      fee = parseYen(a);
      repair = b != null ? parseYen(b) : null;
    }
    if (f("fee") != null) fee = parseYen(f("fee"));
    if (f("repair") != null) repair = parseYen(f("repair"));
    const runningMonthly = (fee ?? 0) + (repair ?? 0);

    const payment = Math.round(monthlyPayment(price, loanRate, loanYears));
    assumptions.push(
      `全額を金利${Math.round(loanRate * 10000) / 100}%・${loanYears}年の元利均等で借りた場合`,
    );

    // 利回り: 年間収入があれば表面利回りを計算、利回りしか無ければ年間収入を逆算
    let grossYield = f("yield") != null ? parsePercent(f("yield")) : null;
    let annualIncome = f("income") != null ? parseYen(f("income")) : null;
    if (annualIncome != null && grossYield == null) grossYield = annualIncome / price;
    if (grossYield != null && annualIncome == null) annualIncome = Math.round(price * grossYield);
    // 簡易の実質利回り: (年間収入 - 管理費・修繕積立金×12) ÷ 価格。固定資産税・空室等は含まない
    const netYield =
      annualIncome != null && runningMonthly > 0
        ? (annualIncome - runningMonthly * 12) / price
        : null;

    return {
      kind: "sale",
      price,
      area,
      perM2: area ? Math.round(price / area) : null,
      perTsubo: tsubo ? Math.round(price / tsubo) : null,
      fee,
      repair,
      loanPayment: payment,
      monthlyTotal: payment + runningMonthly,
      grossYield,
      annualIncome,
      netYield,
      assumptions,
    };
  }

  globalThis.RealtyParser = { parseYen, parseArea, parsePercent, monthlyPayment, analyze };
})();
