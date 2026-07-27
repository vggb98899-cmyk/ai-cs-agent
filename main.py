"""
入口层：消息编排
流程：情绪检测 → 意图识别 → 回复/告警
关键词匹配（快路径）→ DeepSeek 语义理解（慢路径）
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
    build_cancel_success_reply,
    build_cancel_redirect_reply,
)
from logistics_checker import check_logistics, check_logistics_online
from refund_handler import handle_refund
from cancel_handler import handle_cancel
from emotion_monitor import check_emotion
from deepseek_client import generate_refund_reply as ds_refund_reply
from deepseek_client import classify_intent

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


def _is_garbage_input(text: str) -> bool:
    """检测无意义的乱码/垃圾输入，避免浪费 DeepSeek API"""
    import re
    # 提取中文字符
    chinese = re.findall(r'[\u4e00-\u9fff]', text)
    # 全是标点/符号/字母且少于10个字符 → 乱码
    if len(chinese) == 0 and len(text.strip()) < 15:
        return True
    # 全是重复标点
    if all(c in '。，！？.?!,~-、…' for c in text.strip()):
        return True
    return False


def _handle_refund_intent(order_id: str, customer_msg: str, mild_alert: str = "") -> dict:
    """处理退款意图（提取为独立函数，两处共用）"""
    if not order_id:
        return {
            "action": "reply",
            "reply": "您好，请提供您的订单号，例如「退款 ORD003」",
            "alert": mild_alert,
        }
    result = handle_refund(order_id)
    if result["decision"] == "approved":
        amount = float(result["order"]["amount"])
        order_status = result["order"]["status"]
        # 查物流状态，让 DeepSeek 基于事实说话
        log_row = check_logistics(order_id)
        log_status = log_row["status"] if log_row else ""
        reply = ds_refund_reply(order_id, amount, customer_msg,
                                order_status, log_status)
        return {"action": "reply", "reply": reply, "alert": mild_alert}
    elif result["decision"] == "escalated":
        reply = build_refund_escalated_reply(order_id, result["reason"])
        alert = f"退款转人工: {order_id} 原因: {result['reason']}"
        if mild_alert:
            alert += f" | {mild_alert}"
        return {"action": "escalated", "reply": reply, "alert": alert}
    else:
        reply = build_refund_order_not_found(order_id)
        return {"action": "reply", "reply": reply, "alert": mild_alert}


def _normalize_logistics_row(order_id: str, row: dict) -> dict:
    """统一 CSV 和 Playwright 两种返回格式"""
    if row.get("source") == "playwright":
        # Playwright 格式 → 补充 CSV 字段
        csv_row = check_logistics(order_id)
        if csv_row:
            row["last_location"] = csv_row.get("last_location", "未知")
            row["last_time"] = csv_row.get("last_time", "")
            row["carrier"] = csv_row.get("carrier", row.get("carrier", ""))
            row["tracking_number"] = csv_row.get("tracking_number", row.get("tracking_number", ""))
        else:
            row["last_location"] = "物流查询"
            row["last_time"] = ""
    return row


def _handle_logistics_intent(order_id: str, mild_alert: str = "") -> dict:
    """处理物流查询意图（优先 Playwright，降级 CSV）"""
    row = check_logistics_online(order_id)
    if row:
        row = _normalize_logistics_row(order_id, row)
        reply = build_logistics_reply(order_id, row)
    else:
        reply = build_logistics_not_found(order_id)
    return {"action": "reply", "reply": reply, "alert": mild_alert}


# 取消 vs 退款分拆（李敏红线：未发货→取消，已发货→退款）
CANCEL_KEYWORDS = ("取消", "不想要", "不太想要", "不要了")
REFUND_KEYWORDS = ("退款", "退")
HUMAN_KEYWORDS = ("人工", "免单", "赔偿", "优惠券")


def process_message(customer_msg: str, order_id: str | None = None) -> dict:
    """
    处理单条客户消息，返回回复内容和告警记录。

    策略：
    1. 情绪检测（最高优先级）
    2. 关键词快路径：退款/订货号/人工
    3. DeepSeek 语义理解（补漏）
    """
    # ====== 第1步：情绪检测 ======
    emotion = check_emotion(customer_msg, order_id)

    # severe（愤怒/威胁/关键词命中）→ 拦截业务，直接告警
    if emotion.get("severity") == "severe":
        return {
            "action": "alert_human",
            "reply": "",
            "alert": emotion["alert_message"],
        }

    # mild（轻微不满）→ 不拦截，但记下告警信息附加到结果
    mild_alert = emotion["alert_message"] if emotion.get("severity") == "mild" else ""

    # ====== 第2步：关键词快路径 ======
    msg = customer_msg.strip()
    extracted = _extract_order_id(msg) or order_id

    # 快路径A：取消订单（未发货→取消，已发货→转退款流程）
    if any(kw in msg for kw in CANCEL_KEYWORDS):
        if not extracted:
            return {
                "action": "reply",
                "reply": "您好，请提供您的订单号，例如「取消 ORD012」",
                "alert": mild_alert,
            }
        cancel_result = handle_cancel(extracted)
        if cancel_result["decision"] == "cancelled":
            reply = build_cancel_success_reply(extracted)
            return {"action": "reply", "reply": reply, "alert": mild_alert}
        elif cancel_result["decision"] == "redirect_to_refund":
            # 已发货→转入退款流程
            return _handle_refund_intent(extracted, customer_msg, mild_alert)
        else:
            reply = build_refund_order_not_found(extracted)
            return {"action": "reply", "reply": reply, "alert": mild_alert}

    # 快路径B：退款（已发货诉求，走200元规则）
    if any(kw in msg for kw in REFUND_KEYWORDS):
        return _handle_refund_intent(extracted, customer_msg, mild_alert)

    # 快路径C：有订单号 → 查物流
    if extracted:
        return _handle_logistics_intent(extracted, mild_alert)

    # 快路径D：转人工（含免单/赔偿等需人工处理的需求）
    if any(kw in msg for kw in HUMAN_KEYWORDS):
        return {
            "action": "escalated",
            "reply": "🔄 正在为您转接人工客服，请稍候……",
            "alert": "客户请求转人工客服" + (f" | {mild_alert}" if mild_alert else ""),
        }

    # ====== 第2.5步：垃圾输入检测（省钱，不调DeepSeek） ======
    if _is_garbage_input(msg):
        logger.info("垃圾输入拦截: %s", msg[:30])
        return {
            "action": "reply",
            "reply": "您好，请描述您的问题，例如输入订单号查询物流或申请退款。",
            "alert": mild_alert,
        }

    # ====== 第3步：DeepSeek 语义理解（慢路径） ======
    intent_result = classify_intent(msg)
    if intent_result.get("success"):
        intent = intent_result.get("intent", "other")
        ds_order = intent_result.get("order_id") or extracted

        logger.info("DeepSeek 意图路由: %s → %s", msg[:30], intent)

        if intent == "cancel":
            # DeepSeek 识别为取消 → 走取消流程
            if not ds_order:
                return {
                    "action": "reply",
                    "reply": "您好，请提供您的订单号，例如「取消 ORD012」",
                    "alert": mild_alert,
                }
            cancel_result = handle_cancel(ds_order)
            if cancel_result["decision"] == "cancelled":
                return {"action": "reply", "reply": build_cancel_success_reply(ds_order), "alert": mild_alert}
            elif cancel_result["decision"] == "redirect_to_refund":
                return _handle_refund_intent(ds_order, customer_msg, mild_alert)
            else:
                return {"action": "reply", "reply": build_refund_order_not_found(ds_order), "alert": mild_alert}
        elif intent == "refund":
            return _handle_refund_intent(ds_order, customer_msg, mild_alert)
        elif intent == "logistics":
            if ds_order:
                return _handle_logistics_intent(ds_order, mild_alert)
            return {
                "action": "reply",
                "reply": "您好，请提供您的订单号，我帮您查询物流信息。",
                "alert": mild_alert,
            }
        elif intent == "human":
            return {
                "action": "escalated",
                "reply": "🔄 正在为您转接人工客服，请稍候……",
                "alert": "客户请求转人工客服（DeepSeek识别）" + (f" | {mild_alert}" if mild_alert else ""),
            }

    # 兜底：欢迎引导
    return {
        "action": "reply",
        "reply": build_greeting(),
        "alert": mild_alert,
    }


if __name__ == "__main__":
    """交互式测试入口"""
    print("=" * 50)
    print("智能客服小智 v2.0  输入消息测试，输入 q 退出")
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
