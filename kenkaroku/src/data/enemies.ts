import type { Element, Role, Skill, Stats } from "../core/types";

export interface EnemyDef {
  id: string;
  name: string;
  glyph: string; // 仮素材で表示する一文字
  element: Element;
  role: Role;
  /** 特徴文（図鑑・戦闘時の説明） */
  desc: string;
  /** 役割由来の基礎値に掛ける補正 */
  statMod?: Partial<Stats>;
  skill: Skill;
  boss?: boolean;
}

export const ENEMIES: EnemyDef[] = [
  {
    id: "kooni",
    name: "小鬼",
    glyph: "鬼",
    element: "rock",
    role: "atk",
    desc: "群れで動く小さな鬼。一匹なら子どもでも追い払えるが、十匹いると話が変わる。",
    statMod: { hp: 0.8, atk: 0.85 },
    skill: { name: "棍棒乱打", desc: "前列に攻撃力150%。", effects: [{ kind: "damage", target: "front", mult: 1.5 }] },
  },
  {
    id: "akaoni",
    name: "赤鬼",
    glyph: "赤",
    element: "fire",
    role: "atk",
    desc: "怒ると全身が燃えるように赤くなる鬼。たいてい怒っている。",
    skill: {
      name: "怒髪金棒",
      desc: "前列に攻撃力180%、30%で火傷。",
      effects: [{ kind: "damage", target: "front", mult: 1.8, status: { type: "burn", chance: 0.3, turns: 2, power: 0.25 } }],
    },
  },
  {
    id: "aooni",
    name: "青鬼",
    glyph: "青",
    element: "water",
    role: "def",
    desc: "赤鬼の相方。冷静で、相方が暴れたあとの後始末をしている。",
    skill: { name: "鉄皮", desc: "自身に盾。", effects: [{ kind: "shield", target: "self", ratio: 0.25, turns: 2 }] },
  },
  {
    id: "kappa",
    name: "河童",
    glyph: "河",
    element: "water",
    role: "atk",
    desc: "川辺で相撲を挑んでくる妖。頭の皿が乾くと急に弱気になる。",
    skill: {
      name: "尻子玉抜き",
      desc: "後列に攻撃力160%、25%で目眩。",
      effects: [{ kind: "damage", target: "back", mult: 1.6, status: { type: "stun", chance: 0.25, turns: 1 } }],
    },
  },
  {
    id: "kamaitachi",
    name: "鎌鼬",
    glyph: "鼬",
    element: "wind",
    role: "atk",
    desc: "つむじ風に乗って現れる三匹組。斬られた者は痛みに気づくのが遅れる。",
    statMod: { spd: 1.2, hp: 0.85 },
    skill: {
      name: "旋風三連",
      desc: "HP割合の低い敵に攻撃力70%×3、50%で出血。",
      effects: [{ kind: "damage", target: "lowestHp", mult: 0.7, hits: 3, status: { type: "bleed", chance: 0.5, turns: 2, power: 0.2 } }],
    },
  },
  {
    id: "tengu",
    name: "天狗",
    glyph: "天",
    element: "wind",
    role: "mag",
    desc: "山に棲む高慢な妖。団扇の一振りで嵐を呼ぶが、鼻を褒めると機嫌がよくなる。",
    skill: { name: "羽団扇", desc: "全体に攻撃力100%。", effects: [{ kind: "damage", target: "all", mult: 1.0 }] },
  },
  {
    id: "tsuchigumo",
    name: "土蜘蛛",
    glyph: "蜘",
    element: "rock",
    role: "def",
    desc: "古い洞窟に巣を張る大蜘蛛。糸に絡まれると足が石のように重くなる。",
    statMod: { hp: 1.2 },
    skill: {
      name: "岩糸縛り",
      desc: "前列に攻撃力110%、40%で目眩。",
      effects: [{ kind: "damage", target: "front", mult: 1.1, status: { type: "stun", chance: 0.4, turns: 1 } }],
    },
  },
  {
    id: "hitotsume",
    name: "一つ目入道",
    glyph: "目",
    element: "rock",
    role: "atk",
    desc: "見上げるほどの巨体に大きな一つ目。目が合うと動けなくなるという。",
    statMod: { hp: 1.25, spd: 0.85 },
    skill: {
      name: "睨み据え",
      desc: "前列に攻撃力200%、40%で攻撃低下。",
      effects: [{ kind: "damage", target: "front", mult: 2.0, status: { type: "atkDown", chance: 0.4, turns: 2 } }],
    },
  },
  {
    id: "kasha",
    name: "火車",
    glyph: "車",
    element: "fire",
    role: "mag",
    desc: "燃える車輪を引く猫の妖。葬列を狙って現れ、炎で道をふさぐ。",
    skill: {
      name: "業火輪",
      desc: "全体に攻撃力90%、50%で火傷。",
      effects: [{ kind: "damage", target: "all", mult: 0.9, status: { type: "burn", chance: 0.5, turns: 2, power: 0.25 } }],
    },
  },
  {
    id: "yukinba",
    name: "雪婆",
    glyph: "雪",
    element: "water",
    role: "mag",
    desc: "吹雪の夜に戸を叩く老婆の妖。応えると家ごと凍らされる。",
    skill: {
      name: "吹雪",
      desc: "全体に攻撃力80%、25%で凍結。",
      effects: [{ kind: "damage", target: "all", mult: 0.8, status: { type: "freeze", chance: 0.25, turns: 1 } }],
    },
  },
  {
    id: "gashamusha",
    name: "骸武者",
    glyph: "骸",
    element: "rock",
    role: "def",
    desc: "古戦場で討ち死にした武者の骨が、鎧ごと立ち上がったもの。",
    statMod: { def: 1.3 },
    skill: {
      name: "亡者の構え",
      desc: "味方全体に盾。",
      effects: [{ kind: "shield", target: "allAllies", ratio: 0.12, turns: 2 }],
    },
  },
  {
    id: "omukade",
    name: "大百足",
    glyph: "百",
    element: "fire",
    role: "atk",
    desc: "山を七巻き半するという巨大な百足。毒の牙は鉄をも溶かす。",
    statMod: { hp: 1.3, atk: 1.1 },
    skill: {
      name: "百足牙",
      desc: "HP割合の低い敵に攻撃力220%、60%で出血。",
      effects: [{ kind: "damage", target: "lowestHp", mult: 2.2, status: { type: "bleed", chance: 0.6, turns: 2, power: 0.3 } }],
    },
  },
  {
    id: "ibaraki",
    name: "茨木",
    glyph: "茨",
    element: "wind",
    role: "atk",
    desc: "酒呑に仕える鬼の副将。失った片腕の代わりに茨の義手を振るう。",
    statMod: { hp: 2.2, atk: 1.25 },
    boss: true,
    skill: {
      name: "茨の大爪",
      desc: "後列に攻撃力220%、50%で出血。",
      effects: [{ kind: "damage", target: "back", mult: 2.2, status: { type: "bleed", chance: 0.5, turns: 2, power: 0.3 } }],
    },
  },
  {
    id: "shuten",
    name: "酒呑",
    glyph: "酒",
    element: "fire",
    role: "mag",
    desc: "鬼の首魁。大盃を傾けるたびに、八洲のどこかで鬼火が上がる。",
    statMod: { hp: 3.2, atk: 1.35 },
    boss: true,
    skill: {
      name: "百鬼夜宴",
      desc: "全体に攻撃力140%、60%で火傷。",
      effects: [{ kind: "damage", target: "all", mult: 1.4, status: { type: "burn", chance: 0.6, turns: 2, power: 0.35 } }],
    },
  },
];

export const ENEMY_BY_ID: Record<string, EnemyDef> = Object.fromEntries(ENEMIES.map((e) => [e.id, e]));
