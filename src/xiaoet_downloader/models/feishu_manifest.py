#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import Optional

from ..api.feishu import FeishuBitableClient


class FeishuManifest:
    """飞书多维表格下载清单，跨设备共享下载状态"""

    def __init__(self, client: FeishuBitableClient, product_id: str, course_name: str):
        self._client = client
        self._product_id = product_id
        self._course_name = course_name

    @classmethod
    def load(cls, feishu_config, product_id: str, course_name: str) -> 'FeishuManifest':
        client = FeishuBitableClient(
            app_id=feishu_config.app_id,
            app_secret=feishu_config.app_secret,
            app_token=feishu_config.bitable_app_token,
            table_id=feishu_config.table_id,
        )
        return cls(client, product_id, course_name)

    def is_completed(self, resource_id: str) -> bool:
        return self._client.is_completed(self._product_id, resource_id)

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

    def is_ppt_downloaded(self, resource_id: str) -> bool:
        return self._client.is_ppt_downloaded(self._product_id, resource_id)

    def mark_ppt_count(self, resource_id: str, count: int) -> None:
        self._client.mark_ppt_count(self._product_id, resource_id, count)

    def mark_ppt_empty(self, resource_id: str) -> None:
        self._client.mark_ppt_empty(self._product_id, resource_id)

    def save(self) -> None:
        pass  # 数据实时写入云端，无需本地持久化
