#!/usr/bin/env python3
"""批量给已下载资源目录加 YYYYMMDD- 前缀，方便按日期排序"""
import os, re, json, sys
from pathlib import Path

def main():
    # 读 config 拿 download_dir
    config_path = Path(__file__).parent.parent / 'config.json'
    if not config_path.exists():
        print(f'未找到 config.json: {config_path}')
        sys.exit(1)
    with open(config_path) as f:
        cfg = json.load(f)
    base = cfg.get('download_dir', 'download')

    if not os.path.isdir(base):
        print(f'下载目录不存在: {base}')
        sys.exit(1)

    renamed = 0
    skipped = 0

    for root, dirs, _files in os.walk(base):
        for d in dirs:
            old_path = os.path.join(root, d)

            # 跳过已有前缀的
            if re.match(r'\d{8}-', d):
                skipped += 1
                continue

            # 提取日期（支持 23年 和 2023年 两种年份格式，日可选）
            m = re.search(r'(\d{2,4})年(\d{1,2})月(\d{1,2})日?', d)
            if not m:
                continue

            y, mo, day = m.group(1), m.group(2), m.group(3)
            if len(y) == 2:
                y = '20' + y
            if not day:
                day = '01'
            new_name = f'{y}{mo.zfill(2)}{day.zfill(2)}-{d}'
            new_path = os.path.join(root, new_name)

            if os.path.exists(new_path):
                print(f'  SKIP (已存在): {new_name[:70]}')
                continue

            os.rename(old_path, new_path)
            renamed += 1
            print(f'  {d[:60]}')
            print(f'  → {new_name[:60]}')
            print()

    print(f'\n完成: {renamed} 个重命名, {skipped} 个已有前缀跳过')

if __name__ == '__main__':
    main()
