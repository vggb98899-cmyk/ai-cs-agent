"""
配置层：所有阈值、路径、关键词集中管理
其他模块引用本模块，运行时不得修改
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（密钥从这里读，不硬编码）
load_dotenv()

# ---------- 路径 ----------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

LOGISTICS_CSV = DATA_DIR / "logistics.csv"
ORDERS_CSV = DATA_DIR / "orders.csv"

# ---------- 退款规则 ----------
REFUND_MAX_AMOUNT = 200.0       # 小额退款金额上限（元）
REFUND_MAX_DAYS = 7              # 下单到申请退款的最大天数
REFUND_ALLOWED_STATUS = "已发货未签收"

# ---------- 情绪关键词 ----------
ALERT_KEYWORDS = [
    # 投诉/维权类
    "投诉", "差评", "欺诈", "曝光", "骗子",
    "315", "工商", "法院", "律师", "起诉", "举报",
    # 辱骂/情绪类
    "操", "妈的", "垃圾", "废物", "SB", "傻逼", "去死",
    "TMD", "什么破", "什么烂",
    # 威胁类
    "没完", "走着瞧", "曝光你", "找你麻烦",
]

# ---------- 飞书告警 ----------
# v1.0 用 Webhook 模拟飞书告警，不需要真实机器人
FEISHU_WEBHOOK_URL = os.getenv(
    "FEISHU_WEBHOOK_URL",
    "",  # 空字符串时 fallback 到本地日志
)

# ---------- 日志 ----------
LOG_LEVEL = "INFO"
LOG_FILE = BASE_DIR / "cs_agent.log"

# ---------- DeepSeek API ----------
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# 是否启用 DeepSeek（有 Key 就启用，没有就 fallback 到规则）
DEEPSEEK_ENABLED = bool(DEEPSEEK_API_KEY)

# ---------- CSV 编码 ----------
CSV_ENCODING = "utf-8-sig"
