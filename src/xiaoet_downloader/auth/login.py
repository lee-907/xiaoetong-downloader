#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
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


def qrcode_login(user_agent: str) -> str:
    """Playwright 打开微信登录页，用户扫码后返回 cookie 字符串"""
    from playwright.sync_api import sync_playwright

    logger.info("正在启动浏览器获取登录二维码...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()

        try:
            page.goto(LOGIN_PAGE, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            # 点击「已阅读并同意」复选框，使二维码出现
            try:
                agree_checkbox = page.locator("label").filter(has_text="已阅读并同意")
                agree_checkbox.wait_for(state="visible", timeout=10000)
                agree_checkbox.click()
                logger.info("✓ 已勾选协议复选框")
            except Exception:
                logger.warning("未能自动勾选协议复选框，请手动勾选")

            # 等待二维码 canvas 出现
            try:
                page.wait_for_selector("canvas", timeout=10000)
            except Exception:
                pass

            # 截图二维码
            page.screenshot(path="qrcode.png")
            logger.info("=" * 50)
            logger.info("请打开 qrcode.png 查看微信登录二维码并用微信扫码")
            logger.info("=" * 50)

            # 等待扫码后跳转到首页
            try:
                page.wait_for_url("**/home**", timeout=120000)
                logger.info("✓ 扫码成功，页面已跳转")
            except Exception:
                logger.error("等待扫码超时（2分钟），请重试")
                browser.close()
                return ""

            time.sleep(2)

            # 提取所有 cookie
            cookies = context.cookies()
            cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
            logger.info(f"✓ 获取到 {len(cookies)} 个 cookie")

            return cookie_str

        finally:
            browser.close()
