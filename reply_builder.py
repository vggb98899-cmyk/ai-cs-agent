"""
工具层：组装各类回复消息
只依赖 config.py，不依赖任何业务模块
"""

from datetime import datetime
from config import REFUND_MAX_AMOUNT


def build_logistics_reply(order_id: str, row: dict) -> str:
    """组装物流查询回复"""
    lines = [
        f"📦 订单 {order_id} 物流信息：",
        f"  快递公司：{row['carrier']}",
        f"  运单号：{row['tracking_number']}",
        f"  当前状态：{row['status']}",
        f"  最新位置：{row['last_location']}（{row['last_time']}）",
    ]
    # 轨迹换行展示
    trajectory = row["trajectory"].replace("→", "\n  → ")
    lines.append(f"  轨迹详情：\n  {trajectory}")
    return "\n".join(lines)


def build_logistics_not_found(order_id: str) -> str:
    """订单号未匹配"""
    return (
        f"❌ 未查到订单 {order_id} 的物流信息，请核对订单号是否正确。\n"
        f"如需帮助，请回复「人工」联系客服。"
    )


def build_refund_approved_reply(order_id: str, amount: float) -> str:
    """退款自动同意通知"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return (
        f"✅ 您好，订单 {order_id}（¥{amount:.2f}）的退款申请已自动审核通过。\n"
        f"退款金额将在 1-3 个工作日内原路返回。\n"
        f"处理时间：{now}\n"
        f"如有其他问题请随时联系，感谢您的理解与支持！"
    )


def build_refund_escalated_reply(order_id: str, reason: str) -> str:
    """退款转人工通知"""
    return (
        f"🔄 您好，订单 {order_id} 的退款申请因「{reason}」"
        f"已转交人工客服处理，请耐心等待。\n"
        f"我们会尽快为您处理！"
    )


def build_refund_order_not_found(order_id: str) -> str:
    """未查到订单"""
    return f"❌ 未查到订单 {order_id}，请核对订单号。"


def build_greeting() -> str:
    """欢迎消息"""
    return (
        "您好，我是智能客服小智 ⚡\n"
        "您可以发送以下内容：\n"
        "  • 订单号 → 查询物流\n"
        "  • 「退款+订单号」→ 申请退款\n"
        "  • 「人工」→ 转接人工客服"
    )


def build_cancel_success_reply(order_id: str) -> str:
    """取消订单成功通知（未发货）"""
    return (
        f"✅ 订单 {order_id} 已成功取消，商品尚未发货，无需其他操作。\n"
        f"退款金额将在 1-3 个工作日内原路返回。"
    )


def build_cancel_redirect_reply(order_id: str, reason: str) -> str:
    """已发货→转退款通知"""
    return (
        f"🔄 订单 {order_id} 已发货，无法直接取消。\n"
        f"{reason}，请耐心等待人工处理。"
    )


def build_alert_message(
    customer_msg: str,
    matched_keywords: list[str],
    order_id: str | None,
) -> str:
    """组装飞书告警消息（模拟）"""
    keyword_str = "、".join(matched_keywords)
    order_str = order_id if order_id else "未知"
    return (
        f"🚨 情绪关键词告警\n"
        f"触发词：{keyword_str}\n"
        f"关联订单：{order_str}\n"
        f"客户消息：{customer_msg[:200]}"
    )
