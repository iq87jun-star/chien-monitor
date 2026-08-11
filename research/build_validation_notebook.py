# -*- coding: utf-8 -*-
"""build_validation_notebook.py
v4(H4順張り)検証を1ファイルで完結させる .ipynb を生成する。
外部依存(あなたのColabノート内関数)を一切持たず、data/*_h1.csv だけで
上から実行すれば全結果が出る。核心は「+8% halt の生存バイアス」検証。
"""
import nbformat as nbf
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

nb = new_notebook()
cells = []
def md(s):  cells.append(new_markdown_cell(s))
def code(s):cells.append(new_code_cell(s))

# ---------------------------------------------------------------- 0. 表紙
md(r"""# FundedNext v4 (H4順張り) 検証 — 自己完結ノート

このノートは **外部依存なしで単体実行できる** v4 戦略検証ハーネスです。

### 🚀 本番(Dukascopy 10年)の使い方 — これだけ
1. Google Drive に好きな名前のフォルダを作り、H1 データを入れる
   （**`.parquet` も `.csv` も対応**。例: `マイドライブ/fundednext_data/EURJPY_1h_10y.parquet ...`）。
2. **0.5セル**の `DRIVE_SUBDIR` をそのフォルダ名にして実行 → 認証許可。
3. 「すべてのセルを実行」。第1章のバナーが **緑(✅ years≈10)** なら本番判定。

> Driveにデータが無い/Colab以外なら、`data` フォルダ → 無ければ **Yahoo 2.8年を自動取得**
> （研究用フォールバック。この場合バナーは赤で「本番判定にならない」と警告）。
> CSVファイル名は **ペア名を含めばOK**（`USDJPY_Candlestick_1_Hour_BID_...csv` 等）。
> **列名(Open/High/Low/Close, bid/ask接頭辞)と時刻形式(`dd.mm.yyyy HH:MM:SS.000` 等)は自動判別**
> します。既存CSVがあれば自動取得はスキップされます。

## このノートが答える問い
v3(D1逆張り)は不採用。手元データで「同じ4条件を**順張り(符号反転)**で読む」と
OOSで芽が出た。これは本物のエッジか? それとも見かけか?

## ⚠ 最重要の発見 — `+8% halt` の生存バイアス
FundedNext Phase1 は「+8%到達で合格・終了」。これをそのままバックテストの
**停止条件**にすると、**負け戦略ですら勝って見える**。実測（手元USDJPY 4089シグナル）:

| 条件 | リターン | 真のMaxDD | 使用トレード |
|---|---|---|---|
| halt-ON (+8%で停止) | **+8.37%** | **−0.40%** | わずか **26** |
| halt-OFF (連続) | **−10.51%** | **−49.79%** | 全 **4089** |

同じ戦略・同じデータで、停止するか否かだけで優等生↔大惨事に反転する。
→ **equity系の合格(baseline/WF/HoldOut)は halt-ON だと信用できない。**
本ノートは halt-ON と **halt-OFF(連続)** を必ず並べて出し、生存バイアスを排除する。

## 構成
1. 設定 / データ読込
2. シグナル生成（4条件・順張り反転）
3. バックテスト核（halt フラグ付き）
4. **halt-ON vs halt-OFF 比較**（核心）
5. 全ペア・全期間ベースライン
6. Hold-Out 75/25 (OOS)
7. 年次ウォークフォワード
8. 順列検定（halt 非依存・順序非依存のエッジ検定）
9. **総合合否ゲート**

> 研究用。最終判断は実 bid/ask ハーネスとフォワード/デモで再確認すること。
""")

# ---------------------------------------------------------------- 0.5 Driveマウント
md("## 0.5 Google Drive マウント（Dukascopy 10年データ用）\n\n"
   "**ここだけ設定すれば本番データで動きます。** 手順:\n"
   "1. 下の `DRIVE_SUBDIR` を、Drive上でCSVを入れたフォルダ名に書き換える。\n"
   "2. このセルを実行 → 認証を許可。\n\n"
   "CSVファイル名はペア名(USDJPY等)を含めば何でもOK。列名・時刻形式は自動判別。\n\n"
   "> Colab以外(ローカル/Jupyter)で動かす場合はこのセルは自動でスキップされ、"
   "次セルの `DATA_DIR` 既定値('data')か環境変数が使われます。")
code(r"""# ★★ ここを自分のDriveフォルダ名に変更 ★★
# 例: マイドライブ直下に 'fundednext_data' を作ってCSVを入れたなら下記のまま。
DRIVE_SUBDIR = "fundednext_data"     # MyDrive/<ここ> にCSVを置く

DRIVE_DATA_DIR = None
try:
    from google.colab import drive   # Colabでのみ成功
    drive.mount('/content/drive')
    DRIVE_DATA_DIR = f"/content/drive/MyDrive/{DRIVE_SUBDIR}"
    import os as _os
    if _os.path.isdir(DRIVE_DATA_DIR):
        _n=len([f for f in _os.listdir(DRIVE_DATA_DIR) if f.lower().endswith('.csv')])
        print(f"✅ Driveマウント成功: {DRIVE_DATA_DIR}  (CSV {_n}個)")
        if _n==0:
            print("   ⚠ このフォルダにCSVがありません。Drive上のフォルダ名/中身を確認してください。")
    else:
        print(f"⚠ フォルダが見つかりません: {DRIVE_DATA_DIR}")
        print("   Drive内に '"+DRIVE_SUBDIR+"' フォルダを作りCSVを入れるか、DRIVE_SUBDIRを修正。")
        print("   マウント直後はDrive反映に数秒かかることがあります(再実行で解決する場合あり)。")
except Exception as e:
    print("Colab環境ではないためDriveマウントはスキップ:", type(e).__name__)
    print("→ 次セルの DATA_DIR(既定 'data' または環境変数) を使います。")
""")

