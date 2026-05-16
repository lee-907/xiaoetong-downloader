#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
from datetime import datetime, timezone
from typing import Optional


class DownloadManifest:
    """下载清单，记录已完成的资源"""

    def __init__(self, course_dir: str, product_id: str):
        self._filepath = os.path.join(course_dir, 'manifest.json')
        self._product_id = product_id
        self._resources: dict = {}

    @classmethod
    def load(cls, course_dir: str, product_id: str) -> 'DownloadManifest':
        """从课程目录加载清单，不存在则创建空的"""
        manifest = cls(course_dir, product_id)
        if os.path.exists(manifest._filepath):
            try:
                with open(manifest._filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                manifest._resources = data.get('resources', {})
            except (json.JSONDecodeError, IOError):
                manifest._resources = {}
        return manifest

    def save(self):
        """写入清单文件"""
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        with open(self._filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'product_id': self._product_id,
                'resources': self._resources
            }, f, ensure_ascii=False, indent=2)

    def is_completed(self, resource_id: str) -> bool:
        """判断资源是否已完成下载"""
        entry = self._resources.get(resource_id)
        return entry is not None and entry.get('status') == 'completed'

    def mark_completed(self, resource_id: str, title: str, file_path: str, rtype: str):
        """标记资源下载完成"""
        self._resources[resource_id] = {
            'title': title,
            'type': rtype,
            'file_path': file_path,
            'status': 'completed',
            'downloaded_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        }
