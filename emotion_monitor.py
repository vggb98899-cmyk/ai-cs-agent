"""
业务层：情绪监控
v1.0：关键词匹配
v2.0：关键词匹配 + DeepSeek 语义分析（补漏）
"""

import logging
import re

from config import ALERT_KEYWORDS
from reply_builder import build_alert_message
from deepseek_client import analyze_sentiment

logger = logging.getLogger(__name__)


def _extract_order_id(text: str) -> str | None:
    """从文本中提取订单号（ORD开头+3位数字）"""
    match = re.search(r"ORD\d{3,6}", text)
    return match.group(0) if match else None


def check_emotion(customer_msg: str, order_id: str | None = None) -> dict:
    """
    检查客户消息是否触发情绪告警。

    策略（两层防护）：
    1. 关键词匹配（快路径）→ 命中直接告警
    2. DeepSeek 语义分析（慢路径）→ 关键词没命中但语义负面也告警

    Returns:
        dict: {
            "is_alert": bool,
            "matched_keywords": list[str],
            "alert_message": str,
            "order_id": str | None,
        }
    """
    detected_order = order_id or _extract_order_id(customer_msg)

    # ====== 第1层：关键词匹配（快路径） ======
    matched = [kw for kw in ALERT_KEYWORDS if kw in customer_msg]

    if matched:
        alert_msg = build_alert_message(customer_msg, matched, detected_order)
        logger.warning("关键词告警: %s 订单=%s", matched, detected_order)
        return {
            "is_alert": True,
            "matched_keywords": matched,
            "alert_message": alert_msg,
            "order_id": detected_order,
        }

    # ====== 第2层：DeepSeek 语义分析（补漏） ======
    sentiment = analyze_sentiment(customer_msg)
    if sentiment.get("success") and sentiment.get("is_negative"):
        # DeepSeek 认为有负面情绪，也告警
        alert_msg = build_alert_message(
            customer_msg,
            [f"[DeepSeek]{sentiment.get('sentiment', '负面情绪')}"],
            detected_order,
        )
        logger.warning("DeepSeek 语义告警: %s", sentiment.get("reason"))
        return {
            "is_alert": True,
            "matched_keywords": [f"DeepSeek:{sentiment.get('sentiment', '')}"],
            "alert_message": alert_msg,
            "order_id": detected_order,
        }

    return {
        "is_alert": False,
        "matched_keywords": [],
        "alert_message": "",
        "order_id": detected_order,
    }