# ---------------------------------------------------------------- 1. 設定
md("## 1. 設定 / データ読込\n\n"
   "`DATA_DIR` の決定順: ①0.5でDriveにCSVが見つかればそれ → ②環境変数 DATA_DIR → "
   "③既定 'data'(無ければYahoo 2.8年を自動取得=研究用)。")
code(r"""import os, math, numpy as np, pandas as pd
import matplotlib.pyplot as plt
import warnings
# np.datetime64 のタイムゾーン警告で出力が埋まるのを防ぐ(結果に影響なし)
warnings.filterwarnings("ignore", message="no explicit representation of timezones")
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- データ場所の決定 (Drive優先) ---
# DRIVE_DATA_DIR は 0.5セルで設定済み(Colab時)。それが実在すれば最優先。
_drive = globals().get("DRIVE_DATA_DIR")
if _drive and os.path.isdir(_drive):
    DATA_DIR = _drive
else:
    DATA_DIR = os.environ.get("DATA_DIR", "data")
OUT_DIR  = os.environ.get("OUT_DIR", ".")
os.makedirs(OUT_DIR, exist_ok=True)
print("使用 DATA_DIR =", os.path.abspath(DATA_DIR))

PAIRS = ["USDJPY","EURJPY","GBPJPY","USDCHF","GBPUSD","EURUSD","AUDUSD","NZDUSD","USDCAD"]

# --- 戦略 + FundedNext ルール パラメータ ---
P = dict(
    # シグナル
    Momentum      = True,    # True=順張り(条件を反転) / False=逆張り(=v3移植)
    VotesRequired = 3,       # 4条件中いくつ一致で発注(K)
    RsiPeriod=14, RsiBuyLevel=35.0, RsiSellLevel=65.0,
    BBPeriod=20, BBZThreshold=1.5,
    StreakDays=3, RetThreshold=0.0025,
    AtrPeriod=14, AtrSLMult=1.5, RR=1.2,
    HoldH4Bars=12,           # 保有 = H4 × 12 (=48h)
    MinStopPips=6.0, MaxStopPips=250.0,
    # コスト
    SpreadMult=1.0, SlipPips=0.2,
    # 資金 / FundedNext
    InitialBalance=100_000.0,
    RiskPerTradePct=0.4,     # 1トレードのリスク% of balance
    ProfitTargetPct=8.0,     # Phase1 利益目標
    EquityFloorDDPct=10.0,   # 総合DD失格ライン
    DailyStopPct=5.0,        # 日次DD失格ライン
    MaxTradesPerDay=3, MaxDailyRiskPct=1.2,
    MinLot=0.01, MaxSpreadPips=3.0,
)
print("設定OK  Momentum =", P["Momentum"], " K =", P["VotesRequired"])
""")

