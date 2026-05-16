#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import subprocess
import time
import requests
from ..utils.logger import logger

LOGIN_PAGE = "https://study.xiaoe-tech.com/#/wx"


def check_cookie_valid(cookie: str, app_id: str, user_agent: str) -> bool:
    """调 API 判断 cookie 是否有效"""
    if not cookie:
        return False
    try:
        url = f"https://{app_id}.h5.xiaoeknow.com/xe.micro_page.navigation.get/1.0.0"
        resp = requests.post(
            url,
            headers={
                'cookie': cookie,
                'User-Agent': user_agent,
                'Content-Type': 'application/json'
            },
            data=json.dumps({"app_id": app_id, "agent_type": 1, "app_version": 0}),
            timeout=10
        )
        if resp.status_code != 200:
            return False
        data = resp.json()
        return data.get('code') == 0 and data.get('data', {}).get('user_id')
    except Exception:
        return False


def qrcode_login(app_id: str, user_agent: str) -> str:
    """Playwright 打开微信登录页，用户扫码后返回 cookie 字符串"""
    from playwright.sync_api import sync_playwright

    logger.info("正在后台获取登录二维码...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()

        try:
            page.goto(LOGIN_PAGE, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # 勾选「已阅读并同意」复选框（二维码需要勾选后才显示）
            try:
                # 等页面渲染完，尝试多种方式勾选
                time.sleep(1)
                checked = False

                # 方式1: 找原生 checkbox input
                checkbox = page.locator('input[type="checkbox"]').first
                try:
                    checkbox.wait_for(state="attached", timeout=5000)
                    checkbox.check(force=True)
                    checked = True
                    logger.info("✓ 已勾选协议复选框 (input)")
                except Exception:
                    pass

                # 方式2: 页面可能使用自定义组件，用 evaluate 勾选
                if not checked:
                    try:
                        page.evaluate("""
                            () => {
                                const cb = document.querySelector('input[type="checkbox"]');
                                if (cb && !cb.checked) {
                                    cb.click();
                                    return true;
                                }
                                // 尝试找 el-checkbox 组件
                                const el = document.querySelector('.el-checkbox');
                                if (el) el.click();
                                return true;
                            }
                        """)
                        checked = True
                        logger.info("✓ 已勾选协议复选框 (js)")
                    except Exception:
                        pass

                # 方式3: 点击 label 左侧（避开协议链接文字）
                if not checked:
                    label = page.locator("label").filter(has_text="已阅读并同意").first
                    label.wait_for(state="visible", timeout=5000)
                    box = label.bounding_box()
                    if box:
                        page.mouse.click(box['x'] + 15, box['y'] + box['height'] / 2)
                        checked = True
                        logger.info("✓ 已勾选协议复选框 (label+offset)")

                if not checked:
                    raise Exception("所有方式均失败")
            except Exception:
                logger.warning("未能自动勾选协议复选框，请手动勾选后扫码")

            # 等待二维码 canvas 出现，截取二维码元素
            try:
                canvas = page.wait_for_selector("canvas", timeout=10000)
                if canvas:
                    canvas.screenshot(path="qrcode.png")
            except Exception:
                page.screenshot(path="qrcode.png")

            logger.info("正在打开二维码图片...")
            subprocess.run(['open', 'qrcode.png'], check=False)

            # 等待扫码后页面跳转（离开微信登录页）
            try:
                page.wait_for_url(
                    lambda url: '/wx' not in url and url != LOGIN_PAGE and 'login' not in url.lower(),
                    timeout=120000
                )
                logger.info("✓ 扫码成功，页面已跳转")
            except Exception:
                logger.error("等待扫码超时（2分钟），请重试")
                return ""

            # 跳转到课程域名触发跨域 SSO，确保 xiaoeknow.com 的 cookie 被种下
            logger.info("正在同步登录态到课程域...")
            time.sleep(2)
            app_domain = f"https://{app_id}.h5.xiaoeknow.com"
            try:
                page.goto(app_domain, wait_until="domcontentloaded", timeout=15000)
                time.sleep(3)
                logger.info(f"✓ 已访问 {app_domain}")
            except Exception as e:
                logger.warning(f"访问课程域失败: {e}")

            # 提取所有 cookie
            all_cookies = context.cookies()
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in all_cookies)
            domains = set(c.get('domain', '') for c in all_cookies)
            logger.info(f"✓ 获取到 {len(all_cookies)} 个 cookie，覆盖域: {domains}")

            return cookie_str

        finally:
            browser.close()
