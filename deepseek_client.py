"""
DeepSeek API 客户端
两个核心能力：
1. 语义级情绪分析（比关键词匹配更准）
2. 退款话术生成（拟人化安慰，不再模板化）

依赖配置层读取 API Key
"""

import logging
from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_ENABLED

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    """懒加载 OpenAI 客户端"""
    global _client
    if _client is None and DEEPSEEK_ENABLED:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    return _client


def analyze_sentiment(customer_msg: str) -> dict:
    """
    用 DeepSeek 分析客户消息情绪。

    Returns:
        dict: {
            "success": True | False,   # API 调用是否成功
            "is_negative": bool,       # 是否是负面情绪
            "sentiment": str,          # 情绪分类
            "should_alert": bool,      # 是否应该告警
            "reason": str,             # 分析理由
        }
    """
    client = _get_client()
    if not client:
        logger.warning("DeepSeek 未配置，跳过语义分析")
        return {
            "success": False,
            "is_negative": False,
            "sentiment": "unknown",
            "should_alert": False,
            "reason": "API 未配置",
        }

    prompt = (
        "你是一个客服情绪分析系统。分析以下客户消息，判断：\n"
        "1. 客户的真实情绪是什么（正常咨询 / 轻微不满 / 愤怒 / 威胁）\n"
        "2. 是否需要转人工处理\n"
        "3. 简要说明判断理由\n\n"
        "请严格按照 JSON 格式返回，不要包含其他文字：\n"
        '{"sentiment": "愤怒", "should_alert": true, "reason": "客户使用辱骂词汇，情绪激烈"}'
    )

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": customer_msg},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        # 清理可能的多余标记
        text = text.replace("```json", "").replace("```", "").strip()

        import json
        result = json.loads(text)
        result["success"] = True
        is_negative = result.get("sentiment") in ("愤怒", "威胁", "轻微不满")
        result["is_negative"] = is_negative
        logger.info("DeepSeek 情绪分析: %s → %s", customer_msg[:30], result)
        return result

    except Exception as e:
        logger.error("DeepSeek 情绪分析异常: %s", str(e))
        return {
            "success": False,
            "is_negative": False,
            "sentiment": "unknown",
            "should_alert": False,
            "reason": f"API 调用失败: {str(e)[:50]}",
        }


def generate_refund_reply(order_id: str, amount: float, customer_msg: str,
                           order_status: str = "", logistics_status: str = "") -> str:
    """
    用 DeepSeek 生成退款通过的拟人化回复。

    Args:
        order_id: 订单号
        amount: 退款金额
        customer_msg: 客户原始消息
        order_status: 订单状态（如"已发货未签收"）
        logistics_status: 物流状态（如"派送中"）

    Returns:
        生成的回复文本，API 失败时返回模板文本
    """
    client = _get_client()
    if not client:
        logger.warning("DeepSeek 未配置，使用模板回复")
        return _fallback_refund_reply(order_id, amount)

    prompt = (
        "你是电商客服小智，性格亲切温和。客户申请退款已自动审核通过。\n"
        "请根据以下**真实订单数据**生成回复。\n"
        "⚠️ 重要规则：只能基于下方提供的真实数据说话，禁止编造物流状态或发货情况。\n"
        "如果客户说的和真实数据不一致，委婉纠正而非附和。\n"
        "生成一段简短、温暖的退款确认回复（不超过 100 字）：\n"
        "- 礼貌但不过度热情\n"
        "- 告知退款已通过、金额、到账时间\n"
        "- 基于真实状态回复（如已发货则告知会拦截退回）\n"
    )

    status_info = f"订单状态：{order_status}" if order_status else ""
    logistics_info = f"物流状态：{logistics_status}" if logistics_status else ""
    facts = f"{status_info}\n{logistics_info}".strip()

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"客户消息：{customer_msg}\n"
                        f"订单号：{order_id}\n"
                        f"退款金额：¥{amount:.2f}\n"
                        f"{facts}\n"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=300,
        )
        reply = resp.choices[0].message.content.strip()
        logger.info("DeepSeek 生成退款回复成功: %s", reply[:50])
        return reply

    except Exception as e:
        logger.error("DeepSeek 生成回复异常: %s", str(e))
        return _fallback_refund_reply(order_id, amount)