code(r"""import glob, re
def pip_size(pair): return 0.01 if pair.endswith("JPY") else 0.0001

# 列名のゆらぎを吸収するマップ(小文字化して照合)
_COLMAP = {
    "open":["open","o","bidopen","openbid","open_bid","askopen"],
    "high":["high","h","bidhigh","highbid","high_bid","askhigh"],
    "low": ["low","l","bidlow","lowbid","low_bid","asklow"],
    "close":["close","c","bidclose","closebid","close_bid","askclose","price"],
}
_TIMECOLS = ["timestamp","time","datetime","date","gmt time","gmttime",
             "local time","localtime","date time"]

def _find_file(pair):
    # DATA_DIR から pair に対応するデータファイルを柔軟に探す。
    # 対応: .parquet / .csv。<PAIR>_h1.* を最優先、無ければペア名を含む任意ファイル。
    for ext in (".parquet",".csv"):
        exact=os.path.join(DATA_DIR,f"{pair}_h1{ext}")
        if os.path.exists(exact): return exact
    cands=[]
    for ext in ("*.parquet","*.csv"):
        for f in glob.glob(os.path.join(DATA_DIR,ext)):
            base=os.path.basename(f).upper()
            if pair.upper() in base.replace("/",""):
                cands.append(f)
    if not cands:
        return os.path.join(DATA_DIR,f"{pair}_h1.csv")  # 存在しないパス→上位でエラー扱い
    # parquetを優先、次にH1/60min/1_Hour 表記を優先
    pq=[f for f in cands if f.lower().endswith(".parquet")]
    pool=pq or cands
    h1=[f for f in pool if re.search(r"(_H1|1_?H|1_HOUR|60M|HOURLY|H1|_1H)", os.path.basename(f).upper())]
    return (h1 or pool)[0]

def _pick(cols_lower, candidates):
    for c in candidates:
        if c in cols_lower: return cols_lower[c]
    return None

def load_h1(pair):
    # Dukascopy / Yahoo / 汎用の CSV・Parquet を自動判別して H1 OHLC(UTC, tz-naive) を返す。
    #  - 形式: .parquet と .csv の両対応
    #  - 時刻: 専用列(timestamp等) または index(DatetimeIndex) を自動検出
    #  - 列名: Open/High/Low/Close の大小・bid/ask接頭辞を吸収
    path=_find_file(pair)
    if path.lower().endswith(".parquet"):
        df=pd.read_parquet(path)
    else:
        df=pd.read_csv(path)
    # 時刻がindexに入っている形式(Parquetで多い)を先に処理
    idx_is_time = isinstance(df.index, pd.DatetimeIndex) or \
                  (df.index.name and str(df.index.name).lower() in _TIMECOLS)
    if idx_is_time:
        df=df.reset_index()
    cols_lower={str(c).strip().lower():c for c in df.columns}
    # 時刻列
    tcol=_pick(cols_lower,_TIMECOLS)
    if tcol is None: tcol=df.columns[0]    # 先頭列を時刻とみなす
    s=df[tcol]
    if pd.api.types.is_datetime64_any_dtype(s):
        t=pd.to_datetime(s, utc=True, errors="coerce")
    else:
        s=s.astype(str).str.strip()
        # Dukascopy 'dd.mm.yyyy HH:MM:SS.000' を明示的に試す→ダメなら汎用
        t=pd.to_datetime(s, format="%d.%m.%Y %H:%M:%S.%f", errors="coerce", utc=True)
        if t.isna().mean()>0.5:
            t=pd.to_datetime(s, format="%d.%m.%Y %H:%M:%S", errors="coerce", utc=True)
        if t.isna().mean()>0.5:
            t=pd.to_datetime(s, errors="coerce", utc=True, format="mixed")
    df["__t"]=t
    # OHLC列
    o=_pick(cols_lower,_COLMAP["open"]); h=_pick(cols_lower,_COLMAP["high"])
    l=_pick(cols_lower,_COLMAP["low"]);  c=_pick(cols_lower,_COLMAP["close"])
    miss=[k for k,v in dict(open=o,high=h,low=l,close=c).items() if v is None]
    if miss:
        raise ValueError(f"{os.path.basename(path)}: 列が見つかりません {miss} / 実際の列={list(df.columns)}")
    out=df[["__t",o,h,l,c]].copy()
    out.columns=["time","open","high","low","close"]
    out=out.dropna(subset=["time"])
    # UTCのままtz情報だけ外す(値は不変)。これで np.searchsorted の tz警告を根絶。
    out["time"]=out["time"].dt.tz_localize(None)
    out=out.set_index("time").sort_index()
    out=out[~out.index.duplicated(keep="first")]
    return out[["open","high","low","close"]].astype(float)

def resample_h4(h1):
    o=h1["open"].resample("4h",label="left",closed="left").first()
    h=h1["high"].resample("4h",label="left",closed="left").max()
    l=h1["low"].resample("4h",label="left",closed="left").min()
    c=h1["close"].resample("4h",label="left",closed="left").last()
    h4=pd.concat([o,h,l,c],axis=1); h4.columns=["open","high","low","close"]
    return h4.dropna()

# --- データ自動取得フォールバック ---------------------------------------
# DATA_DIR に <PAIR>_h1.csv が無ければ Yahoo Finance から取得してキャッシュ。
# これで「Colabで開いて実行するだけ」で必ず動く。Dukascopy 10年を使う場合は
# その CSV を DATA_DIR に置けば、こちらは取得をスキップする(既存ファイル優先)。
def ensure_data(pairs=PAIRS, data_dir=DATA_DIR):
    import urllib.request, json, csv, time as _t, datetime as _dt
    os.makedirs(data_dir, exist_ok=True)
    ymap={"EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X","AUDUSD":"AUDUSD=X",
          "USDCHF":"USDCHF=X","USDCAD":"USDCAD=X","NZDUSD":"NZDUSD=X",
          "EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X"}
    for p in pairs:
        path=os.path.join(data_dir,f"{p}_h1.csv")
        if os.path.exists(path):                      # 既存(=Dukascopy等)優先
            continue
        sym=ymap.get(p)
        if not sym:
            print(f"[{p}] Yahooシンボル未定義→スキップ"); continue
        try:
            u=(f"https://query2.finance.yahoo.com/v8/finance/chart/{sym}"
               f"?interval=1h&period1=1704067200&period2=1767225599")
            req=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0"})
            d=json.loads(urllib.request.urlopen(req,timeout=25).read())
            r=d["chart"]["result"][0]; ts=r["timestamp"]; q=r["indicators"]["quote"][0]
            rows=[]
            for i,t in enumerate(ts):
                o,h,l,c=q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                if None in (o,h,l,c): continue
                rows.append((_dt.datetime.fromtimestamp(t, _dt.timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S"),o,h,l,c))
            with open(path,"w",newline="") as f:
                w=csv.writer(f); w.writerow(["timestamp","open","high","low","close"]); w.writerows(rows)
            print(f"[{p}] Yahoo取得 {len(rows)}本 -> {path}")
            _t.sleep(0.8)
        except Exception as e:
            print(f"[{p}] 取得失敗(ネット制限?): {type(e).__name__} {str(e)[:50]}")

# 既存CSVが1つも無ければ自動取得を試みる(Dukascopy等を置いていればスキップ)
# _find_file はロングファイル名(USDJPY_Candlestick_..._BID_...csv 等)も拾う
_have=[p for p in PAIRS if os.path.exists(_find_file(p))]
if not _have:
    print("DATA_DIR にCSV無し → Yahooから自動取得を試行(研究用2年データ)...")
    print("※ 本番は Dukascopy 10年CSV を", DATA_DIR, "に置いて再実行してください。")
    print("  (ファイル名は <PAIR>を含めばOK。例 USDJPY_*.csv / 列名・時刻形式は自動判別)")
    ensure_data()
else:
    print(f"既存CSV {len(_have)} ペアを検出:", _have)

# データ点検
_rows=[]
for p in PAIRS:
    try:
        h1=load_h1(p); h4=resample_h4(h1)
        _rows.append(dict(pair=p, h1_bars=len(h1), h4_bars=len(h4),
            start=str(h1.index.min().date()), end=str(h1.index.max().date()),
            years=round((h1.index.max()-h1.index.min()).days/365.25,2)))
    except Exception as e:
        _rows.append(dict(pair=p, h1_bars=0, note=str(e)[:50]))
AVAIL = [r["pair"] for r in _rows if r.get("h1_bars",0)>0]
display(pd.DataFrame(_rows))
print("利用可能ペア:", AVAIL)

# データ年数チェック: 2年前後なら「Yahooサンプル」=本番ではない、と大きく警告
_yrs=[r["years"] for r in _rows if r.get("years")]
_maxyr=max(_yrs) if _yrs else 0
print("\n" + "="*64)
if _maxyr < 5:
    print("🔴 注意: 読み込んだデータは最長", _maxyr, "年です。")
    print("   これは Yahoo の研究用サンプル(約2.8年)とみられます。")
    print("   → 当初の強い結果(順列p≈0 等)は Dukascopy 10年/2016-20 由来。")
    print("     本番判定にはなりません。")
    print("   【対処】Dukascopy 10年の H1 CSV を下記フォルダに置いて再実行:")
    print("        DATA_DIR =", os.path.abspath(DATA_DIR))
    print("     Colabなら左の📁から data/ にアップロード、または Drive をマウントして")
    print("     第1章の DATA_DIR をそのパスに変更。既存CSVがあれば自動取得はスキップ。")
else:
    print("✅ データ年数 OK (最長", _maxyr, "年)。本番判定として読めます。")
print("="*64)
if not AVAIL:
    print("\n⚠ データが1つもありません。ネット制限の場合は手動でCSVを DATA_DIR に置いて再実行。")
""")

