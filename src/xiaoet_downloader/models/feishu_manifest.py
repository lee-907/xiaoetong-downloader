#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import Dict, Optional, Set

from ..api.feishu import FeishuBitableClient


class FeishuManifest:
    """飞书多维表格下载清单，跨设备共享下载状态"""

    def __init__(self, client: FeishuBitableClient, product_id: str, course_name: str,
                 completed_ids: Set[str], ppt_cache: Dict[str, int]):
        self._client = client
        self._product_id = product_id
        self._course_name = course_name
        self._completed_ids = completed_ids  # 已完成的 resource_id 集合
        self._ppt_cache = ppt_cache          # resource_id -> PPT数量 (含 -1 表示空)

    @classmethod
    def load(cls, feishu_config, product_id: str, course_name: str) -> 'FeishuManifest':
        client = FeishuBitableClient(
            app_id=feishu_config.app_id,
            app_secret=feishu_config.app_secret,
            app_token=feishu_config.bitable_app_token,
            table_id=feishu_config.table_id,
        )
        records = client.fetch_product_records(product_id)
        completed_ids: Set[str] = set()
        ppt_cache: Dict[str, int] = {}
        for rid, fields in records.items():
            if fields.get("status") == "completed":
                completed_ids.add(rid)
            ppt_val = fields.get("PPT数量")
            if ppt_val is not None:
                ppt_cache[rid] = ppt_val
        return cls(client, product_id, course_name, completed_ids, ppt_cache)

    def is_completed(self, resource_id: str) -> bool:
        return resource_id in self._completed_ids

    def mark_completed(self, resource_id: str, title: str, file_path: str, rtype: str) -> None:
        file_size = 0
        if file_path and os.path.isfile(file_path):
            try:
                file_size = os.path.getsize(file_path)  # bytes, API 层会转为 MB
            except OSError:
                pass

        self._client.mark_completed(
            product_id=self._product_id,
            resource_id=resource_id,
            title=title,
            course_name=self._course_name,
            file_path=file_path,
            rtype=rtype,
            file_size=file_size,
        )
        self._completed_ids.add(resource_id)

    def is_ppt_downloaded(self, resource_id: str) -> bool:
        count = self._ppt_cache.get(resource_id)
        return count is not None and (count > 0 or count == -1)

    def mark_ppt_count(self, resource_id: str, count: int) -> None:
        self._client.mark_ppt_count(self._product_id, resource_id, count)
        self._ppt_cache[resource_id] = count

    def mark_ppt_empty(self, resource_id: str) -> None:
        self._client.mark_ppt_empty(self._product_id, resource_id)
        self._ppt_cache[resource_id] = -1

    def save(self) -> None:
        pass  # 数据实时写入云端，无需本地持久化
