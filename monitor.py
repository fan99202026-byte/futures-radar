#!/usr/bin/env python3
"""用法:
  python monitor.py test   发一条测试推送(检查密钥对不对)
  python monitor.py poll   扫描一次(给 GitHub Actions 定时用)
  python monitor.py ws     实时模式(需要一台一直开着、能连币安的电脑/服务器)
只读取公开行情,不需要币安 API Key,不会下单。"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

import config
from signals import Candle, evaluate

BJ = timezone(timedelta(hours=8))


# ---------- 推送 ----------
def notify(title, text):
    """推送通知到所有已配置的渠道。"""
    sent = False
    
    # Telegram
    tg_token, tg_chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        try:
            r = requests.post(f"https://api.telegram.org/bot{tg_token}/sendMessage",
                              json={"chat_id": tg_chat, "text": f"{title}\n{text}"}, timeout=15)
            print(f"✓ Telegram {r.status_code}")
            sent = True
        except Exception as e:
            print(f"✗ Telegram 失败: {e}")
    
    # Bark
    bark_key = os.getenv("BARK_KEY")
    if bark_key:
        try:
            server = os.getenv("BARK_SERVER", "https://api.day.app")
            r = requests.post(f"{server}/push", 
                            json={"device_key": bark_key, "title": title,
                                  "body": text, "group": "合约提醒"}, timeout=15)
            print(f"✓ Bark {r.status_code}")
            sent = True
        except Exception as e:
            print(f"✗ Bark 失败: {e}")
    
    # 飞书
    feishu = os.getenv("FEISHU_WEBHOOK")
    if feishu:
        try:
            r = requests.post(feishu, json={"msg_type": "text",
                                            "content": {"text": f"{title}\n{text}"}}, timeout=15)
            print(f"✓ 飞书 {r.status_code}")
            sent = True
        except Exception as e:
            print(f"✗ 飞书 失败: {e}")
    
    if not sent:
        print("(未配置推送渠道,只打印)")
    print(f"--- {title}\n{text}\n")


# ---------- 行情 ----------
def fetch_candles(symbol):
    """从币安拉取已收盘的 K 线。"""
    r = requests.get(f"{config.FAPI_BASE}/fapi/v1/klines",
                     params={"symbol": symbol, "interval": config.INTERVAL,
                             "limit": config.KLINE_LIMIT}, timeout=15)
    r.raise_for_status()
    now = int(time.time() * 1000)
    out = []
    for k in r.json():
        if k[6] < now:  # 收盘时间已过 = 已收盘,最后一根未收盘的丢掉
            out.append(Candle(k[0], float(k[1]), float(k[2]), float(k[3]),
                              float(k[4]), float(k[5]), k[6], float(k[7])))
    return out


def run_poll():
    """扫描一次:逐个币种拉行情,检测信号,推送。"""
    ok = 0
    for sym in config.SYMBOLS:
        try:
            candles = fetch_candles(sym)
            ok += 1
        except requests.HTTPError as e:
            code = e.response.status_code
            hint = "(被地区限制,GitHub 的服务器可能在币安不支持的地区)" if code == 451 else ""
            print(f"❌ {sym} 取行情失败 HTTP {code} {hint}")
            continue
        except Exception as e:
            print(f"❌ {sym} 取行情失败: {e!r}")
            continue
        
        sigs = evaluate(sym, candles)
        print(f"✓ {sym}: 已收盘K线 {len(candles)} 根, 提醒 {len(sigs)} 个")
        for s in sigs:
            notify(s.title, s.text)
    
    if ok == 0:
        print("❌ 全部币种获取失败")
        sys.exit(1)  # 全部失败就让这次运行显示红色,方便发现


def on_kline_event(data, buffers):
    """处理一条 WebSocket kline 推送。只有K线收盘(x=true)才返回提醒。"""
    if data.get("e") != "kline":
        return []
    k = data["k"]
    if not k.get("x"):  # 未收盘,跳过
        return []
    
    sym = data["s"]
    candle = Candle(k["t"], float(k["o"]), float(k["h"]), float(k["l"]),
                    float(k["c"]), float(k["v"]), k["T"], float(k["q"]))
    buf = buffers.setdefault(sym, [])
    
    # 更新缓冲区:如果是同一根K线的更新,替换;否则追加
    if buf and buf[-1].open_time == candle.open_time:
        buf[-1] = candle
    else:
        buf.append(candle)
    
    # 只保留最近的 KLINE_LIMIT 根
    del buf[:-config.KLINE_LIMIT]
    
    return evaluate(sym, buf)


async def run_ws():
    """实时模式:连接 WebSocket,收收行情推送,检测信号,推送提醒。"""
    import websockets
    
    print("初始化缓冲区...")
    buffers = {s: fetch_candles(s) for s in config.SYMBOLS}
    print(f"✓ 已加载 {len(buffers)} 个币种的历史K线")
    
    streams = "/".join(f"{s.lower()}@kline_{config.INTERVAL}" for s in config.SYMBOLS)
    url = f"{config.WS_BASE}?streams={streams}"
    
    last_sent = {}  # (symbol, kind) -> 上次推送时间
    reconnect_count = 0
    
    while True:\n        try:
            reconnect_count += 1
            print(f"[连接 #{reconnect_count}] 连接 WebSocket: {len(config.SYMBOLS)} 个币种")
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                print(f"✓ 已连接币安实时行情")
                reconnect_count = 0  # 连接成功,重置计数
                
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        sigs = on_kline_event(msg.get("data", msg), buffers)
                        for s in sigs:
                            key = (s.symbol, s.kind)
                            # 冷却期检查:防刷屏
                            if time.time() - last_sent.get(key, 0) < config.COOLDOWN_MIN * 60:
                                print(f"⏸ {s.symbol} {s.kind} 在冷却期内,跳过")
                                continue
                            last_sent[key] = time.time()
                            print(f"\\n🔔 [信号] {s.symbol} {s.kind}")
                            notify(s.title, s.text)
                    except json.JSONDecodeError:
                        print(f"⚠ 收到畸形 JSON,跳过")
                        continue
        except asyncio.CancelledError:
            print("\\n收到停止信号,退出")
            break
        except Exception as e:
            print(f"\\n❌ WebSocket 连接断开: {e!r}")
            wait_sec = min(30, 2 ** (reconnect_count - 1))  # 指数退避,最多等30秒
            print(f"⏳ {wait_sec} 秒后重连...")
            await asyncio.sleep(wait_sec)
            try:  # 补齐断线期间漏掉的K线
                print("补充历史K线...")
                buffers = {s: fetch_candles(s) for s in config.SYMBOLS}
                print(f"✓ 已重新加载")
            except Exception as e2:
                print(f"⚠ 补充K线失败: {e2!r}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "poll"
    if mode == "test":
        print("📤 发送测试推送...")
        notify("合约提醒·测试", "收到这条说明推送渠道已经配置成功。✓")
    elif mode == "poll":
        print("🔍 扫描模式开始...")
        run_poll()
    elif mode == "ws":
        print("🔌 实时模式开始...")
        try:
            asyncio.run(run_ws())
        except KeyboardInterrupt:
            print("\\n⏹ 用户中断")
    else:
        print("用法: python monitor.py [test|poll|ws]")
        print("  test - 发送测试推送")
        print("  poll - 扫描一次(GitHub Actions 用)")
        print("  ws   - 实时模式(长期运行)")
