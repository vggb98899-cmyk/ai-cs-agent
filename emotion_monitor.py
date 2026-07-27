"""
业务层：情绪关键词监控
命中关键词 → 返回告警信息，禁止机器人自动回复
v1.0：关键词匹配 → v2.0：意图识别 + 情感分析
"""

import logging
import re

from config import ALERT_KEYWORDS
from reply_builder import build_alert_message

logger = logging.getLogger(__name__)


def _extract_order_id(text: str) -> str | None:
    """从文本中提取订单号（ORD开头+3位数字）"""
    match = re.search(r"ORD\d{3,6}", text)
    return match.group(0) if match else None


def check_emotion(customer_msg: str, order_id: str | None = None) -> dict:
    """
    检查客户消息是否触发情绪关键词。

    Args:
        customer_msg: 客户消息原文
        order_id: 可选，已提取的订单号

    Returns:
        dict: {
            "is_alert": True | False,
            "matched_keywords": list[str],
            "alert_message": str,
            "order_id": str | None
        }
    """
    # 1. 匹配关键词
    matched = []
    for keyword in ALERT_KEYWORDS:
        if keyword in customer_msg:
            matched.append(keyword)

    if not matched:
        return {
            "is_alert": False,
            "matched_keywords": [],
            "alert_message": "",
            "order_id": order_id,
        }

    # 2. 尝试从消息中提取订单号（如果没传的话）
    detected_order = order_id or _extract_order_id(customer_msg)

    # 3. 组装告警信息
    alert_msg = build_alert_message(customer_msg, matched, detected_order)

    logger.warning(
        "情绪告警触发: 关键词=%s 订单=%s 消息=%s",
        matched, detected_order, customer_msg[:80],
    )

    return {
        "is_alert": True,
        "matched_keywords": matched,
        "alert_message": alert_msg,
        "order_id": detected_order,
    }
