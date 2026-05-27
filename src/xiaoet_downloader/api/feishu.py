#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import time
import socket
from datetime import datetime
from typing import Optional, Dict, Any

import requests

from ..utils.logger import logger


class FeishuBitableClient:
    """飞书多维表格 API 客户端"""

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str, app_token: str, table_id: str):
        self._app_id = app_id
        self._app_secret = app_secret
        self._app_token = app_token
        self._table_id = table_id
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._device = socket.gethostname()

    # ---- token ----

    def _get_access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        resp = self._request("POST", url, json={"app_id": self._app_id, "app_secret": self._app_secret}, auth_required=False)
        self._token = resp["tenant_access_token"]
        self._token_expires_at = time.time() + resp.get("expire", 7200)
        return self._token

    # ---- record CRUD ----

    def search_record(self, product_id: str, resource_id: str) -> Optional[Dict[str, Any]]:
        """按 product_id + resource_id 搜索记录，返回第一条匹配或 None"""
        url = f"{self.BASE_URL}/bitable/v1/apps/{self._app_token}/tables/{self._table_id}/records/search"
        body = {
            "filter": {
                "conjunction": "and",
                "conditions": [
                    {"field_name": "product_id", "operator": "is", "value": [product_id]},
                    {"field_name": "resource_id", "operator": "is", "value": [resource_id]},
                ],
            },
            "page_size": 1,
        }
        resp = self._request("POST", url, json=body)
        items = resp.get("data", {}).get("items", [])
        return items[0] if items else None

    def insert_record(self, fields: Dict[str, Any]) -> str:
        """新增一条记录，返回 record_id"""
        url = f"{self.BASE_URL}/bitable/v1/apps/{self._app_token}/tables/{self._table_id}/records"
        resp = self._request("POST", url, json={"fields": fields})
        return resp["data"]["record"]["record_id"]

    def update_record(self, record_id: str, fields: Dict[str, Any]) -> None:
        """更新已有记录"""
        url = f"{self.BASE_URL}/bitable/v1/apps/{self._app_token}/tables/{self._table_id}/records/{record_id}"
        self._request("PUT", url, json={"fields": fields})

    def upsert_record(self, product_id: str, resource_id: str, fields: Dict[str, Any]) -> None:
        """存在则更新，不存在则新增"""
        existing = self.search_record(product_id, resource_id)
        if existing:
            self.update_record(existing["record_id"], fields)
        else:
            self.insert_record(fields)

    # ---- high-level helpers ----

    def is_completed(self, product_id: str, resource_id: str) -> bool:
        record = self.search_record(product_id, resource_id)
        if not record:
            return False
        return record.get("fields", {}).get("status") == "completed"

    def mark_completed(self, product_id: str, resource_id: str, title: str,
                       course_name: str, file_path: str, rtype: str,
                       file_size: int = 0, error_message: str = "") -> None:
        fields = {
            "resource_id": resource_id,
            "title": title,
            "resource_type": rtype,
            "course_name": course_name,
            "product_id": product_id,
            "status": "completed",
            "device": self._device,
            "file_path": file_path,
            "file_size": round(file_size / (1024 * 1024), 1) if file_size else 0,
            "downloaded_at": int(time.time() * 1000),
        }
        ts = self._parse_class_date(title)
        if ts:
            fields["上课日期"] = ts
        if error_message:
            fields["error_message"] = error_message
        self.upsert_record(product_id, resource_id, fields)

    def mark_ppt_count(self, product_id: str, resource_id: str, count: int) -> None:
        existing = self.search_record(product_id, resource_id)
        if existing:
            self.update_record(existing["record_id"], {"PPT数量": count})

    def is_ppt_downloaded(self, product_id: str, resource_id: str) -> bool:
        """PPT 已处理（已下载或已确认为空），无需再调 API"""
        record = self.search_record(product_id, resource_id)
        if not record:
            return False
        count = record.get("fields", {}).get("PPT数量")
        return count is not None and (count > 0 or count == -1)

    def mark_ppt_empty(self, product_id: str, resource_id: str) -> None:
        """标记该直播无 PPT，后续跳过"""
        self.mark_ppt_count(product_id, resource_id, -1)

    @staticmethod
    def _parse_class_date(title: str):
        m = re.search(r'(\d{2,4})年(\d{1,2})月(\d{1,2})日', title)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            try:
                return int(datetime(y, mo, d).timestamp() * 1000)
            except ValueError:
                pass
        return None

    # ---- HTTP ----

    # ---- 一键初始化 ----

    @classmethod
    def init_table(cls, app_id: str, app_secret: str, existing_app_token: str = "") -> dict:
        """
        一键创建多维表格 + 下载记录表 + 全部字段。
        如果提供 existing_app_token，则复用已有的多维表格。

        Returns:
            {"app_token": "...", "table_id": "..."}
        """
        token = cls._get_token_static(app_id, app_secret)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # 1. 创建或复用多维表格
        if existing_app_token:
            app_token = existing_app_token
            logger.info(f"复用已有多维表格: {app_token}")
        else:
            resp = requests.post(
                f"{cls.BASE_URL}/bitable/v1/apps",
                headers=headers,
                json={"name": "小鹅通下载记录"},
                timeout=30,
            ).json()
            if resp.get("code") != 0:
                raise RuntimeError(f"创建多维表格失败: {resp.get('msg')}")
            app_token = resp["data"]["app"]["app_token"]
            logger.info(f"已创建多维表格: {app_token}")

        # 2. 创建表格
        resp = requests.post(
            f"{cls.BASE_URL}/bitable/v1/apps/{app_token}/tables",
            headers=headers,
            json={"table": {"name": "下载记录"}},
            timeout=30,
        ).json()
        if resp.get("code") != 0:
            raise RuntimeError(f"创建数据表失败: {resp.get('msg')}")
        table_id = resp["data"]["table_id"]
        logger.info(f"已创建数据表: {table_id}")

        # 3. 批量添加字段
        fields_def = [
            {"field_name": "resource_id", "type": 1},
            {"field_name": "title", "type": 1},
            {"field_name": "resource_type", "type": 3,
             "property": {"options": [
                 {"name": "VIDEO", "color": 1},
                 {"name": "LIVE", "color": 2},
                 {"name": "DOCUMENT", "color": 3},
                 {"name": "AUDIO", "color": 4},
             ]}},
            {"field_name": "course_name", "type": 1},
            {"field_name": "product_id", "type": 1},
            {"field_name": "status", "type": 3,
             "property": {"options": [
                 {"name": "completed", "color": 1},
                 {"name": "failed", "color": 2},
                 {"name": "skipped", "color": 3},
             ]}},
            {"field_name": "device", "type": 1},
            {"field_name": "file_path", "type": 1},
            {"field_name": "file_size", "type": 2},
            {"field_name": "downloaded_at", "type": 5},
            {"field_name": "上课日期", "type": 5},
            {"field_name": "error_message", "type": 1},
        ]

        field_url = f"{cls.BASE_URL}/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        for fd in fields_def:
            requests.post(field_url, headers=headers, json=fd, timeout=30)

        logger.info(f"已添加 {len(fields_def)} 个字段")

        # 4. 删除默认字段
        resp = requests.get(field_url, headers=headers, timeout=30).json()
        for item in resp.get("data", {}).get("items", []):
            if item.get("field_name", "").startswith("字段"):
                field_id = item["field_id"]
                requests.delete(
                    f"{field_url}/{field_id}", headers=headers, timeout=30
                )
                logger.info(f"已删除默认字段: {field_id}")

        return {"app_token": app_token, "table_id": table_id}

    @staticmethod
    def _get_token_static(app_id: str, app_secret: str) -> str:
        resp = requests.post(
            f"https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=30,
        ).json()
        if resp.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {resp.get('msg')}")
        return resp["tenant_access_token"]

    # ---- HTTP ----

    def _request(self, method: str, url: str, json: Optional[dict] = None,
                 auth_required: bool = True, max_retries: int = 3) -> dict:
        headers = {}
        if auth_required:
            headers["Authorization"] = f"Bearer {self._get_access_token()}"

        last_exc = None
        for attempt in range(max_retries):
            try:
                resp = requests.request(method, url, headers=headers, json=json, timeout=30)
                data = resp.json()
                code = data.get("code", -1)

                if code == 0:
                    return data

                if code == 9999167 or (resp.status_code == 429 and attempt < max_retries - 1):
                    wait = 2 ** attempt
                    logger.warning(f"飞书 API 限流，{wait}s 后重试 (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue

                msg = data.get("msg", "unknown error")
                raise RuntimeError(f"飞书 API 错误 (code={code}): {msg}")

            except requests.RequestException as e:
                last_exc = e
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"飞书 API 网络错误，{wait}s 后重试: {e}")
                    time.sleep(wait)
                else:
                    raise RuntimeError(f"飞书 API 不可达: {e}") from e

        raise RuntimeError(f"飞书 API 不可达: {last_exc}")
