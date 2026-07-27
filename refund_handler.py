"""
业务层：小额退款处理
规则引擎（v1.0 硬编码 if 规则）
v1.0：固定规则 → v2.0：大模型生成话术
"""

import csv
import logging
from datetime import datetime, date

from config import ORDERS_CSV, CSV_ENCODING
from config import REFUND_MAX_AMOUNT, REFUND_MAX_DAYS, REFUND_ALLOWED_STATUS

logger = logging.getLogger(__name__)


def _days_since(order_date_str: str, today: date | None = None) -> int:
    """计算从下单到今天的间隔天数（内部辅助函数）"""
    order_date = datetime.strptime(order_date_str.strip(), "%Y-%m-%d").date()
    today = today or date.today()
    return (today - order_date).days


def handle_refund(order_id: str) -> dict:
    """
    处理退款申请。

    Args:
        order_id: 订单号

    Returns:
        dict: {
            "decision": "approved" | "escalated" | "order_not_found",
            "reason": str | None,      # escalated 时说明原因
            "order": dict | None       # 订单信息
        }
    """
    # 1. 查订单
    order = _find_order(order_id)
    if order is None:
        logger.info("退款申请: %s 订单不存在", order_id)
        return {"decision": "order_not_found", "reason": None, "order": None}

    amount = float(order["amount"])
    status = order["status"].strip()
    days = _days_since(order["order_date"])

    logger.info(
        "退款审核: %s 金额=%.2f 状态=%s 下单天数=%d",
        order_id, amount, status, days,
    )

    # 2. 逐条检查条件（早返回原则）
    checks = []

    if amount > REFUND_MAX_AMOUNT:
        checks.append(f"金额 ¥{amount:.0f} 超过免审限额 ¥{REFUND_MAX_AMOUNT:.0f}")

    if status != REFUND_ALLOWED_STATUS:
        checks.append(f"当前状态「{status}」不是「{REFUND_ALLOWED_STATUS}」")

    if days > REFUND_MAX_DAYS:
        checks.append(f"已下单 {days} 天，超过 {REFUND_MAX_DAYS} 天免审期")

    if checks:
        reason = "；".join(checks)
        logger.info("退款转人工: %s 原因=%s", order_id, reason)
        return {"decision": "escalated", "reason": reason, "order": order}

    # 3. 全部通过 → 自动同意
    logger.info("退款自动同意: %s 金额=%.2f", order_id, amount)
    return {"decision": "approved", "reason": None, "order": order}


def _find_order(order_id: str) -> dict | None:
    """内部函数：根据订单号查订单"""
    try:
        with open(ORDERS_CSV, mode="r", encoding=CSV_ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["order_id"].strip() == order_id.strip():
                    return row
    except FileNotFoundError:
        logger.error("订单数据文件不存在: %s", ORDERS_CSV)
        return None
    except Exception as e:
        logger.error("读取订单数据异常: %s", str(e))
        return None
    return None
