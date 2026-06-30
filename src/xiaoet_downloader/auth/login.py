#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
import requests
from typing import Optional
from urllib.parse import quote

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
        user_id = data.get('data', {}).get('user_id', '')
        return data.get('code') == 0 and user_id and not user_id.startswith('anonymous')
    except (requests.RequestException, json.JSONDecodeError, ValueError):
        return False


# ============================================================
# Helpers
# ============================================================

def _build_direct_login_url(app_id: str, product_id: str) -> str:
    """构造带 LoginCard=login_wechat 的直接扫码登录 URL（使用店铺实际域名 h5.xet.pomoho.com）"""
    if product_id.startswith('course_'):
        path = 'ecourse'
    elif product_id.startswith('p_'):
        path = 'column'
    else:
        path = 'ecourse'
    domain = f"{app_id}.h5.xet.pomoho.com"
    course_url = (
        f"https://{domain}/p/course/{path}/{product_id}"
        f"?l_program=xe_know_pc&sub_course_list_mode=0"
    )
    encoded = quote(course_url, safe='')
    return (
        f"https://{domain}/p/t/free/v1/basic-platform/"
        f"h5_basic/login/auth?LoginCard=login_wechat&redirect_url={encoded}"
    )


def _is_on_target_domain(url: str, app_id: str) -> bool:
    """是否在课程内容域"""
    return (
        f"{app_id}.h5.xiaoeknow.com" in url
        or f"{app_id}.h5.xet." in url
    )


def _is_auth_page(url: str) -> bool:
    """是否为登录/认证页面"""
    return '/login' in url or '/auth' in url


def _handle_checkbox(page):
    """尝试勾选协议复选框"""
    try:
        cb = page.locator('input[type="checkbox"]').first
        cb.wait_for(state="attached", timeout=3000)
        cb.check(force=True)
        logger.info("✓ 已勾选协议复选框")
        return
    except Exception:
        pass
    try:
        page.evaluate("""
            () => {
                const cb = document.querySelector('input[type="checkbox"]');
                if (cb && !cb.checked) { cb.click(); return true; }
                const el = document.querySelector('.el-checkbox');
                if (el) el.click();
                return true;
            }
        """)
        logger.info("✓ 已勾选协议复选框 (js)")
    except Exception:
        pass


def _save_qrcode_image(page) -> Optional[str]:
    """从页面提取二维码图片，保存为 PNG 临时文件，返回路径"""
    import tempfile, base64

    time.sleep(3)

    try:
        src = page.evaluate("""() => {
            const imgs = document.querySelectorAll('img');
            for (const img of imgs) {
                if (img.src && img.src.startsWith('data:image') && img.clientWidth > 100)
                    return img.src;
            }
            return null;
        }""")
    except Exception:
        src = None

    if not src:
        return None

    try:
        base64_data = src.split(",", 1)[1]
        qr_bytes = base64.b64decode(base64_data)
        path = tempfile.mktemp(suffix=".png", prefix="xiaoetong_qrcode_")
        with open(path, "wb") as f:
            f.write(qr_bytes)
        logger.info(f"✓ 二维码已保存: {path}")
        return path
    except Exception as e:
        logger.warning(f"保存二维码失败: {e}")
        return None


def _extract_cookies(context) -> str:
    """从浏览器 context 提取所有 cookie"""
    all_cookies = context.cookies()
    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in all_cookies)
    names = [c['name'] for c in all_cookies]
    logger.info(f"✓ 获取到 {len(all_cookies)} 个 cookie: {names}")
    logger.info(f"Cookie:\n{cookie_str}")
    return cookie_str


# ============================================================
# QR code login
# ============================================================

def qrcode_login(app_id: str, product_id: str, user_agent: str) -> str:
    """打开浏览器，直接导航到带 LoginCard=login_wechat 的登录页，
    用户扫码后 OAuth/SSO 链重定向到课程页，提取 cookie。

    product_id 为空时回退到旧版 study.xiaoe-tech.com/#/wx 扫码页。
    """
    from playwright.sync_api import sync_playwright

    logger.info("正在准备登录...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=user_agent)
        page = context.new_page()

        try:
            # ======== Step 1: 直接打开扫码页 ========

            if product_id:
                login_url = _build_direct_login_url(app_id, product_id)
            else:
                login_url = LOGIN_PAGE

            logger.info("打开微信扫码页...")
            page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            time.sleep(1)

            logger.info(f"当前页面: {page.url[:120]}...")

            # ======== Step 2: 复选框 ========

            _handle_checkbox(page)

            # 保存二维码图片供后续使用（如 Hermes 发飞书）
            _save_qrcode_image(page)

            # ======== Step 3: 等待扫码完成 ========

            logger.info("=" * 50)
            logger.info("请扫码登录（5分钟超时，终端或浏览器均可）")
            logger.info("=" * 50)

            pre_scan_url = page.url

            try:
                page.wait_for_url(
                    lambda url: url != pre_scan_url,
                    timeout=300000
                )
                logger.info(f"✓ 检测到跳转: {page.url[:120]}...")
                time.sleep(3)
                logger.info("✓ 登录完成")
            except Exception:
                logger.warning("等待超时（5分钟），尝试提取当前 Cookie...")

            # ======== Step 4: 提取 Cookie ========

            return _extract_cookies(context)

        finally:
            browser.close()
