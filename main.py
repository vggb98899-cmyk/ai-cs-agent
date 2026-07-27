"""
入口层：消息编排
流程：情绪检测 → 意图识别 → 回复/告警
不超过 50 行，只做组装不做实现
"""

import logging

from config import LOG_LEVEL, LOG_FILE
from reply_builder import (
    build_greeting,
    build_logistics_reply,
    build_logistics_not_found,
    build_refund_approved_reply,
    build_refund_escalated_reply,
    build_refund_order_not_found,
)
from logistics_checker import check_logistics
from refund_handler import handle_refund
from emotion_monitor import check_emotion
from deepseek_client import generate_refund_reply as ds_refund_reply

# ---------- 配置日志 ----------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")


def _extract_order_id(text: str) -> str | None:
    """从文本中提取订单号（ORD开头+3位数字）"""
    import re
    match = re.search(r"ORD\d{3,6}", text)
    return match.group(0) if match else None


def process_message(customer_msg: str, order_id: str | None = None) -> dict:
    """
    处理单条客户消息，返回回复内容和告警记录。
    """
    # ====== 第1步：情绪检测（优先级最高） ======
    emotion = check_emotion(customer_msg, order_id)
    if emotion["is_alert"]:
        logger.warning("命中情绪关键词，转人工: %s", emotion["matched_keywords"])
        return {
            "action": "alert_human",
            "reply": "",
            "alert": emotion["alert_message"],
        }

    # ====== 第2步：意图识别 ======
    msg = customer_msg.strip()

    # 场景A：客户说"退款"/"退"（"能退吗"也能触发）
    if "退款" in msg or "退" in msg:
        extracted = _extract_order_id(msg) or order_id
        if not extracted:
            return {
                "action": "reply",
                "reply": "您好，请提供您的订单号，例如「退款 ORD003」",
                "alert": "",
            }
        result = handle_refund(extracted)
        if result["decision"] == "approved":
            amount = float(result["order"]["amount"])
            reply = ds_refund_reply(extracted, amount, customer_msg)
            return {"action": "reply", "reply": reply, "alert": ""}
        elif result["decision"] == "escalated":
            reply = build_refund_escalated_reply(extracted, result["reason"])
            alert = f"退款转人工: {extracted} 原因: {result['reason']}"
            return {"action": "escalated", "reply": reply, "alert": alert}
        else:
            reply = build_refund_order_not_found(extracted)
            return {"action": "reply", "reply": reply, "alert": ""}

    # 场景B：客户提供了订单号
    extracted = _extract_order_id(msg) or order_id
    if extracted:
        row = check_logistics(extracted)
        if row:
            reply = build_logistics_reply(extracted, row)
        else:
            reply = build_logistics_not_found(extracted)
        return {"action": "reply", "reply": reply, "alert": ""}

    # 场景C：客户说"人工"
    if "人工" in msg:
        return {
            "action": "escalated",
            "reply": "🔄 正在为您转接人工客服，请稍候……",
            "alert": "客户请求转人工客服",
        }

    # 场景D：其他 → 欢迎引导
    return {
        "action": "reply",
        "reply": build_greeting(),
        "alert": "",
    }


if __name__ == "__main__":
    """交互式测试入口：在命令行里直接发消息测试"""
    print("=" * 50)
    print("智能客服小智 v1.0  输入消息测试，输入 q 退出")
    print("=" * 50)
    print(build_greeting())
    print("-" * 50)

    while True:
        msg = input("\n>>> 客户消息：").strip()
        if msg.lower() in ("q", "quit", "exit"):
            print("已退出")
            break

        result = process_message(msg)

        if result["action"] == "alert_human":
            print(f"\n🚨 [告警] {result['alert']}")
        elif result["action"] == "escalated":
            print(f"\n🔄 [转人工] {result['reply']}")
            if result["alert"]:
                print(f"   ⚠️ {result['alert']}")
        elif result["action"] == "reply":
            print(f"\n🤖 [回复]\n{result['reply']}")
