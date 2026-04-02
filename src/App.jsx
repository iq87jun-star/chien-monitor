import { useState, useEffect, useRef } from "react";

const T = {
  primary:      "#1A56DB",
  primaryLight: "#EEF3FF",
  surface:      "#FFFFFF",
  surfaceVar:   "#F4F6FB",
  outline:      "#E2E8F0",
  onSurface:    "#0F172A",
  onSurfaceMed: "#475569",
  onSurfaceLow: "#94A3B8",
  normal:  { bg:"#ECFDF5", text:"#059669", border:"#A7F3D0", badge:"#D1FAE5" },
  delay:   { bg:"#FFFBEB", text:"#D97706", border:"#FDE68A", badge:"#FEF3C7" },
  stop:    { bg:"#FFF1F2", text:"#E11D48", border:"#FECDD3", badge:"#FFE4E6" },
  unknown: { bg:"#F8FAFC", text:"#64748B", border:"#E2E8F0", badge:"#F1F5F9" },
  shadow:   "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.05)",
  shadowMd: "0 2px 8px rgba(0,0,0,0.09), 0 8px 24px rgba(0,0,0,0.07)",
  r: { sm:"8px", md:"14px", lg:"18px", xl:"24px", full:"999px" },
};

const STATUS = {
  normal:  { label:"平常運転",     emoji:"✅", color: T.normal  },
  delay:   { label:"遅　延",       emoji:"⚠️", color: T.delay   },
  stop:    { label:"運転見合わせ", emoji:"🚫", color: T.stop    },
  unknown: { label:"情報なし",     emoji:"❓", color: T.unknown },
};

const AGENTS = [
  { id:"official", label:"公式情報",    icon:"🏢", accent:"#1A56DB",
    prompt: l=>`「${l}」の現在の運行状況を公式サイトやYahoo!乗換案内で調べてください。` },
  { id:"news",     label:"ニュース",     icon:"📰", accent:"#7C3AED",
    prompt: l=>`「${l}」の遅延・運休に関する最新ニュースを調べてください。` },
  { id:"realtime", label:"リアルタイム", icon:"📡", accent:"#0891B2",
    prompt: l=>`「${l}」の今この瞬間の遅延状況を最新情報で調べてください。` },
  { id:"related",  label:"接続路線",     icon:"🔗", accent:"#DC2626",
    prompt: l=>`「${l}」と接続する路線への遅延波及影響を調べてください。` },
];

const SYSTEM_PROMPT = `あなたは日本の鉄道遅延情報を収集する専門エージェントです。
ウェブ検索で最新の運行情報を調べて、必ず以下のJSON形式だけで回答してください。余分なテキスト不要。
{
  "status": "normal"|"delay"|"stop"|"unknown",
  "delayMinutes": 数値またはnull,
  "affectedSection": "影響区間またはnull",
  "cause": "原因またはnull",
  "detail": "1〜3文の詳細説明",
