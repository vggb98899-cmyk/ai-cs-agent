"""
业务层：物流查询
读本地 CSV 匹配订单号，返回物流轨迹
v1.0：本地 CSV → v2.0：Playwright 模拟抓取
"""

import csv
import logging

from config import LOGISTICS_CSV, CSV_ENCODING

logger = logging.getLogger(__name__)


def check_logistics(order_id: str) -> dict | None:
    """
    根据订单号查询物流信息。
    
    Args:
        order_id: 订单号（如 ORD001）
    
    Returns:
        匹配到的物流行字典，或 None（未找到）
    """
    try:
        with open(LOGISTICS_CSV, mode="r", encoding=CSV_ENCODING) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["order_id"].strip() == order_id.strip():
                    logger.info("物流匹配成功: %s", order_id)
                    return row
    except FileNotFoundError:
        logger.error("物流数据文件不存在: %s", LOGISTICS_CSV)
        return None
    except Exception as e:
        logger.error("读取物流数据异常: %s", str(e))
        return None

    logger.info("物流匹配失败: %s（无此订单）", order_id)
    return None
