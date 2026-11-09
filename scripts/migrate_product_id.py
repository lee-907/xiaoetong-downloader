#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把飞书下载记录从一个 product_id 迁移到另一个 product_id。

使用场景：小鹅通续费后机构更换了课程 ID。飞书去重键是
(product_id, resource_id)，不迁移的话下载器会把已下载资源当成新资源重下一遍。

用法：
    # 预演（只统计，不写入）
    python scripts/migrate_product_id.py --old p_xxx --new course_xxx

    # 实际执行
    python scripts/migrate_product_id.py --old p_xxx --new course_xxx --apply

    # 迁移旧 ID 下全部记录（默认只迁移新课程中仍存在的资源）
    python scripts/migrate_product_id.py --old p_xxx --new course_xxx --apply --all
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from xiaoet_downloader import XiaoetConfig
from xiaoet_downloader.api.client import XiaoetAPIClient
from xiaoet_downloader.api.feishu import FeishuBitableClient

BATCH_SIZE = 500  # 飞书 batch_update 单次上限


def main() -> int:
    parser = argparse.ArgumentParser(description='迁移飞书下载记录的 product_id')
    parser.add_argument('--old', required=True, help='旧 product_id')
    parser.add_argument('--new', required=True, help='新 product_id')
    parser.add_argument('--config', default='config.json', help='配置文件路径 (默认: config.json)')
    parser.add_argument('--apply', action='store_true', help='实际写入（默认只预演）')
    parser.add_argument('--all', action='store_true',
                        help='迁移旧 ID 下全部记录（默认只迁移新课程中仍存在的资源）')
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f'配置文件不存在: {args.config}')
        return 1

    cfg = XiaoetConfig.from_file(str(config_path))
    fs = cfg.feishu
    fc = FeishuBitableClient(fs.app_id, fs.app_secret, fs.bitable_app_token, fs.table_id)

    old_items = fc.fetch_product_record_items(args.old)
    print(f'旧 ID {args.old} 记录数: {len(old_items)}')

    targets = old_items
    if not args.all:
        new_ids = {rid for rid, _ in XiaoetAPIClient(cfg).get_column_items(cfg.app_id, args.new)}
        print(f'新课程 {args.new} 资源数: {len(new_ids)}')
        targets = [
            item for item in old_items
            if fc._get_text(item.get('fields', {}), 'resource_id') in new_ids
        ]

    print(f'待迁移记录数: {len(targets)}')
    if not args.apply:
        print('预演结束（未写入）。加 --apply 实际执行。')
        return 0

    records = [
        {'record_id': item['record_id'], 'fields': {'product_id': args.new}}
        for item in targets
    ]
    for start in range(0, len(records), BATCH_SIZE):
        chunk = records[start:start + BATCH_SIZE]
        fc.batch_update_records(chunk)
        print(f'已更新 {min(start + BATCH_SIZE, len(records))}/{len(records)}')

    remaining_old = len(fc.fetch_product_record_items(args.old))
    migrated_new = len(fc.fetch_product_record_items(args.new))
    print(f'迁移完成: 旧 ID 剩余 {remaining_old} 条, 新 ID 现有 {migrated_new} 条')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
