import type { Element, Rarity, Role, Skill, Stats } from "../core/types";

/** 立ち絵SVGの髪型 */
export type HairStyle =
  | "longSide" // 片側に流した長髪
  | "hime" // 姫カット
  | "hoodShort" // 短髪＋フード
  | "wildLong" // ぼさぼさの長髪
  | "bunBells" // お団子＋簪
  | "short" // 短髪
  | "scarfLow" // 襟巻で口元を隠す
  | "ponytail" // ポニーテール
  | "sideTail" // サイドテール
  | "twinTail" // ツインテール
  | "bob" // おかっぱ
  | "highTail" // 高い位置の結い上げ
  | "fluffy" // ふわふわ
  | "hairpinBob"; // 前髪ぱっつんのボブ

/** 立ち絵SVGの武器形状 */
export type WeaponShape =
  | "twinKatana"
  | "naginata"
  | "caneSword"
  | "towerShield"
  | "kaguraBell"
  | "odachi"
  | "kunai"
  | "twinShields"
  | "crossSpear"
  | "bow"
  | "bokken"
  | "pinwheel"
  | "staff"
  | "lantern";

/** 紋（モチーフ）の種類 */
export type MotifKey =
  | "sakura"
  | "snow"
  | "gear"
  | "onigawara"
  | "lotus"
  | "flameScale"
  | "newMoon"
  | "crane"
  | "maple"
  | "bonfire"
  | "snowRabbit"
  | "aoi"
  | "yuzu"
  | "foxMask";

export interface Relation {
  id: string;
  label: string;
}

export interface CharacterDef {
  id: string;
  family: string; // 姓（無い場合は空文字）
  given: string; // 名
  kana: string;
  epithet: string; // 二つ名
  rarity: Rarity;
  element: Element;
  role: Role;
  school: string; // 流派
  age: string; // 年齢感
  personality: string;
  firstPerson: string; // 一人称
  toneSample: string; // 口調サンプル
  color: string; // テーマカラー
  colorSub: string;
  motif: MotifKey;
  motifText: string;
  weapon: string;
  weaponShape: WeaponShape;
  hair: HairStyle;
  likes: string;
  dislikes: string;
  profile: string;
  relations: Relation[];
  skill: Skill;
  /** 役割・レア由来の基礎値に掛ける個別補正（省略時1） */
  statMod?: Partial<Stats>;
  /** 本番イラストが入ったら差し替える */
  imageUrl?: string;
}

export function fullName(c: CharacterDef): string {
  return c.family ? `${c.family} ${c.given}` : c.given;
}

