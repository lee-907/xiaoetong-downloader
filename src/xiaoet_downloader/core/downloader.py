#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import threading
import requests
import m3u8
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple
from m3u8.model import SegmentList, Segment, find_key

from ..models.config import XiaoetConfig
from ..models.resource import Resource, VideoMetadata, DownloadResult, DownloadStatus
from ..utils.file_utils import FileUtils
from ..utils.logger import logger


class VideoDownloader:
    """视频下载器"""

    def __init__(self, config: XiaoetConfig):
        """初始化下载器"""
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.user_agent,
            'Referer': f'https://{config.app_id}.h5.xiaoeknow.com/'
        })

    def download_m3u8_video(self, resource: Resource, play_url: str,
                            download_dir: str, nocache: bool = False,
                            max_workers: int = 3) -> DownloadResult:
        """
        下载m3u8视频

        Args:
            resource: 视频资源对象
            play_url: m3u8播放地址
            download_dir: 下载目录
            nocache: 是否忽略缓存
            max_workers: 并行下载线程数

        Returns:
            DownloadResult: 下载结果
        """
        if not play_url:
            return DownloadResult(resource, False, "无效的播放地址")

        # TS 缓存放在课程目录下的 cache/ 子目录
        lesson_dir = os.path.join(download_dir, FileUtils.sanitize_filename(resource.title))
        resource_dir = os.path.join(lesson_dir, 'cache')
        FileUtils.ensure_dir(resource_dir)

        try:
            resource.download_status = DownloadStatus.DOWNLOADING
            logger.info(f"开始下载视频: {resource.title}")

            response = self.session.get(play_url)
            if response.status_code != 200:
                return DownloadResult(resource, False, f"获取m3u8内容失败: HTTP {response.status_code}")

            try:
                media = m3u8.loads(response.text)
            except Exception as e:
                return DownloadResult(resource, False, f"解析m3u8内容失败: {str(e)}")

            if not media.data.get('segments'):
                return DownloadResult(resource, False, "m3u8文件中没有找到视频片段")

            url_prefix = self._get_url_prefix(play_url)
            total_segments = len(media.data['segments'])
            logger.info(f"总计 {total_segments} 个视频片段")

            # 预扫描：区分已缓存和需下载的片段
            segment_map = {}  # index -> Segment
            pending_indices = []  # 需要下载的 index 列表
            downloaded_count = 0

            # 保存原始 URI（用于下载），然后改为本地文件名（用于本地 m3u8）
            original_uris = {}  # index -> original URI
            for index, segment in enumerate(media.data['segments']):
                ts_file = os.path.join(resource_dir, f'v_{index}.ts')
                original_uris[index] = segment['uri']  # 保存原始 URI（含鉴权参数）
                segment['uri'] = f'v_{index}.ts'        # 本地 m3u8 用本地文件名
                seg = Segment(base_uri=None, keyobject=find_key(segment.get('key', {}), media.keys), **segment)
                segment_map[index] = seg

                if not nocache and os.path.exists(ts_file):
                    downloaded_count += 1
                else:
                    pending_indices.append(index)

            # 并行下载未缓存的片段
            if pending_indices:
                lock = threading.Lock()
                completed = 0
                total_pending = len(pending_indices)

                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    for index in pending_indices:
                        seg_data = dict(media.data['segments'][index])
                        seg_data['uri'] = original_uris[index]  # 恢复原始 URI 用于下载
                        ts_file = os.path.join(resource_dir, f'v_{index}.ts')
                        future = executor.submit(
                            self._download_segment, seg_data, ts_file, url_prefix,
                            index + 1, total_segments
                        )
                        futures[future] = index

                    for future in as_completed(futures):
                        success = future.result()
                        with lock:
                            completed += 1
                            if success:
                                downloaded_count += 1
                            # 更新进度条
                            current_total = downloaded_count
                            percent = current_total / total_segments
                            filled_length = int(50 * percent)
                            bar = '█' * filled_length + '░' * (50 - filled_length)
                            sys.stdout.write(f'\r[{bar}] {percent:.1%} ({current_total}/{total_segments})')
                            sys.stdout.flush()

            # 构建最终进度条（下载部分完成后）
            if pending_indices:
                print()

            # 按索引顺序构建 segments 列表
            segments = SegmentList()
            for index in sorted(segment_map.keys()):
                segments.append(segment_map[index])

            changed = len(pending_indices) > 0 and downloaded_count > 0
            complete = downloaded_count == total_segments

            # 生成本地m3u8文件
            m3u8_file = os.path.join(resource_dir, 'video.m3u8')
            if changed or not os.path.exists(m3u8_file):
                media.segments = segments
                with open(m3u8_file, 'w', encoding='utf8') as f:
                    f.write(media.dumps())

            # 保存元数据
            metadata = VideoMetadata(
                title=resource.title,
                complete=complete,
                total_segments=total_segments,
                downloaded_segments=downloaded_count
            )
            FileUtils.save_json(metadata.to_dict(), os.path.join(resource_dir, 'metadata.json'))

            resource.download_status = DownloadStatus.COMPLETED if complete else DownloadStatus.FAILED

            if complete:
                logger.info(f"视频下载完成: {resource.title}")
                return DownloadResult(resource, True, "下载完成", lesson_dir)
            else:
                logger.warning(f"视频下载不完整: {resource.title} ({downloaded_count}/{total_segments})")
                return DownloadResult(resource, False, f"下载不完整 ({downloaded_count}/{total_segments})")

        except Exception as e:
            resource.download_status = DownloadStatus.FAILED
            logger.error(f"下载视频时发生错误: {str(e)}")
            return DownloadResult(resource, False, f"下载失败: {str(e)}")

    def _get_url_prefix(self, play_url: str) -> str:
        """获取URL前缀"""
        if 'v.f230' in play_url:
            return play_url.split('v.f230')[0]
        return play_url.rsplit('/', 1)[0] + '/'

    def _download_segment(self, segment: dict, ts_file: str, url_prefix: str,
                          current: int, total: int, max_retries: int = 3) -> bool:
        """
        下载单个视频片段

        Args:
            segment: 片段信息
            ts_file: 本地文件路径
            url_prefix: URL前缀
            current: 当前片段序号
            total: 总片段数
            max_retries: 最大重试次数

        Returns:
            bool: 是否下载成功
        """
        segment_url = segment.get('uri')
        if not segment_url.startswith('http'):
            segment_url = url_prefix + segment_url

        last_status = None
        for retry_count in range(max_retries):
            try:
                response = self.session.get(segment_url, timeout=30)
                last_status = response.status_code
                if response.status_code == 200:
                    temp_file = ts_file + '.tmp'
                    with open(temp_file, 'wb') as f:
                        f.write(response.content)
                    os.rename(temp_file, ts_file)
                    return True
                else:
                    if retry_count < max_retries - 1:
                        time.sleep(1)
            except requests.exceptions.RequestException:
                if retry_count < max_retries - 1:
                    time.sleep(1)

        logger.warning(f"[{current}/{total}] 下载失败 (HTTP {last_status}): {segment_url[:120]}")
        return False

    def download_document(self, document_url: str, document_file: str, max_retries: int = 3) -> bool:
        """下载文档"""
        if os.path.exists(document_file):
            return True

        for retry_count in range(max_retries):
            try:
                response = self.session.get(document_url, timeout=30)
                if response.status_code == 200:
                    temp_file = document_file + '.tmp'
                    with open(temp_file, 'wb') as f:
                        f.write(response.content)
                    os.rename(temp_file, document_file)
                    return True
                else:
                    if retry_count < max_retries - 1:
                        time.sleep(1)
            except requests.exceptions.RequestException:
                if retry_count < max_retries - 1:
                    time.sleep(1)
        logger.error(f"文档下载失败，已重试 {max_retries} 次: {document_url[:120]}")
        return False
