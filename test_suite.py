"""
回归测试套件：把李敏扔过来的所有测试场景固化下来
每次改完代码跑一遍，通过的✅ 挂了的❌ 一目了然
"""

import sys
sys.path.insert(0, r"D:\Reasonix\ai-cs-agent")

from main import process_message

PASS = 0
FAIL = 0
CASES = []


def test(scene: str, msg: str, expect_action: str, expect_hint: str = ""):
    """注册一个测试用例"""
    CASES.append((scene, msg, expect_action, expect_hint))


def run_all():
    global PASS, FAIL
    print("=" * 60)
    print("  智能客服回归测试套件")
    print(f"  共 {len(CASES)} 个用例")
    print("=" * 60)

    for scene, msg, expect_action, expect_hint in CASES:
        result = process_message(msg)
        action = result["action"]
        reply = result.get("reply", "")
        alert = result.get("alert", "")

        # 判断是否通过
        action_ok = action == expect_action
        hint_ok = not expect_hint or expect_hint in reply or expect_hint in alert

        if action_ok and hint_ok:
            PASS += 1
            status = "✅"
        else:
            FAIL += 1
            status = "❌"
            # 分析失败原因
            detail = f"期望动作={expect_action}，实际={action}"
            if expect_hint and not hint_ok:
                detail += f" | 期望包含「{expect_hint}」"
                detail += f" | 实际回复={reply[:80] if reply else alert[:80]}"

        # 一行展示
        action_icon = {"reply": "🤖", "escalated": "🔄", "alert_human": "🚨"}
        icon = action_icon.get(action, "❓")
        action_label = {"reply": "自动回复", "escalated": "转人工", "alert_human": "告警"}

        print(f"\n{status} {scene}")
        print(f"  客户: {msg}")
        print(f"  系统: {icon} {action_label.get(action, action)}")
        if status == "❌":
            print(f"  原因: {detail}")
        if status == "✅" and expect_hint:
            preview = reply[:60] if reply else alert[:60]
            print(f"  验证: 包含「{expect_hint}」✓")

    # 汇总
    print()
    print("=" * 60)
    total = PASS + FAIL
    rate = PASS / total * 100 if total else 0
    print(f"  通过: {PASS}/{total}  ({rate:.0f}%)")
    if FAIL:
        print(f"  失败: {FAIL}")
    print("=" * 60)
    return FAIL == 0


# ============================================================
# 注册测试用例（来自李敏的历史测试 + 日常场景）
# ============================================================

# ---- 物流查询 ----
test("物流查询-正常", "亲，帮忙看下 ORD008 到哪了？急用。",
     "reply", "派送中")

# ---- 退款：规则判断 ----
test("退款-符合条件自动同意", "退款 ORD005",
     "reply", "审核通过")

test("退款-超金额转人工", "退款 ORD004",
     "escalated", "金额")

test("退款-超期转人工", "ORD010 买了半个月了，一直没用，能退吗？",
     "escalated", "超过")

test("退款-已签收转人工", "ORD009 昨天刚收到，我要退",
     "escalated", "状态")

test("退款-无订单号", "我要退款",
     "reply", "订单号")

# ---- 取消订单 ----
test("取消-未发货直接取消", "取消 ORD012",
     "reply", "已成功取消")

test("取消-已发货转退款", "取消 ORD005",
     "reply", "审核通过")

# ---- 退款：语义理解 ----
test("退款-不想要了（无关键词）", "我不想要了，如果没到货的话",
     "reply", "订单号")

# ---- 情绪告警 ----
test("情绪-脏话告警", "我操了，你们的东西有问题",
     "alert_human", "操")

test("情绪-差评告警", "你们客服是死了吗？再不回消息我就差评了",
     "alert_human", "差评")

test("情绪-曝光告警", "ORD011 就是垃圾！再不退款我直接去消协曝光你们！！",
     "alert_human", "曝光")

test("情绪-语义告警（无关键词）", "你们这质量也太差了吧，用了三天就坏了",
     "escalated", "人工客服")

# ---- 转人工 ----
test("转人工-明确请求", "妈的转人工",
     "alert_human", "妈的")

test("转人工-免单", "可以免单吗",
     "escalated", "人工")

test("转人工-赔偿（DeepSeek识别）", "东西坏了能赔我吗",
     "escalated", "DeepSeek识别")

# ---- 其他 ----
test("其他-闲聊", "有货吗",
     "reply", "智能客服小智")

test("其他-空消息", "你好",
     "reply", "智能客服小智")


if __name__ == "__main__":
    run_all()