export const CHARACTERS: CharacterDef[] = [
  {
    id: "hisame",
    family: "紅葉",
    given: "緋雨",
    kana: "もみじ ひさめ",
    epithet: "血桜の剣客",
    rarity: "UR",
    element: "fire",
    role: "atk",
    school: "散華二刀流",
    age: "17歳ほど",
    personality: "普段は穏やかで甘党。追い詰められるほど笑みが深くなる。",
    firstPerson: "わたし",
    toneSample: "ふふ、まだ斬り足りませんね。お団子はそのあとにしましょう？",
    color: "#c8283c",
    colorSub: "#f2a7b4",
    motif: "sakura",
    motifText: "散り桜・赤い組紐",
    weapon: "二刀「夕霧」「朝露」",
    weaponShape: "twinKatana",
    hair: "longSide",
    likes: "みたらし団子、夜桜",
    dislikes: "苦い薬、約束を破る人",
    profile:
      "散華二刀流の免許皆伝。片側だけ長い袖に赤い組紐を結び、桜の散る中で舞うように斬る。普段は茶屋めぐりが趣味の穏やかな娘だが、劣勢になるほど楽しげに笑う癖があり、味方からも少し怖がられている。",
    relations: [
      { id: "yae", label: "勝手にライバル視されている" },
      { id: "koyuki", label: "剣の手ほどきをしている" },
    ],
    skill: {
      name: "緋時雨",
      desc: "HP割合の最も低い敵に2連撃（攻撃力140%×2）。80%で出血（2合）。",
      effects: [
        { kind: "damage", target: "lowestHp", mult: 1.4, hits: 2, status: { type: "bleed", chance: 0.8, turns: 2, power: 0.3 } },
      ],
    },
    statMod: { atk: 1.08, spd: 1.06 },
  },
  {
    id: "rin",
    family: "白峰",
    given: "凛",
    kana: "しらみね りん",
    epithet: "氷華の薙刀",
    rarity: "UR",
    element: "water",
    role: "mag",
    school: "白峰流薙刀術",
    age: "18歳ほど",
    personality: "名家の令嬢。冷静沈着で毒舌だが、誰より仲間を見ている。",
    firstPerson: "わたくし",
    toneSample: "その程度で剣華を名乗るおつもり？ ……怪我は、ありませんわね。",
    color: "#7cc4e4",
    colorSub: "#e8f6fc",
    motif: "snow",
    motifText: "雪の結晶",
    weapon: "白銀の薙刀「六花」",
    weaponShape: "naginata",
    hair: "hime",
    likes: "静かな雪の朝、詰将棋",
    dislikes: "騒がしい場所、甘すぎる菓子",
    profile:
      "北の名門・白峰家の跡取り。水色の羽織と白銀の薙刀で、冷気をまとう術を操る。口は悪いが面倒見がよく、幼なじみのしずくが転ぶたびに手を差し伸べている。",
    relations: [
      { id: "shizuku", label: "幼なじみ" },
      { id: "yae", label: "うるさいと思っている" },
    ],
    skill: {
      name: "六花繚乱",
      desc: "敵全体に攻撃力110%。35%で凍結（1合）。",
      effects: [{ kind: "damage", target: "all", mult: 1.1, status: { type: "freeze", chance: 0.35, turns: 1 } }],
    },
  },
  {
    id: "yasha",
    family: "鴉丸",
    given: "夜叉",
    kana: "からすまる やしゃ",
    epithet: "絡繰の剣鬼",
    rarity: "UR",
    element: "wind",
    role: "atk",
    school: "鴉丸絡繰剣",
    age: "16歳ほど",
    personality: "無口な絡繰技師。機械いじりの話になると急に饒舌になる。",
    firstPerson: "ボク",
    toneSample: "……用件だけ。あ、その歯車？ それはね、三段変速の逆止め機構で——",
    color: "#4a5d8a",
    colorSub: "#c9a24a",
    motif: "gear",
    motifText: "歯車・鴉の羽",
    weapon: "仕込み刀「黒羽」",
    weaponShape: "caneSword",
    hair: "hoodShort",
    likes: "油の匂い、分解できるもの",
    dislikes: "雨（錆びる）、大声",
    profile:
      "片目に拡大レンズを付けた絡繰技師。自作の仕込み刀は刃の角度を戦闘中に組み替えられる。人と話すのは苦手だが、壊れた物を見ると黙っていられない。",
    relations: [
      { id: "tomoe", label: "盾の修理を任されている" },
      { id: "saku", label: "気配のなさに一目置いている" },
    ],
    skill: {
      name: "鴉羽落とし",
      desc: "後列の敵1体に攻撃力260%。50%で目眩（1合）。",
      effects: [{ kind: "damage", target: "back", mult: 2.6, status: { type: "stun", chance: 0.5, turns: 1 } }],
    },
    statMod: { spd: 1.08 },
  },
  {
    id: "tomoe",
    family: "鉄心",
    given: "巴",
    kana: "てっしん ともえ",
    epithet: "不動の大盾",
    rarity: "UR",
    element: "rock",
    role: "def",
    school: "鉄心不動流",
    age: "20歳ほど",
    personality: "豪快な姉御肌。とにかくよく食べ、よく笑う。",
    firstPerson: "あたい",
    toneSample: "あたいの後ろにいな！ ……で、晩飯はまだかい？",
    color: "#8a6a3c",
    colorSub: "#d9b26a",
    motif: "onigawara",
    motifText: "鬼瓦の紋・注連縄",
    weapon: "鉄扉の大盾「門守」",
    weaponShape: "towerShield",
    hair: "wildLong",
    likes: "大盛りの飯、力比べ",
    dislikes: "空腹、細かい計算",
    profile:
      "城門の鉄扉をそのまま盾にしたと噂される怪力娘。注連縄を肩に掛け、鬼瓦の紋を背負う。仲間の前に立つことを何よりの誇りにしている。",
    relations: [
      { id: "yasha", label: "盾の整備を頼んでいる" },
      { id: "yuzu", label: "門番仲間として可愛がっている" },
    ],
    skill: {
      name: "不動鉄扉",
      desc: "味方全体に最大HP18%の盾（2合）。前列の敵に攻撃力100%、60%で攻撃低下（2合）。",
      effects: [
        { kind: "shield", target: "allAllies", ratio: 0.18, turns: 2 },
        { kind: "damage", target: "front", mult: 1.0, status: { type: "atkDown", chance: 0.6, turns: 2 } },
      ],
    },
  },
  {
    id: "shizuku",
    family: "蓮華",
    given: "しずく",
    kana: "れんげ しずく",
    epithet: "慈雨の巫女",
    rarity: "UR",
    element: "water",
    role: "heal",
    school: "蓮華神楽",
    age: "17歳ほど",
    personality: "おっとりした巫女。天然で、何もない所でもよく転ぶ。",
    firstPerson: "しずく",
    toneSample: "えへへ、しずくが治してあげますね〜。……あっ、わわっ！",
    color: "#e48fb4",
    colorSub: "#bfe3d8",
    motif: "lotus",
    motifText: "蓮の花・雨粒の簪",
    weapon: "神楽鈴「露払」",
    weaponShape: "kaguraBell",
    hair: "bunBells",
    likes: "雨音、お昼寝",
    dislikes: "急な坂道、雷",
    profile:
      "雨乞いの神楽を受け継ぐ蓮華神社の巫女。鈴を鳴らすと癒やしの雨が降る。転んでも泣かない根性の持ち主。凛とは物心つく前からの幼なじみ。",
    relations: [
      { id: "rin", label: "幼なじみ（りんちゃん）" },
      { id: "akari", label: "夜道で一緒に震えている" },
    ],
    skill: {
      name: "慈雨神楽",
      desc: "味方全体を攻撃力180%分回復。",
      effects: [{ kind: "heal", target: "allAllies", mult: 1.8 }],
    },
  },
  {
    id: "yae",
    family: "焔",
    given: "八重",
    kana: "ほむら やえ",
    epithet: "紅蓮の大太刀",
    rarity: "UR",
    element: "fire",
    role: "mag",
    school: "焔一刀流",
    age: "17歳ほど",
    personality: "熱血で負けず嫌い。緋雨を一方的にライバル視している。",
    firstPerson: "オレ",
    toneSample: "勝負だ緋雨！ ……え、団子食ってから？ じゃあオレも食う！",
    color: "#e8601c",
    colorSub: "#ffd27a",
    motif: "flameScale",
    motifText: "炎の鱗模様",
    weapon: "身の丈ほどの大太刀「火喰」",
    weaponShape: "odachi",
    hair: "short",
    likes: "勝負、辛いもの",
    dislikes: "引き分け、じっと待つこと",
    profile:
      "身の丈ほどの大太刀を振り回す焔一刀流の若き師範代。炎の鱗模様の羽織がトレードマーク。緋雨に一度負けて以来、毎日のように勝負を挑んでいる（戦績は非公開）。",
    relations: [
      { id: "hisame", label: "ライバル（自称）" },
      { id: "hibari", label: "早朝稽古の相棒" },
    ],
    skill: {
      name: "焔車",
      desc: "敵全体に攻撃力130%。70%で火傷（2合）。",
      effects: [{ kind: "damage", target: "all", mult: 1.3, status: { type: "burn", chance: 0.7, turns: 2, power: 0.35 } }],
    },
  },
  {
    id: "saku",
    family: "霞",
    given: "朔",
    kana: "かすみ さく",
    epithet: "影縫いの忍",
    rarity: "SSR",
    element: "wind",
    role: "atk",
    school: "霞隠れ",
    age: "15歳ほど",
    personality: "気配が薄すぎて、点呼でよく忘れられる。本人は少し気にしている。",
    firstPerson: "朔",
    toneSample: "……朔は、ずっとここにいました。",
    color: "#3a3550",
    colorSub: "#9c94c4",
    motif: "newMoon",
    motifText: "新月・黒い襟巻",
    weapon: "苦無",
    weaponShape: "kunai",
    hair: "scarfLow",
    likes: "新月の夜、狭い所",
    dislikes: "点呼",
    profile: "霞隠れの里の忍。黒い襟巻で口元を隠し、影を縫い留める術で敵の動きを封じる。",
    relations: [{ id: "yasha", label: "唯一すぐ気づいてくれる" }],
    skill: {
      name: "影縫い",
      desc: "後列の敵1体に攻撃力220%。40%で目眩（1合）。",
      effects: [{ kind: "damage", target: "back", mult: 2.2, status: { type: "stun", chance: 0.4, turns: 1 } }],
    },
    statMod: { spd: 1.12 },
  },
  {
    id: "chizuru",
    family: "岩代",
    given: "千鶴",
    kana: "いわしろ ちづる",
    epithet: "鶴翼の守り手",
    rarity: "SSR",
    element: "rock",
    role: "def",
    school: "岩代鶴翼流",
    age: "16歳ほど",
    personality: "礼儀正しい委員長気質。規律と整列を愛する。",
    firstPerson: "私",
    toneSample: "皆さん、隊列を崩さないでください。私が守ります。",
    color: "#6c7a5a",
    colorSub: "#e9e4d4",
    motif: "crane",
    motifText: "折り鶴",
    weapon: "両翼の双盾",
    weaponShape: "twinShields",
    hair: "ponytail",
    likes: "折り紙、時間厳守",
    dislikes: "遅刻",
    profile: "両腕に翼のような双盾を構える守りの要。暇さえあれば折り鶴を折り、千羽目で願いが叶うと信じている。",
    relations: [{ id: "aoi", label: "せっかちさに手を焼いている" }],
    skill: {
      name: "鶴翼の陣",
      desc: "味方全体に最大HP14%の盾（2合）。",
      effects: [{ kind: "shield", target: "allAllies", ratio: 0.14, turns: 2 }],
    },
  },
  {
    id: "kaede",
    family: "水無月",
    given: "楓",
    kana: "みなづき かえで",
    epithet: "流水の槍",
    rarity: "SSR",
    element: "water",
    role: "atk",
    school: "流水槍術",
    age: "18歳ほど",
    personality: "旅好きで方言まじり。どこへ行っても土産を買ってくる。",
    firstPerson: "うち",
    toneSample: "うち、次はあっちの山越えたいんよ。一緒に行かん？",
    color: "#2f8f9d",
    colorSub: "#e07a3c",
    motif: "maple",
    motifText: "紅葉と流水紋",
    weapon: "十文字槍",
    weaponShape: "crossSpear",
    hair: "sideTail",
    likes: "旅、温泉、土産選び",
    dislikes: "同じ場所に長くいること",
    profile: "八洲を旅して回る槍使い。流れる水のような足さばきで二度突く。",
    relations: [{ id: "hibari", label: "旅先の話をよく聞かせる" }],
    skill: {
      name: "流水十文字",
      desc: "前列の敵に攻撃力130%×2。",
      effects: [{ kind: "damage", target: "front", mult: 1.3, hits: 2 }],
    },
  },
  {
    id: "hibari",
    family: "篝",
    given: "ひばり",
    kana: "かがり ひばり",
    epithet: "火矢の射手",
    rarity: "SSR",
    element: "fire",
    role: "mag",
    school: "篝弓術",
    age: "15歳ほど",
    personality: "元気いっぱいの見張り番。誰より早く起きる。",
    firstPerson: "ひばり",
    toneSample: "おっはよーございまーす！ 今日も空がよく見えるよ！",
    color: "#f0a03c",
    colorSub: "#7a3c1e",
    motif: "bonfire",
    motifText: "篝火・雲雀の羽根",
    weapon: "和弓「明星」",
    weaponShape: "bow",
    hair: "twinTail",
    likes: "朝焼け、高い所",
    dislikes: "夜更かし",
    profile: "櫓の見張り番を務める弓の名手。雲雀の羽根を矢羽に使い、火矢を雨のように降らせる。",
    relations: [{ id: "yae", label: "早朝稽古で叩き起こしている" }],
    skill: {
      name: "暁の火矢",
      desc: "敵全体に攻撃力95%。50%で火傷（2合）。",
      effects: [{ kind: "damage", target: "all", mult: 0.95, status: { type: "burn", chance: 0.5, turns: 2, power: 0.25 } }],
    },
  },
  {
    id: "koyuki",
    family: "",
    given: "小雪",
    kana: "こゆき",
    epithet: "見習い剣士",
    rarity: "SR",
    element: "water",
    role: "atk",
    school: "（散華二刀流 見習い）",
    age: "13歳ほど",
    personality: "頑張り屋の新入り。何でもメモを取る。",
    firstPerson: "わたし",
    toneSample: "は、はいっ！ 小雪、全力でがんばりますっ！",
    color: "#a8c8e8",
    colorSub: "#ffffff",
    motif: "snowRabbit",
    motifText: "小さな雪うさぎ",
    weapon: "木刀",
    weaponShape: "bokken",
    hair: "bob",
    likes: "雪うさぎ作り、緋雨先輩",
    dislikes: "失敗（でもめげない）",
    profile: "緋雨に憧れて入門した見習い。まだ真剣は持たせてもらえないが、木刀の素振りは誰より多い。",
    relations: [{ id: "hisame", label: "憧れの先輩" }],
    skill: {
      name: "雪うさぎ斬り",
      desc: "前列の敵に攻撃力180%。20%で凍結（1合）。",
      effects: [{ kind: "damage", target: "front", mult: 1.8, status: { type: "freeze", chance: 0.2, turns: 1 } }],
    },
  },
  {
    id: "aoi",
    family: "疾風",
    given: "葵",
    kana: "はやて あおい",
    epithet: "韋駄天",
    rarity: "SR",
    element: "wind",
    role: "atk",
    school: "飛脚走法",
    age: "15歳ほど",
    personality: "せっかちな飛脚出身。話も足も速い。",
    firstPerson: "あたし",
    toneSample: "はいはい急いで！ あたしもう三往復したよ！",
    color: "#3c9c6c",
    colorSub: "#f2e08a",
    motif: "aoi",
    motifText: "葵の紋・風車",
    weapon: "風車の手裏剣",
    weaponShape: "pinwheel",
    hair: "highTail",
    likes: "駆けっこ、早飯",
    dislikes: "待ち時間",
    profile: "城下一の飛脚だった少女。草鞋を履き潰す速さで戦場を駆け、弱った敵を逃さない。",
    relations: [{ id: "chizuru", label: "よく「走らない！」と怒られる" }],
    skill: {
      name: "韋駄天二段",
      desc: "HP割合の最も低い敵に攻撃力100%×2。",
      effects: [{ kind: "damage", target: "lowestHp", mult: 1.0, hits: 2 }],
    },
    statMod: { spd: 1.15 },
  },
  {
    id: "yuzu",
    family: "石動",
    given: "柚",
    kana: "いするぎ ゆず",
    epithet: "石垣番",
    rarity: "SR",
    element: "rock",
    role: "def",
    school: "石垣棒術",
    age: "16歳ほど",
    personality: "のんびり屋の門番。立ったまま寝られる。",
    firstPerson: "ゆず",
    toneSample: "ふわぁ……ゆず、ちゃんと起きてるよぉ……",
    color: "#d8b83c",
    colorSub: "#6c6a5c",
    motif: "yuzu",
    motifText: "柚子・石垣模様",
    weapon: "六尺棒",
    weaponShape: "staff",
    hair: "fluffy",
    likes: "日向ぼっこ、柚子湯",
    dislikes: "早起き",
    profile: "城の石垣を守る門番。のんびりしているが、棒術の構えは石垣のように崩れない。",
    relations: [{ id: "tomoe", label: "姉さんと慕っている" }],
    skill: {
      name: "石垣固め",
      desc: "自身に最大HP30%の盾（2合）。前列の敵に攻撃力80%、50%で攻撃低下（2合）。",
      effects: [
        { kind: "shield", target: "self", ratio: 0.3, turns: 2 },
        { kind: "damage", target: "front", mult: 0.8, status: { type: "atkDown", chance: 0.5, turns: 2 } },
      ],
    },
  },
  {
    id: "akari",
    family: "",
    given: "灯",
    kana: "あかり",
    epithet: "提灯持ち",
    rarity: "SR",
    element: "fire",
    role: "mag",
    school: "狐火術",
    age: "14歳ほど",
    personality: "怖がりなのに夜道担当。狐面をかぶると少しだけ強気になる。",
    firstPerson: "あかり",
    toneSample: "ひっ……！ な、なんでもないです。あかり、照らしますね……",
    color: "#e8823c",
    colorSub: "#f6efe0",
    motif: "foxMask",
    motifText: "提灯・狐面",
    weapon: "狐火の提灯",
    weaponShape: "lantern",
    hair: "hairpinBob",
    likes: "明るい部屋、油揚げ",
    dislikes: "暗闇、怪談",
    profile: "提灯に狐火を灯して夜道を照らす役目の少女。狐面は「怖い顔を見ないため」につけている。",
    relations: [{ id: "shizuku", label: "一緒にいると落ち着く" }],
    skill: {
      name: "狐火灯籠",
      desc: "敵全体に攻撃力80%。40%で火傷（2合）。",
      effects: [{ kind: "damage", target: "all", mult: 0.8, status: { type: "burn", chance: 0.4, turns: 2, power: 0.2 } }],
    },
  },
];

export const CHAR_BY_ID: Record<string, CharacterDef> = Object.fromEntries(CHARACTERS.map((c) => [c.id, c]));

/** 新規データの初期所持キャラ */
export const STARTER_IDS = ["koyuki", "aoi", "yuzu", "akari", "chizuru"];
