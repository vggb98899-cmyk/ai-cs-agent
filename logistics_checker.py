"""
业务层：物流查询
v1.0：本地 CSV
v2.0：先试 Playwright 抓取，失败降级 CSV（李敏要求"体面的降级"）
"""

import csv
import logging

from config import LOGISTICS_CSV, CSV_ENCODING
from logistics_fetcher import fetch_logistics

logger = logging.getLogger(__name__)


# CSV 中的物流商映射（order_id → carrier name）
_CARRIER_MAP: dict[str, str] = {}


def _load_carrier_map():
    """加载订单→物流商映射"""
    global _CARRIER_MAP
    try:
        with open(LOGISTICS_CSV, mode="r", encoding=CSV_ENCODING) as f:
            for row in csv.DictReader(f):
                _CARRIER_MAP[row["order_id"].strip()] = row["carrier"].strip()
    except Exception:
        pass


def check_logistics_online(order_id: str) -> dict | None:
    """
    物流查询：先 Playwright 抓取，失败降级 CSV。
    符合李敏要求的"体面的降级"——客户不会看到报错。
    
    Returns:
        dict | None: {"status", "trajectory", "source", "carrier", ...} 或 None
    """
    # 1. 查 CSV 获取物流商和单号（为 Playwright 准备）
    csv_row = check_logistics(order_id)
    if csv_row is None:
        return None

    tracking = csv_row.get("tracking_number", "")
    carrier = csv_row.get("carrier", "")

    # 2. 试 Playwright 抓取（可能失败，比如被反爬）
    if tracking:
        result = fetch_logistics(tracking, carrier)
        if result:
            # Playwright 成功 → 用真实数据
            result["carrier"] = carrier
            result["tracking_number"] = tracking
            result["order_id"] = order_id
            result["source"] = "playwright"
            logger.info("✅ Playwright 抓取成功: %s (%s)", order_id, carrier)
            return result

    # 3. 降级：返回 CSV 数据
    logger.info("⬇️ 降级 CSV: %s", order_id)
    csv_row["source"] = "csv"
    return csv_row


def check_logistics(order_id: str) -> dict | None:
    """
    CSV 本地查询（内部用，退款流程需要订单状态时不调 Playwright）
    """
    try:
        with open(LOGISTICS_CSV, mode="r", encoding=CSV_ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["order_id"].strip() == order_id.strip():
                    return row
    except FileNotFoundError:
        logger.error("物流数据文件不存在: %s", LOGISTICS_CSV)
        return None
    except Exception as e:
        logger.error("读取物流数据异常: %s", str(e))
        return None

    logger.info("物流匹配失败: %s（无此订单）", order_id)
    return None