# ---------------------------------------------------------------- 2. シグナル
md("## 2. シグナル生成（4条件の票集計）\n\n"
   "RSI・ボリンジャーZ・連続足・リターン閾値の4票。`K`票以上で発注。"
   "`Momentum=True` で符号を反転（逆張り条件→順張り/トレンド継続として読む）。")
code(r"""def _rsi_wilder(close, n):
    d=close.diff(); up=d.clip(lower=0.0); dn=(-d).clip(lower=0.0)
    ru=up.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    rd=dn.ewm(alpha=1/n,adjust=False,min_periods=n).mean()
    return 100-100/(1+ru/rd.replace(0,np.nan))

def _atr_wilder(df, n):
    h,l,c=df["high"],df["low"],df["close"]; pc=c.shift(1)
    tr=pd.concat([(h-l),(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False,min_periods=n).mean()

def compute_signals(h4, P):
    c=h4["close"]
    rsi=_rsi_wilder(c,P["RsiPeriod"])
    n=P["BBPeriod"]
    mean=c.shift(1).rolling(n).mean(); std=c.shift(1).rolling(n).std(ddof=1)
    z=(c-mean)/std
    down=(c<c.shift(1)).astype(int); up=(c>c.shift(1)).astype(int)
    def streak(flag):
        s=[]; run=0
        for v in flag.values:
            run=run+1 if v==1 else 0; s.append(run)
        return pd.Series(s,index=flag.index)
    ds=streak(down); us=streak(up); ret=c.pct_change()
    bv=((rsi<P["RsiBuyLevel"]).astype(int)+(z<-P["BBZThreshold"]).astype(int)
        +(ds>=P["StreakDays"]).astype(int)+(ret<-P["RetThreshold"]).astype(int))
    sv=((rsi>P["RsiSellLevel"]).astype(int)+(z>P["BBZThreshold"]).astype(int)
        +(us>=P["StreakDays"]).astype(int)+(ret>P["RetThreshold"]).astype(int))
    K=P["VotesRequired"]
    sig=pd.Series(0,index=c.index,dtype=int)
    sig[(bv>=K)&(bv>sv)]=1
    sig[(sv>=K)&(sv>bv)]=-1
    if P.get("Momentum"): sig=-sig
    return pd.DataFrame({"signal":sig,"atr":_atr_wilder(h4,P["AtrPeriod"])})
""")

