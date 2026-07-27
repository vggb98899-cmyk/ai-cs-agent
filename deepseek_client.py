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


def generate_refund_reply(order_id: str, amount: float, customer_msg: str) -> str:
    """
    用 DeepSeek 生成退款通过的拟人化回复。

    Args:
        order_id: 订单号
        amount: 退款金额
        customer_msg: 客户原始消息（用于参考语气）

    Returns:
        生成的回复文本，API 失败时返回模板文本
    """
    client = _get_client()
    if not client:
        logger.warning("DeepSeek 未配置，使用模板回复")
        return _fallback_refund_reply(order_id, amount)

    prompt = (
        "你是电商客服小智，性格亲切温和。客户申请退款已自动审核通过。\n"
        "请根据以下信息，生成一段简短、温暖的退款确认回复（不超过 100 字）：\n"
        "- 礼貌但不过度热情，像真人客服在说话\n"
        "- 告知退款已通过、金额、到账时间\n"
        "- 结合客户原始消息的语气适当安抚\n"
        "- 不要使用过多表情符号，1-2个即可\n"
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
                        f"退款金额：¥{amount:.2f}\n"
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


def _fallback_refund_reply(order_id: str, amount: float) -> str:
    """API 失败时的模板兜底"""
    return (
        f"✅ 您好，订单 {order_id}（¥{amount:.2f}）的退款申请已自动审核通过。\n"
        f"退款金额将在 1-3 个工作日内原路返回，请耐心等待。"
    )
