"""信号识别:只做计算,不联网。提醒=值得你看一眼,不是下单指令。"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import config

BJ = timezone(timedelta(hours=8))


@dataclass
class Candle:
    open_time: int   # 毫秒
    o: float
    h: float
    l: float
    c: float
    v: float         # 成交量(标的数量)
    close_time: int  # 毫秒
    qv: float        # 成交额(USDT)


@dataclass
class Signal:
    symbol: str
    kind: str        # 如 "放量突破(多)"
    sound: str       # long / short / spike_up / spike_down
    title: str
    text: str


def ma(values, n, back=0):
    end = len(values) - back
    start = end - n
    if start < 0:
        return None
    return sum(values[start:end]) / n


def fmt(x):
    return f"{x:,.2f}" if abs(x) >= 1 else f"{x:.4f}"


def _title(symbol, kind):
    name = config.NAMES.get(symbol, "")
    return f"{symbol} {name} {kind}".replace("  ", " ")


def _build(symbol, kind, side, candles, level_name, level, ma7, ma25, ma99, vol_ratio, sound="long"):
    last = candles[-1]
    recent = candles[-config.STOP_LOOKBACK:]
    if side == "long":
        stop = min(x.l for x in recent)
        risk = last.c - stop
        target = last.c + config.TARGET_R * risk
    else:
        stop = max(x.h for x in recent)
        risk = stop - last.c
        target = last.c - config.TARGET_R * risk
    if risk <= 0:
        return None
    fee = last.c * config.FEE_ROUND_TRIP_PCT
    net_rr = (config.TARGET_R * risk - fee) / (risk + fee)
    if net_rr < config.MIN_NET_RR:
        return None
    warn = "  ⚠️扣费后偏低,通常不值得做" if net_rr < 1.2 else ""
    when = datetime.fromtimestamp((last.close_time + 1) / 1000, BJ).strftime("%m-%d %H:%M")
    dist_ma7 = (last.c - ma7) / ma7 * 100
    text = (
        f"{when}(北京)5分钟K线收盘 {fmt(last.c)}\n"
        f"{level_name} {fmt(level)}｜量能 {vol_ratio:.1f}×均量｜距MA7 {dist_ma7:+.2f}%\n"
        f"MA7 {fmt(ma7)} / MA25 {fmt(ma25)} / MA99 {fmt(ma99)}\n"
        f"参考止损 {fmt(stop)}(风险 {fmt(risk)},{risk / last.c * 100:.2f}%)\n"
        f"参考目标{config.TARGET_R:g}R {fmt(target)}｜扣费后风险收益比约 {net_rr:.2f}{warn}\n"
        f"只是提醒,不是下单指令:先看是否追高、整体趋势、回踩是否缩量守住。"
    )
    return Signal(symbol, kind, sound, _title(symbol, kind), text)


def evaluate(symbol, candles):
    """candles:已收盘K线(旧→新)。返回最新一根收盘K线触发的提醒。"""
    if len(candles) < 105:
        return []
    last = candles[-1]
    closes = [x.c for x in candles]
    ma7, ma25, ma99 = ma(closes, 7), ma(closes, 25), ma(closes, 99)
    ma25_prev, ma99_prev = ma(closes, 25, back=3), ma(closes, 99, back=3)
    if None in (ma7, ma25, ma99, ma25_prev, ma99_prev):
        return []

    prev = candles[-1 - config.VOL_WINDOW:-1]
    avg_v = sum(x.v for x in prev) / len(prev)
    avg_qv = sum(x.qv for x in prev) / len(prev)
    if avg_v <= 0 or avg_qv < config.MIN_AVG_QUOTE_VOL:
        return []
    vol_ratio = last.v / avg_v

    look = candles[-1 - config.BREAKOUT_LOOKBACK:-1]
    hh = max(x.h for x in look)
    ll = min(x.l for x in look)
    up_trend = ma7 > ma25 > ma99 and ma25 > ma25_prev
    down_trend = ma7 < ma25 < ma99 and ma25 < ma25_prev
    t = config.PULLBACK_TOUCH_PCT

    found = []
    if last.c > hh and vol_ratio >= config.VOL_MULT and last.c > ma25:
        found.append(_build(symbol, "放量突破(多)", "long", candles,
                            f"突破近{config.BREAKOUT_LOOKBACK}根高点", hh, ma7, ma25, ma99, vol_ratio, sound="long"))
    if last.c < ll and vol_ratio >= config.VOL_MULT and last.c < ma25:
        found.append(_build(symbol, "放量跌破(空)", "short", candles,
                            f"跌破近{config.BREAKOUT_LOOKBACK}根低点", ll, ma7, ma25, ma99, vol_ratio, sound="short"))
    if (up_trend and ma25 * (1 - t) <= last.l <= ma7 * (1 + t)
            and last.c > ma25 and last.c > last.o and vol_ratio <= config.PULLBACK_VOL_MAX):
        found.append(_build(symbol, "回踩企稳(多)", "long", candles,
                            "回踩MA7~MA25区间,缩量收阳", ma7, ma7, ma25, ma99, vol_ratio, sound="long"))
    if (down_trend and ma7 * (1 - t) <= last.h <= ma25 * (1 + t)
            and last.c < ma25 and last.c < last.o and vol_ratio <= config.PULLBACK_VOL_MAX):
        found.append(_build(symbol, "反弹受阻(空)", "short", candles,
                            "反弹到MA7~MA25区间,缩量收阴", ma7, ma7, ma25, ma99, vol_ratio, sound="short"))
    return [s for s in found if s]


def evaluate_spike(symbol, closed, forming):
    """盘中急动:当前这根K线还没收盘,但涨跌幅和成交量已经明显异常,提前提醒。"""
    if not config.ENABLE_SPIKE or forming is None or len(closed) < config.VOL_WINDOW + 2:
        return []
    prev = closed[-config.VOL_WINDOW:]
    avg_v = sum(x.v for x in prev) / len(prev)
    avg_qv = sum(x.qv for x in prev) / len(prev)
    atr = sum(x.h - x.l for x in prev) / len(prev)
    if avg_v <= 0 or atr <= 0 or avg_qv < config.MIN_AVG_QUOTE_VOL:
        return []
    move = forming.c - forming.o
    if abs(move) < config.SPIKE_ATR_MULT * atr:
        return []
    vol_ratio = forming.v / avg_v
    if vol_ratio < config.SPIKE_VOL_MULT:
        return []
    up = move > 0
    kind = "盘中急拉" if up else "盘中急跌"
    now = datetime.now(BJ).strftime("%H:%M:%S")
    text = (
        f"{now}(北京) 盘中急动 {fmt(abs(move))} 点 | 成交量 {forming.v:.0f} | 平均量 {avg_v:.0f} | 放大 {vol_ratio:.2f}×"
    )
    sound = "spike_up" if up else "spike_down"
    return [Signal(symbol, kind, sound, _title(symbol, kind), text)]