# ---------------------------------------------------------------- 3. バックテスト核
md("## 3. バックテスト核（halt フラグ付き）\n\n"
   "H4確定足[1]でシグナル→翌H4始値で約定→H1足でイントラバーSL/TP/時間切れ判定"
   "（同足はSL優先=保守）。`halt_on_target`/`halt_on_floor` で +8%停止・DD失格停止を"
   "切替える。これが本ノートの肝。\n\n"
   "戻り値はトレード明細 `tdf` と連続equity曲線 `eqdf`。"
   "**真のMaxDDは halt-OFF の eqdf からのみ求まる。**")
code(r"""def run_backtest(pair, h1, h4, P, halt_on_target=True, halt_on_floor=True):
    pip=pip_size(pair)
    sg=compute_signals(h4,P)
    spread=pip*P["SpreadMult"]; slip=pip*P["SlipPips"]
    t1=h1.index.values
    o1=h1["open"].values; h1h=h1["high"].values; l1=h1["low"].values; c1=h1["close"].values
    idx=list(sg.index); sigv=sg["signal"].values; atrv=sg["atr"].values

    equity=P["InitialBalance"]; trades=[]; eq_curve=[]
    cur_day=None; day_start_eq=equity; trades_today=0; risk_used=0.0
    day_blocked=False; halted=False
    floor_eq=P["InitialBalance"]*(1-P["EquityFloorDDPct"]/100.0)
    target_eq=P["InitialBalance"]*(1+P["ProfitTargetPct"]/100.0)
    risk_usd=P["InitialBalance"]*P["RiskPerTradePct"]/100.0  # 1Rの$リスク(初期残高基準=定額)

    for i in range(len(idx)-1):
        t_next=idx[i+1]; s=sigv[i]; atr=atrv[i]
        d=t_next.date()
        if cur_day!=d:
            cur_day=d; day_start_eq=equity; trades_today=0; risk_used=0.0; day_blocked=False
        if halt_on_floor and equity<=floor_eq: halted=True
        if halted: break
        if halt_on_target and equity>=target_eq: break
        if s==0 or not (atr==atr) or atr<=0: continue
        if day_blocked: continue
        if trades_today>=P["MaxTradesPerDay"]: continue
        if risk_used+P["RiskPerTradePct"]>P["MaxDailyRiskPct"]+1e-9: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip<P["MinStopPips"] or sd/pip>P["MaxStopPips"]: continue
        a=int(np.searchsorted(t1,np.datetime64(t_next),side="left"))
        if a>=len(t1): break
        mid=o1[a]
        if s>0: entry=mid+spread/2+slip; sl=entry-sd; tp=entry+P["RR"]*sd
        else:   entry=mid-spread/2-slip; sl=entry+sd; tp=entry-P["RR"]*sd
        until=t_next+np.timedelta64(P["HoldH4Bars"]*4,"h")
        b=int(np.searchsorted(t1,np.datetime64(until),side="right")); b=max(b,a+1)
        hh=h1h[a:b]; ll=l1[a:b]; cc=c1[a:b]; R=None; off=len(hh)-1
        for k in range(len(hh)):
            if s>0: hit_sl=ll[k]<=sl; hit_tp=hh[k]>=tp
            else:   hit_sl=hh[k]>=sl; hit_tp=ll[k]<=tp
            if hit_sl: R=-1.0; off=k; break
            if hit_tp: R=P["RR"]; off=k; break
        if R is None:
            last=cc[-1] if len(cc) else entry
            diff=(last-entry) if s>0 else (entry-last)
            R=diff/sd; off=len(hh)-1
        pnl=R*risk_usd
        equity+=pnl; trades_today+=1; risk_used+=P["RiskPerTradePct"]
        ent_time=pd.Timestamp(t1[a]); ex_i=min(a+off,len(t1)-1)
        exit_time=pd.Timestamp(t1[ex_i])
        eq_curve.append((exit_time,equity))
        trades.append(dict(pair=pair,sig=int(s),ent_time=ent_time,exit_time=exit_time,
            reason=("SL" if R<0 else "TP" if R>=P["RR"] else "TIME"),
            stop_pips=sd/pip,pnl=pnl,equity=equity,rmultiple=R))
        if equity-day_start_eq <= -P["InitialBalance"]*P["DailyStopPct"]/100.0:
            day_blocked=True
    tdf=pd.DataFrame(trades)
    eqdf=pd.DataFrame(eq_curve,columns=["time","equity"]).set_index("time")
    return tdf, eqdf

def wilson_lower(w,n,z=1.96):
    if n==0: return float("nan")
    p=w/n; den=1+z*z/n; c=p+z*z/(2*n)
    adj=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)
    return (c-adj)/den

def evaluate(tdf, eqdf, P, label=""):
    n=len(tdf)
    if n==0: return dict(label=label,n=0)
    R=tdf["rmultiple"].values; pnl=tdf["pnl"].values
    gp=R[R>0].sum(); gl=-R[R<0].sum(); pf=gp/gl if gl>0 else float("inf")
    w=int((R>0).sum()); wr=w/n; be=1.0/(1.0+P["RR"])
    wlo=wilson_lower(w,n)
    span=max((tdf["ent_time"].max()-tdf["ent_time"].min()).days,1)
    eq=eqdf["equity"]; peak=eq.cummax(); dd=((eq-peak)/peak*100.0)
    maxdd=float(dd.min()) if len(dd) else 0.0
    total_pct=(eq.iloc[-1]/P["InitialBalance"]-1)*100 if len(eq) else 0.0
    yrs=span/365.25
    cagr=((eq.iloc[-1]/P["InitialBalance"])**(1/yrs)-1)*100 if (len(eq) and yrs>0 and eq.iloc[-1]>0) else float("nan")
    mx=run=0
    for v in pnl:
        run=run+1 if v<0 else 0; mx=max(mx,run)
    sharpe=(R.mean()/R.std()*np.sqrt(len(R))) if R.std()>0 else float("nan")
    return dict(label=label,n=n,trades_per_year=round(n/yrs,1),
        wr=round(wr*100,1), be=round(be*100,1), wilson_lo=round(wlo*100,1),
        wilson_gt_BE=bool(wlo>be), PF=round(pf,2), exp_R=round(R.mean(),3),
        total_pct=round(total_pct,2), CAGR_pct=round(cagr,2),
        maxDD_pct=round(maxdd,2), max_consec_loss=mx, sharpe=round(sharpe,2))
""")

