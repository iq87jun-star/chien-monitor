#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_gcal_ics.py — 3戦略EAのタイミングを Googleカレンダー用 .ics に出力。

Googleカレンダー → 設定 → インポート/エクスポート → 「インポート」で chien_ea_schedule.ics を取込む。
タイムゾーンは Asia/Tokyo(JST=UTC+9・DSTなし)。v7はUTC定刻なのでJSTでも年中固定。

入る予定:
  ・v7 ENTRY: 毎週 月曜 JST 13:00/15:00/17:00/19:00 (=UTC 4/6/8/10) … 円クロスLONGの定刻
  ・v7 EXIT : 毎週 火曜 同時刻 (24h時間決済の目安)
  ・v4 判定 : 平日 毎日 JST 06:30 頃 (日足確定後・条件成立時のみ建玉。時刻は業者サーバ時刻で±1h)
  ・E5 判定 : 毎月 1日 JST 06:30 頃 (月初・方向転換時のみ建玉)
各予定に開始5分前のポップアップ通知(VALARM)を付与。
"""
import os, datetime as dt

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "calendar")
os.makedirs(OUT, exist_ok=True)
PATH = os.path.join(OUT, "chien_ea_schedule.ics")

# v7定刻の起点となる「最初の月曜」(2026-06以降)
base = dt.date(2026,6,1)
while base.weekday()!=0:  # Monday=0
    base += dt.timedelta(days=1)
mon = base                       # v7 entry 起点(月曜)
tue = base + dt.timedelta(days=1)# v7 exit 起点(火曜)

def vevent(uid, title, desc, start_dt, dur_min, rrule):
    end_dt = start_dt + dt.timedelta(minutes=dur_min)
    f="%Y%m%dT%H%M%S"
    return "\r\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}@chien-ea",
        f"DTSTART;TZID=Asia/Tokyo:{start_dt.strftime(f)}",
        f"DTEND;TZID=Asia/Tokyo:{end_dt.strftime(f)}",
        f"RRULE:{rrule}",
        f"SUMMARY:{title}",
        f"DESCRIPTION:{desc}",
        "BEGIN:VALARM","TRIGGER:-PT5M","ACTION:DISPLAY","DESCRIPTION:reminder","END:VALARM",
        "END:VEVENT",
    ])

ev=[]
# v7 ENTRY (月曜 13/15/17/19 JST)
for h in (13,15,17,19):
    s=dt.datetime(mon.year,mon.month,mon.day,h,0,0)
    ev.append(vevent(f"v7entry{h}", f"v7 ENTRY 円LONG (JST {h}:00 / UTC {h-9})",
        "v7=月曜・週末フローLONG(EURJPY/GBPJPY/USDJPY)。定刻エントリー・24h保有。スプレッド高/ニュース時はスキップ。",
        s, 30, "FREQ=WEEKLY;BYDAY=MO"))
# v7 EXIT (火曜 同時刻=24h後)
for h in (13,15,17,19):
    s=dt.datetime(tue.year,tue.month,tue.day,h,0,0)
    ev.append(vevent(f"v7exit{h}", f"v7 EXIT 24h時間決済 (JST {h}:00)",
        "v7の各ショットを建玉24h後に時間決済(目安)。", s, 15, "FREQ=WEEKLY;BYDAY=TU"))
# v4 判定 (平日 06:30 JST)
s=dt.datetime(mon.year,mon.month,mon.day,6,30,0)
ev.append(vevent("v4check", "v4 日足判定 (条件成立時のみ建玉)",
    "v4=日足k≥4合議(9ペア)。日足確定(業者サーバ00:00≒JST 6-7時, DSTで±1h)に判定。条件成立時のみ建玉・SL1.5ATR/RR1.2/8日。",
    s, 15, "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"))
# E5 判定 (毎月1日 06:30 JST)
s=dt.datetime(2026,7,1,6,30,0)
ev.append(vevent("e5check", "E5 月初判定 (方向転換時のみ建玉)",
    "E5=金+株価指数の月次TSMOM。月初に判定・方向転換時のみ建て替え。", s, 15, "FREQ=MONTHLY;BYMONTHDAY=1"))

ics = "\r\n".join([
  "BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//chien-monitor//EA schedule//JA","CALSCALE:GREGORIAN",
  "METHOD:PUBLISH","X-WR-CALNAME:Chien EA Schedule","X-WR-TIMEZONE:Asia/Tokyo",
  # Asia/Tokyo VTIMEZONE (固定+0900・DSTなし)
  "BEGIN:VTIMEZONE","TZID:Asia/Tokyo","BEGIN:STANDARD","DTSTART:19700101T000000",
  "TZOFFSETFROM:+0900","TZOFFSETTO:+0900","TZNAME:JST","END:STANDARD","END:VTIMEZONE",
  *ev,
  "END:VCALENDAR",
]) + "\r\n"

with open(PATH,"w",encoding="utf-8",newline="") as f:
    f.write(ics)
print("wrote", PATH)
print(f"v7 entry起点(月曜)={mon}  v7 exit起点(火曜)={tue}")
print(f"イベント数: {len(ev)} (v7entry4 + v7exit4 + v4平日 + E5月初)")
