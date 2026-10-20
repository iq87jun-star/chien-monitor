# -*- coding: utf-8 -*-
"""オフライン検証: python -m pytest ops/theoption -q(ネットワーク・キー不要。偽の WebSocket サーバーで往復を確かめる)。"""
import asyncio, datetime as dt, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import to_probe as P, to_summarize as S

def upd(name, status="Opened", **kw):
    c = dict(name=name, status=status, type="HighLow", expiration_type="FixedDuration", asset=name.split("|")[0], **kw)
    return {"type": "update", "sid": "s-1", "key": name, "snapshot": True, "values": {"timestamp": "2026-10-26T21:01:00Z", "contract": json.dumps(c)}}

def test_parse_name():
    d = P.parse_name("BTCJPY|FE|15M|HIGHLOW|HIGH|2026_08_10_14_05_00")
    assert (d["asset"], d["exp"], d["dur"], d["product"], d["sel"], d["stamp"]) == ("BTCJPY", "FE", "15M", "HIGHLOW", "HIGH", "2026_08_10_14_05_00")
    assert P.parse_name("USDJPY|FD|30S|TOUCH|LOW")["sel"] == "LOW"
    assert P.is_target("USDJPY|FD|1H|HIGHLOW|HIGH") and not P.is_target("USDJPY|FE|1H|HIGHLOW|HIGH") and not P.is_target("BTCJPY|FD|1H|HIGHLOW|HIGH")

def test_recorder_and_summary(capsys):
    with tempfile.TemporaryDirectory() as tmp:
        r = P.Recorder(os.path.join(tmp, "x.jsonl"))
        assert r.on_frame(upd("USDJPY|FD|1H|HIGHLOW|HIGH", payout_multiplier=1.85)) == ["USDJPY|FD|1H|HIGHLOW|HIGH"]
        assert r.on_frame(upd("USDJPY|FD|1H|HIGHLOW|HIGH")) == []                       # 二度目は初出ではない
        assert r.on_frame(upd("EURJPY|FD|1H|HIGHLOW|LOW", status="Closed")) == []      # Opened 以外は数えない
        r.on_frame(upd("USDJPY|FD|30S|TOUCH|LOW")); r.on_frame({"type": "update", "sid": "s-2", "key": "k", "values": {"strike": "150.1"}})
        out = S.report(r.path)
        assert list(out["target"]) == ["USDJPY|FD|1H|HIGHLOW|HIGH"] and out["paysamp"]["USDJPY|FD|1H|HIGHLOW|HIGH"][1] == {"payout_multiplier": 1.85}
        assert ("FD", "30S", "TOUCH") in out["combo"] and "payout_multiplier" in out["fields"]

def test_ws_roundtrip_with_fake_gateway():
    import websockets
    got = {}
    async def handler(ws):
        req = getattr(ws, "request", None); hdrs = req.headers if req else ws.request_headers
        got["auth"] = hdrs.get("Authorization")
        await ws.send(json.dumps({"type": "ready", "connectionId": "c-1", "protocolVersion": "1.0"}))
        sub = json.loads(await ws.recv()); got["sub"] = sub
        await ws.send(json.dumps({"type": "subscribed", "reqId": sub["reqId"], "sid": "s-1"}))
        await ws.send(json.dumps(upd("GBPJPY|FD|1H|HIGHLOW|HIGH")))
        got["data_sub"] = json.loads(await ws.recv())
        await asyncio.sleep(0.2)
    async def run():
        async with websockets.serve(handler, "127.0.0.1", 0) as srv:
            port = list(srv.sockets)[0].getsockname()[1]
            with tempfile.TemporaryDirectory() as tmp:
                r = P.Recorder(os.path.join(tmp, "y.jsonl"))
                until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=30)
                try: await asyncio.wait_for(P.ws_session(f"ws://127.0.0.1:{port}", "KEY", r, until, True, 0), 3)
                except Exception: pass
                return r
    r = asyncio.run(run())
    assert got["auth"] == "Bearer KEY" and got["sub"] == {"type": "subscribe", "reqId": "1", "stream": "contracts"}
    assert got["data_sub"]["stream"] == "contract_data" and got["data_sub"]["key"] == "GBPJPY|FD|1H|HIGHLOW|HIGH"
    assert "GBPJPY|FD|1H|HIGHLOW|HIGH" in r.first_seen

def test_never_trades():
    src = open(P.__file__, encoding="utf-8").read()
    assert "/trading/buy" not in src and "/trading/sell" not in src

def test_write_summary_files():
    with tempfile.TemporaryDirectory() as tmp:
        r = P.Recorder(os.path.join(tmp, "probe_demo_20261026_0525.jsonl")); r.on_frame(upd("USDJPY|FD|1H|HIGHLOW|HIGH"))
        P.write_summary(r.path, r)
        assert "USDJPY|FD|1H|HIGHLOW|HIGH" in open(os.path.join(tmp, "probe_demo_20261026_0525.summary.txt"), encoding="utf-8").read()
        assert "targets=1" in open(os.path.join(tmp, "_diag", "last_run.txt"), encoding="utf-8").read()