# ---------------------------------------------------------------- 4. halt 比較(核心)
md("## 4. 🔴 halt-ON vs halt-OFF 比較（このノートの核心）\n\n"
   "各ペアで **+8%停止あり** と **停止なし(10年連続)** を並べる。\n"
   "- `halt-ON` の `final_pct` が約8%で頭打ち・MaxDDが極小なら、それは生存バイアス。\n"
   "- `halt-OFF` の `total_pct` がプラス・`trueMaxDD` が −10%以内なら、エッジは本物。\n"
   "- `halt-OFF` が大きくマイナス・`trueMaxDD` が −30%超なら、+8%合格は**見かけ**。")
code(r"""def halt_compare(pairs=None):
    pairs = pairs or AVAIL
    rows=[]; eqs_off={}
    for pair in pairs:
        try:
            h1=load_h1(pair); h4=resample_h4(h1)
            t_on, e_on  = run_backtest(pair,h1,h4,P,halt_on_target=True, halt_on_floor=True)
            t_off,e_off = run_backtest(pair,h1,h4,P,halt_on_target=False,halt_on_floor=False)
            ev_on = evaluate(t_on, e_on, P,f"{pair} ON")
            ev_off= evaluate(t_off,e_off,P,f"{pair} OFF")
            eqs_off[pair]=e_off
            rows.append(dict(pair=pair,
                ON_n=ev_on.get("n",0), ON_final_pct=ev_on.get("total_pct"),
                ON_maxDD=ev_on.get("maxDD_pct"),
                OFF_n=ev_off.get("n",0), OFF_total_pct=ev_off.get("total_pct"),
                OFF_CAGR=ev_off.get("CAGR_pct"), OFF_trueMaxDD=ev_off.get("maxDD_pct"),
                OFF_consecL=ev_off.get("max_consec_loss"),
                OFF_breach10=bool((ev_off.get("maxDD_pct") or 0) <= -10.0),
                verdict=("本物?" if (ev_off.get("total_pct",0)>0 and (ev_off.get("maxDD_pct") or -99)>-10)
                         else "見かけ(halt生存)")))
        except Exception as e:
            rows.append(dict(pair=pair, verdict=f"err:{str(e)[:40]}"))
    return pd.DataFrame(rows), eqs_off

cmp_df, eqs_off = halt_compare()
display(cmp_df)

# 連続equity曲線(halt-OFF)
fig,ax=plt.subplots(figsize=(11,5))
for pair,e in eqs_off.items():
    if len(e): ax.plot(e.index, e["equity"].values, lw=1, label=pair)
ax.axhline(P["InitialBalance"],color="k",lw=0.6,ls="--")
ax.axhline(P["InitialBalance"]*(1-P["EquityFloorDDPct"]/100),color="r",lw=0.6,ls=":",label="-10% fail line")
ax.set_title("halt-OFF continuous equity (true picture)"); ax.set_ylabel("equity USD")
ax.legend(fontsize=8,ncol=2); ax.grid(alpha=0.3)
plt.tight_layout(); plt.savefig(os.path.join(OUT_DIR,"halt_off_equity.png"),dpi=110); plt.show()
print("\n読み: OFF_total_pct>0 かつ OFF_trueMaxDD>-10% のペアだけが、+8%合格の裏に")
print("      本物のエッジを持つ。多くが見かけなら v4 は採用不可。")
""")

# ---------------------------------------------------------------- 5. ベースライン
md("## 5. 全ペア・全期間ベースライン（halt-OFF=正味の実力）\n\n"
   "PF・取引/年・勝率・Wilson下限・期待Rを halt-OFF（連続）で評価。"
   "これが「+8%で止めずに回し続けた素の戦略性能」。")