def generate_escalated_reply(
    order_id: str,
    reason: str,
    customer_msg: str,
    amount: float | None = None,
) -> str:
    """
    用 DeepSeek 生成转人工话术（V2-02：带情绪安抚的个性化引导）。

    Args:
        order_id: 订单号
        reason: 转人工原因（如"金额¥250超过限额¥200"）
        customer_msg: 客户原话
        amount: 退款金额（可选）

    Returns:
        生成的回复文本，API 失败时返回模板文本
    """
    client = _get_client()
    if not client:
        logger.warning("DeepSeek 未配置，使用模板回复")
        return _fallback_escalated_reply(order_id, reason)

    prompt = (
        "你是电商客服小智，性格亲切温和。客户的退款申请未能自动处理，需要转接人工客服。\n"
        "请根据以下信息生成一段回复（不超过 100 字）：\n"
        "- 语气亲切，像真人客服在说话\n"
        "- 简要说明为什么不能自动处理（引用原因）\n"
        "- 告知已转人工，请客户耐心等待\n"
        "- 不要过度使用表情符号，1个即可\n"
    )

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"客户消息：{customer_msg}\n"
                        f"订单号：{order_id}\n"
                        f"退款金额：¥{amount:.2f}\n转人工原因：{reason}\n"
                        if amount else
                        f"客户消息：{customer_msg}\n"
                        f"订单号：{order_id}\n"
                        f"转人工原因：{reason}\n"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=300,
        )
        reply = resp.choices[0].message.content.strip()
        logger.info("DeepSeek 生成转人工话术成功: %s", reply[:50])
        return reply

    except Exception as e:
        logger.error("DeepSeek 生成转人工话术异常: %s", str(e))
        return _fallback_escalated_reply(order_id, reason)


def _fallback_escalated_reply(order_id: str, reason: str) -> str:
    """转人工话术模板兜底"""
    return (
        f"🔄 您好，订单 {order_id} 的退款申请因「{reason}」"
        f"已转交人工客服处理，请耐心等待。\n"
        f"我们会尽快为您处理！"
    )


def generate_human_transfer_reply(customer_msg: str) -> str:
    """
    用 DeepSeek 生成通用转人工话术（非退款场景）。
    用于"人工""免单""赔偿"等请求。
    """
    client = _get_client()
    if not client:
        logger.warning("DeepSeek 未配置，使用模板回复")
        return _fallback_human_reply()

    prompt = (
        "你是电商客服小智，性格亲切温和。客户提出了需要人工处理的需求。\n"
        "请生成一段回复（不超过 80 字）：\n"
        "- 确认收到客户需求\n"
        "- 告知已转接人工客服\n"
        "- 语气亲切自然\n"
        "- 使用1个表情符号\n"
    )

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"客户消息：{customer_msg}"},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        reply = resp.choices[0].message.content.strip()
        logger.info("DeepSeek 生成转人工话术成功: %s", reply[:50])
        return reply
    except Exception as e:
        logger.error("DeepSeek 生成转人工话术异常: %s", str(e))
        return _fallback_human_reply()


def _fallback_human_reply() -> str:
    """通用转人工模板兜底"""
    return "🔄 正在为您转接人工客服，请稍候……"


def classify_intent(customer_msg: str) -> dict:
    """
    用 DeepSeek 理解客户意图。

    Returns:
        dict: {
            "success": bool,
            "intent": "refund" | "logistics" | "human" | "greeting" | "other",
            "order_id": str | None,
            "reason": str,
        }
    """
    client = _get_client()
    if not client:
        logger.warning("DeepSeek 未配置，跳过意图识别")
        return {"success": False, "intent": "other", "order_id": None, "reason": "API 未配置"}

    prompt = (
        "你是电商客服系统的意图识别引擎。分析客户消息，判断客户最想做什么。\n\n"
        "意图类型：\n"
        "- cancel: 取消订单、不想要了、不要了（未发货诉求）\n"
        "- refund: 退款、退货（已发货诉求）\n"
        "- logistics: 查物流、快递到哪了、什么时候到\n"
        "- human: 转人工、找人工客服、投诉、要赔偿、要免单、要优惠券、要求退款之外的任何特殊处理\n"
        "- greeting: 打招呼、问在不在、闲聊、问有没有货\n"
        "- other: 以上都不属于\n\n"
        "注意：客户要求「免单」「赔偿」「优惠券」等不属于标准退款流程的，归类为 human。\n\n"
        "请严格按照 JSON 格式返回，不要包含其他文字：\n"
        '{"intent": "refund", "order_id": "ORD003", "reason": "客户明确说不要了"}'
    )

    try:
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": customer_msg},
            ],
            temperature=0.1,
            max_tokens=200,
        )
        text = resp.choices[0].message.content.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        import json
        result = json.loads(text)
        result["success"] = True
        logger.info("DeepSeek 意图识别: %s → %s", customer_msg[:30], result.get("intent"))
        return result

    except Exception as e:
        logger.error("DeepSeek 意图识别异常: %s", str(e))
        return {"success": False, "intent": "other", "order_id": None, "reason": str(e)[:50]}


def _fallback_refund_reply(order_id: str, amount: float) -> str:
    """API 失败时的模板兜底"""
    return (
        f"✅ 您好，订单 {order_id}（¥{amount:.2f}）的退款申请已自动审核通过。\n"
        f"退款金额将在 1-3 个工作日内原路返回，请耐心等待。"
    )
