"""
配置层：所有阈值、路径、关键词集中管理
其他模块引用本模块，运行时不得修改
"""

import os
from pathlib import Path

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
    "投诉", "差评", "欺诈", "曝光", "骗子",
    "315", "工商", "法院", "律师", "起诉",
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

# ---------- CSV 编码 ----------
CSV_ENCODING = "utf-8-sig"