code(r"""base_rows=[]
for pair in AVAIL:
    try:
        h1=load_h1(pair); h4=resample_h4(h1)
        tdf,eqdf=run_backtest(pair,h1,h4,P,halt_on_target=False,halt_on_floor=False)
        ev=evaluate(tdf,eqdf,P,pair)
        base_rows.append(ev)
    except Exception as e:
        base_rows.append(dict(label=pair,n=-1))
baseline=pd.DataFrame(base_rows)
cols=["label","n","trades_per_year","wr","be","wilson_lo","wilson_gt_BE",
      "PF","exp_R","total_pct","CAGR_pct","maxDD_pct","max_consec_loss","sharpe"]
display(baseline[[c for c in cols if c in baseline.columns]])
""")

# ---------------------------------------------------------------- 6. Hold-Out
md("## 6. Hold-Out 75/25（直近25%を伏せてOOS）\n\n"
   "前75%でエッジを確認、後25%(未見)で再現するか。OOSもhalt-OFFで評価。\n"
   "合格目安: **OOS PF>1.1 かつ OOS_n≥30 かつ OOS Wilson下限>BE**。")
code(r"""ho_rows=[]
for pair in AVAIL:
    try:
        h1=load_h1(pair); h4=resample_h4(h1)
        cut=h4.index[int(len(h4)*0.75)]
        h4i,h4o=h4[h4.index<=cut],h4[h4.index>cut]
        h1i=h1[h1.index<=cut]; h1o=h1[h1.index>(cut-pd.Timedelta(days=10))]
        ti,ei=run_backtest(pair,h1i,h4i,P,halt_on_target=False,halt_on_floor=False)
        to,eo=run_backtest(pair,h1o,h4o,P,halt_on_target=False,halt_on_floor=False)
        evi=evaluate(ti,ei,P,"IS"); evo=evaluate(to,eo,P,"OOS")
        ho_rows.append(dict(pair=pair,cut=str(cut.date()),
            IS_n=evi.get("n",0),IS_PF=evi.get("PF"),IS_pct=evi.get("total_pct"),
            OOS_n=evo.get("n",0),OOS_PF=evo.get("PF"),OOS_pct=evo.get("total_pct"),
            OOS_wlo=evo.get("wilson_lo"),OOS_gtBE=evo.get("wilson_gt_BE"),
            OOS_maxDD=evo.get("maxDD_pct")))
    except Exception as e:
        ho_rows.append(dict(pair=pair,IS_n=-1))
holdout=pd.DataFrame(ho_rows); display(holdout)
print("合格目安: OOS_PF>1.1 & OOS_n>=30 & OOS_gtBE==True")
""")

# ---------------------------------------------------------------- 7. 年次WF
md("## 7. 年次ウォークフォワード（特定年に依存していないか）\n\n"
   "各暦年だけで回し、プラス年が大半か。1年だけで稼いでいたら脆い。")
code(r"""def yearly_wf(pair, P):
    h1=load_h1(pair); h4=resample_h4(h1); rows=[]
    for y in sorted(set(h4.index.year)):
        h4y=h4[h4.index.year==y]
        if len(h4y)<200: continue
        h1y=h1[(h1.index.year>=y)&(h1.index<=h4y.index.max()+pd.Timedelta(days=5))]
        t,e=run_backtest(pair,h1y,h4y,P,halt_on_target=False,halt_on_floor=False)
        ev=evaluate(t,e,P,str(y))
        rows.append(dict(year=y,n=ev.get("n",0),PF=ev.get("PF"),
            pct=ev.get("total_pct"),maxDD=ev.get("maxDD_pct"),wr=ev.get("wr")))
    return pd.DataFrame(rows)

wf_pos={}
for pair in AVAIL[:3]:
    try:
        wf=yearly_wf(pair,P)
        print(f"\n===== {pair} 年次WF =====")
        display(wf)
        if len(wf):
            pos=int((wf["pct"]>0).sum()); wf_pos[pair]=(pos,len(wf))
            print(f"  プラス年 {pos}/{len(wf)}  年平均件数={wf['n'].mean():.0f}")
    except Exception as e:
        print(f"[{pair}] WFスキップ:", e)
""")

# ---------------------------------------------------------------- 8. 順列検定
md("## 8. 順列検定（halt 非依存・順序非依存のエッジ検定）\n\n"
   "実トレードのR合計が、「同数・同方向比でランダムなH4足にエントリーした」"
   "帰無分布の上位何%か。**halt とも順序とも無関係**なので、生存バイアスに"
   "汚染されない唯一の指標。`emp_p<0.05` なら方向選択に有意なエッジ。\n\n"
   "ただし順列検定はR**合計**を見るだけで**順序を見ない**ため、"
   "「途中で−10%に触れて失格」は検出できない。だから第4章の連続曲線と併読する。")
