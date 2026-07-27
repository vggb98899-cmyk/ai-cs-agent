"""
业务层：取消订单处理
v2.0 新增：与退款退货逻辑切开

核心逻辑（李敏红线）：
- 未发货 → 直接取消，不走金额审核
- 已发货 → 转入退货退款流程（走200元+7天规则）
"""

import csv
import logging

from config import ORDERS_CSV, CSV_ENCODING

logger = logging.getLogger(__name__)

# 定义"已发货"的状态集合
SHIPPED_STATUSES = {"运输中", "已揽收", "已发货未签收", "派送中", "已签收"}


def handle_cancel(order_id: str) -> dict:
    """
    处理取消订单请求。

    Args:
        order_id: 订单号

    Returns:
        dict: {
            "decision": "cancelled" | "redirect_to_refund" | "order_not_found",
            "reason": str | None,
            "order": dict | None,
        }
    """
    order = _find_order(order_id)
    if order is None:
        logger.info("取消订单: %s 订单不存在", order_id)
        return {"decision": "order_not_found", "reason": None, "order": None}

    status = order["status"].strip()
    logger.info("取消审核: %s 当前状态=%s", order_id, status)

    # 未发货 → 直接取消成功
    if status not in SHIPPED_STATUSES:
        logger.info("取消成功: %s 未发货，直接取消", order_id)
        return {"decision": "cancelled", "reason": None, "order": order}

    # 已发货 → 转入退货退款流程
    logger.info("取消转退款: %s 已发货（%s），转入退货退款", order_id, status)
    return {
        "decision": "redirect_to_refund",
        "reason": f"订单已{status}，无法直接取消，已转入退货退款流程",
        "order": order,
    }


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
