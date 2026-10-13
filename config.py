"""可调参数。想增减关注的合约,只改 WATCHLIST;想让提醒更灵敏/更少,改下面的参数。"""
import os

# ============ 关注列表:(币安合约代码, 中文名) ============
# 增加/删除一行即可。代码必须和币安合约页面显示的一致,例如 MUUSDT。
WATCHLIST = [
    # --- 半导体 / 存储 / AI 硬件 ---
    ("MUUSDT", "美光"),
    ("AMDUSDT", "AMD"),
    ("AVGOUSDT", "博通"),
    ("INTCUSDT", "英特尔"),
    ("NVDAUSDT", "英伟达"),
    ("TSMUSDT", "台积电"),
    ("AMATUSDT", "应用材料"),
    ("MRVLUSDT", "Marvell"),
    ("SKHYNIXUSDT", "SK海力士"),
    ("CXMTUSDT", "长鑫科技"),
    ("WDCUSDT", "西部数据"),
    ("CIENUSDT", "Ciena"),
    ("HPEUSDT", "慧与科技"),
    ("SMCIUSDT", "超微电脑"),
    # --- 科技 / 软件 ---
    ("GOOGLUSDT", "谷歌"),
    ("ORCLUSDT", "甲骨文"),
    ("MDBUSDT", "MongoDB"),
    ("TSLAUSDT", "特斯拉"),
    ("BABAUSDT", "阿里巴巴"),
    # --- 加密相关 / 券商 ---
    ("COINUSDT", "Coinbase"),
    ("MSTRUSDT", "微策略"),
    ("HOODUSDT", "罗宾汉"),
    # --- 航天 / 商品 / 能源 ---
    ("RKLBUSDT", "Rocket Lab"),
    ("SPCXUSDT", "太空探索"),
]

# 把 WATCHLIST 展开成 SYMBOLS 与 NAMES
SYMBOLS = [s for s, _ in WATCHLIST]
NAMES = dict(WATCHLIST)

# ============ 声音 ============
SOUND = True          # 有提醒时是否发声
SPEAK = True          # 发声后再用语音报出"哪只合约+什么信号"(Windows 自带语音,不想要改 False)
SPEAK_RATE = 2        # 语速 -10 ~ 10
ALERT_LOG = "alerts.log"   # 每条提醒都会记到这个文件,方便复盘

# ============ 行情 ============
INTERVAL = "5m"
KLINE_LIMIT = 150        # 要 >= 105 才能算 MA99
LOOP_SECONDS = 10        # 轮询备用模式:每隔几秒刷新一次
FAPI_BASE = os.getenv("BINANCE_FAPI", "https://fapi.binance.com")
# 实时连线地址;连不上时程序会自动改用轮询。也可手动改成旧路径 wss://fstream.binance.com/stream
WS_BASE = os.getenv("BINANCE_WS", "wss://fstream.binance.com/market/stream")

# ============ K线收盘后的信号 ============
BREAKOUT_LOOKBACK = 24     # 突破:超过最近多少根K线的高点/低点(24根=2小时)
VOL_WINDOW = 20            # 均量取最近多少根
VOL_MULT = 2.0             # 突破K线成交量需 >= 均量的几倍
PULLBACK_TOUCH_PCT = 0.0015  # 回踩:最低价离均线多近算"碰到"(0.15%)
PULLBACK_VOL_MAX = 1.0     # 回踩K线成交量 <= 均量的几倍才算缩量
COOLDOWN_MIN = 30          # 同一合约同一类提醒,多少分钟内只响一次

# ============ 盘中急动(K线还没收盘就提醒) ============
ENABLE_SPIKE = True
SPIKE_ATR_MULT = 3.0       # 当前5分钟K线涨跌幅 >= 近20根平均振幅的几倍
SPIKE_VOL_MULT = 1.5       # 且这根K线已成交量 >= 近20根平均全根成交量的几倍
SPIKE_COOLDOWN_MIN = 10

# ============ 风险与成本(提醒里会直接算出扣费后的风险收益比) ============
STOP_LOOKBACK = 5          # 参考止损 = 最近几根K线的最低点(多)/最高点(空)
TARGET_R = 2.0             # 参考目标 = 止损距离的几倍
FEE_ROUND_TRIP_PCT = 0.001 # 往返手续费占名义价值比例(0.1%,请按你的真实费率改)
MIN_NET_RR = 0.0           # 扣费后风险收益比低于它就不提醒;0=全部提醒但标注⚠️

# ============ 过滤 ============
MIN_AVG_QUOTE_VOL = 5000   # 近20根平均成交额(USDT)低于它不提醒(周末/太清淡);越小越灵敏
