"""
业务层：Playwright 物流轨迹抓取（V2-01）
目标：打开快递100，输入单号，抓取物流轨迹
失败时优雅降级（返回 None，调用方回退到 CSV）

李敏要求：本地能跑通一次就算成功，被 ban 了降级不要报错
"""

import logging
import re

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright 未安装，物流抓取将始终降级到 CSV")


def _parse_kuaidi100(page) -> str | None:
    """从快递100页面提取物流轨迹文本"""
    try:
        selectors = [
            ".result-wrap .item",
            ".text-time",
            ".result-list .item",
            ".kd-content .item",
            '[class*="result"]',
        ]
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=5000)
                break
            except Exception:
                continue

        body_text = page.inner_text("body")
        lines = body_text.split("\n")
        trajectory_lines = []

        # 提取包含时间戳的轨迹行
        for line in lines:
            line = line.strip()
            if re.search(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}", line):
                trajectory_lines.append(line)

        if trajectory_lines:
            return "\n".join(trajectory_lines)

        # 兜底：返回页面文本前500字
        body_preview = body_text[:500].strip()
        if body_preview and len(body_preview) > 20:
            return body_preview

        return None
    except Exception as e:
        logger.warning("解析快递100页面异常: %s", str(e))
        return None


def _get_text_safe(page, selector: str, default: str = "") -> str:
    """安全获取元素文本"""
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else default
    except Exception:
        return default


def fetch_logistics(tracking_number: str, carrier: str = "") -> dict | None:
    """
    用 Playwright 模拟打开快递100，查询物流轨迹。
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.info("Playwright 不可用，降级 CSV")
        return None

    logger.info("Playwright 抓取: %s (%s)", tracking_number, carrier)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.set_default_timeout(15000)

            try:
                # 1. 打开快递100
                logger.info("打开快递100...")
                page.goto("https://www.kuaidi100.com/", wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=10000)

                # 2. 找到输入框填入单号
                page.wait_for_selector("#input", timeout=8000)
                page.fill("#input", tracking_number)
                logger.info("已填入单号: %s", tracking_number)

                # 3. 按回车触发查询
                page.press("#input", "Enter")
                logger.info("已按回车查询")

                # 4. 等待结果加载
                page.wait_for_timeout(3000)
                trajectory_text = _parse_kuaidi100(page)

                if trajectory_text:
                    # 检查是否真实轨迹（排除"暂无轨迹"等空结果）
                    no_result_keywords = ("暂无", "抱歉", "没有找到", "不存在")
                    if any(kw in trajectory_text for kw in no_result_keywords):
                        logger.warning("单号不存在或暂无轨迹: %s", tracking_number)
                        return None

                    status = "已签收" if "签收" in trajectory_text else "运输中"
                    logger.info("Playwright 抓取成功")
                    return {
                        "status": status,
                        "trajectory": trajectory_text,
                        "source": "playwright",
                    }

                logger.warning("未能提取到轨迹文本")
                return None

            except Exception as e:
                logger.warning("Playwright 抓取异常: %s", str(e))
                return None
            finally:
                browser.close()

    except Exception as e:
        logger.error("Playwright 启动异常: %s", str(e))
        return None
