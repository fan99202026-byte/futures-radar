"""可调参数。想改观察哪些合约、提醒多敏感,只改这个文件。"""
import os

# 观察列表(币安 USDT 永续合约代码,大写)
# 今天重点关注: MUU AMD MSTR COIN
SYMBOLS = ["MUUSDT", "AMDUSDT", "MSTRUSDT", "COINUSDT"]

INTERVAL = "5m"          # 看几分钟K线
KLINE_LIMIT = 150        # 每次取多少根(要 >= 105,才能算 MA99)

# 币安接口地址(能直连用默认值即可)
FAPI_BASE = os.getenv("BINANCE_FAPI", "https://fapi.binance.com")
# 实时模式的行情地址;若连不上,可改成旧路径 wss://fstream.binance.com/stream
WS_BASE = os.getenv("BINANCE_WS", "wss://fstream.binance.com/market/stream")

# ---- 信号参数 ----
BREAKOUT_LOOKBACK = 24     # 突破:要超过最近多少根K线的高点/低点(24根=2小时)
VOL_WINDOW = 20            # 均量取最近多少根
VOL_MULT = 2.0             # 突破K线成交量需 >= 均量的几倍
PULLBACK_TOUCH_PCT = 0.0015  # 回踩:最低价离均线多近算"碰到"(0.15%)
PULLBACK_VOL_MAX = 1.0     # 回踩K线成交量 <= 均量的几倍才算缩量

# ---- 风险与成本(用来在提醒里直接算出扣费后的风险收益比) ----
STOP_LOOKBACK = 5          # 参考止损 = 最近几根K线的最低点(多)/最高点(空)
TARGET_R = 2.0             # 参考目标 = 止损距离的几倍
FEE_ROUND_TRIP_PCT = 0.001 # 往返手续费占名义价值比例(0.1%,请按你的真实费率改)
MIN_NET_RR = 0.0           # 扣费后风险收益比低于它就不提醒;0=全部提醒但标注⚠️

# ---- 过滤与防刷屏 ----
MIN_AVG_QUOTE_VOL = 20000  # 近20根平均成交额(USDT)低于它不提醒(周末/夜盘太清淡)
COOLDOWN_MIN = 30          # 实时模式:同一合约同一类提醒,30分钟内只推一次