code(r"""def permutation_test(pair, P, n_iter=2000, seed=20260531):
    h1=load_h1(pair); h4=resample_h4(h1)
    sg=compute_signals(h4,P); pip=pip_size(pair)
    spread=pip*P["SpreadMult"]; slip=pip*P["SlipPips"]
    t1=h1.index.values; o1=h1["open"].values
    h1h=h1["high"].values; l1=h1["low"].values; c1=h1["close"].values
    idx=list(sg.index); sigv=sg["signal"].values; atrv=sg["atr"].values

    def one_R(s, a, sd):
        if s>0: entry=o1[a]+spread/2+slip; sl=entry-sd; tp=entry+P["RR"]*sd
        else:   entry=o1[a]-spread/2-slip; sl=entry+sd; tp=entry-P["RR"]*sd
        until=t1[a]+np.timedelta64(P["HoldH4Bars"]*4,"h")
        b=int(np.searchsorted(t1,until,side="right")); b=max(b,a+1)
        hh=h1h[a:b]; ll=l1[a:b]; cc=c1[a:b]
        for k in range(len(hh)):
            if s>0: hsl=ll[k]<=sl; htp=hh[k]>=tp
            else:   hsl=hh[k]>=sl; htp=ll[k]<=tp
            if hsl: return -1.0
            if htp: return P["RR"]
        last=cc[-1] if len(cc) else entry
        return ((last-entry) if s>0 else (entry-last))/sd

    Rb=[]; Rs=[]; sigs=[]
    for i in range(len(idx)-1):
        atr=atrv[i]
        if not (atr==atr) or atr<=0: continue
        sd=P["AtrSLMult"]*atr
        if sd/pip<P["MinStopPips"] or sd/pip>P["MaxStopPips"]: continue
        a=int(np.searchsorted(t1,np.datetime64(idx[i+1]),side="left"))
        if a>=len(t1): continue
        Rb.append(one_R(+1,a,sd)); Rs.append(one_R(-1,a,sd)); sigs.append(sigv[i])
    Rb=np.array(Rb); Rs=np.array(Rs); sigs=np.array(sigs)
    real=np.where(sigs!=0)[0]; n=len(real)
    if n<5: return dict(pair=pair,n=int(n),note="件数<5")
    dirs=sigs[real]
    realR=float(np.where(dirs>0,Rb[real],Rs[real]).sum())
    n_buy=int((dirs>0).sum()); M=len(Rb)
    rng=np.random.default_rng(seed); null=np.empty(n_iter)
    base=np.array([1]*n_buy+[-1]*(n-n_buy))
    for it in range(n_iter):
        pick=rng.choice(M,size=min(n,M),replace=False)
        dd=base.copy(); rng.shuffle(dd)
        null[it]=np.where(dd[:len(pick)]>0,Rb[pick],Rs[pick]).sum()
    p=float((null>=realR).mean())
    return dict(pair=pair,n=int(n),real_totalR=round(realR,2),
        null_mean=round(float(null.mean()),2),
        null_p95=round(float(np.percentile(null,95)),2),
        emp_p=round(p,4), significant=bool(p<0.05),
        edge_per_trade=round(realR/n,3))

perm_rows=[]
for pair in AVAIL[:3]:
    try:
        r=permutation_test(pair,P,n_iter=2000); perm_rows.append(r); print(pair, r)
    except Exception as e:
        print(f"[{pair}] 順列スキップ:", e)
""")

# ---------------------------------------------------------------- 9. 合否ゲート
md("## 9. 総合合否ゲート\n\n"
   "**halt-OFF を基準にした厳格判定**。全条件を満たせば v4 EA 実装へ。"
   "1つでも欠ければ見送り（生存バイアスに騙されない）。")
code(r"""def decide():
    print("="*64); print("v4 合否ゲート (halt-OFF 基準)"); print("="*64)
    chk={}
    # 1) halt-OFF でプラス かつ trueMaxDD>-10% のペア
    if 'cmp_df' in globals() and len(cmp_df):
        ok=cmp_df[(cmp_df.get("OFF_total_pct",0)>0) & (cmp_df.get("OFF_trueMaxDD",-99)>-10)]
        chk["A. halt-OFFで純益+ & trueMaxDD>-10%"]=(len(ok),len(cmp_df))
    # 2) OOS PF>1.1 & n>=30 & Wilson>BE
    if 'holdout' in globals() and len(holdout):
        h=holdout[(holdout["OOS_PF"]>1.1)&(holdout["OOS_n"]>=30)&(holdout["OOS_gtBE"]==True)]
        chk["B. OOS PF>1.1 & n>=30 & Wilson>BE"]=(len(h),len(holdout))
    # 3) 順列検定 有意
    if perm_rows:
        sig=[r for r in perm_rows if r.get("significant")]
        chk["C. 順列検定 p<0.05"]=(len(sig),len(perm_rows))
    # 4) 年次WF プラス年が過半
    if wf_pos:
        good=[k for k,(p,t) in wf_pos.items() if t and p/t>=0.6]
        chk["D. 年次WF プラス年>=60%"]=(len(good),len(wf_pos))
    passed=0
    for k,(a,b) in chk.items():
        half=max(1,int(0.5*b)); ok=a>=half; passed+=ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {k}: {a}/{b}")
    print("-"*64)
    go = passed==len(chk) and len(chk)>=3
    print("判定:", "✅ v4 EA実装に進んでよい" if go else "❌ 見送り(優位性の確証不足)")
    print("  ※ 研究判定。実運用前にフォワード/デモで再確認。特に第4章 halt-OFF を重視。")
decide()
""")

nb["cells"]=cells
nb["metadata"]={"kernelspec":{"display_name":"Python 3","language":"python","name":"python3"},
                "language_info":{"name":"python","version":"3.x"}}
out="research/FundedNext_v4_validation_SELFCONTAINED.ipynb"
with open(out,"w",encoding="utf-8") as f:
    nbf.write(nb,f)
print("wrote", out, "cells=",len(cells))
