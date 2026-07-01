#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from urllib.parse import urlparse
from typing import List, Dict, Tuple, Optional, Any

from ..models.config import XiaoetConfig
from ..models.resource import Resource, DownloadResult, ResourceType
from ..models.manifest import DownloadManifest
from ..models.feishu_manifest import FeishuManifest
from ..api.client import XiaoetAPIClient
from ..core.downloader import VideoDownloader
from ..core.transcoder import VideoTranscoder
from ..utils.file_utils import FileUtils
from ..utils.logger import logger


class XiaoetDownloadManager:
    """小鹅通下载管理器"""

    def __init__(self, config: XiaoetConfig):
        """初始化下载管理器"""
        self.config = config
        self.api_client = XiaoetAPIClient(config)
        self.downloader = VideoDownloader(config)
        self._user_id: Optional[str] = None

    def _get_user_id(self) -> Optional[str]:
        """获取用户ID（单次请求，缓存复用）"""
        if self._user_id:
            return self._user_id
        navigation_info = self.api_client.get_micro_navigation_info()
        self._user_id = navigation_info.get('user_id')
        if not self._user_id:
            logger.error("无法获取用户ID")
        return self._user_id

    def download_all_courses(self, nocache: bool = False, auto_transcode: bool = True,
                             force: bool = False, course_filter: str = '') -> Dict[str, Any]:
        """
        下载配置中所有课程的增量内容

        Args:
            course_filter: 可选，按 product_name 或 product_id 过滤，只下载匹配的课程

        Returns:
            {'courses': {product_name: {...}}, 'total_success': int, 'total_failed': int, 'total_skipped': int}
        """
        all_results = {'courses': {}, 'total_success': 0, 'total_failed': 0, 'total_skipped': 0}

        # 过滤课程
        products = self.config.products
        if course_filter:
            products = [
                p for p in products
                if course_filter == p.get('product_name', '') or course_filter == p.get('product_id', '')
            ]
            if not products:
                logger.warning(f"未找到匹配的课程: {course_filter}")
                return all_results

        for i, product in enumerate(products):
            course_dir = self.config.get_course_dir(product)
            logger.info(f"\n{'='*50}")
            logger.info(f"[{i+1}/{len(products)}] 课程: {product['product_name']} ({product['product_id']})")
            logger.info(f"{'='*50}")

            results = self.download_course(product, course_dir, nocache, auto_transcode, force)
            all_results['courses'][product['product_name']] = results
            all_results['total_success'] += len(results.get('success', []))
            all_results['total_failed'] += len(results.get('failed', []))
            all_results['total_skipped'] += len(results.get('skipped', []))

        # 汇总打印
        self._print_all_summary(all_results)
        return all_results

    def download_course(self, product: dict, course_dir: str, nocache: bool = False,
                        auto_transcode: bool = True, force: bool = False) -> Dict[str, List[DownloadResult]]:
        """
        下载单个课程的增量内容

        Args:
            product: 产品信息 {'product_name': ..., 'product_id': ...}
            course_dir: 课程下载目录
            nocache: 是否忽略 TS 缓存
            auto_transcode: 是否自动转码
            force: 是否忽略 manifest 强制下载

        Returns:
            {'success': [...], 'failed': [...], 'skipped': [...]}
        """
        product_id = product['product_id']
        results = {'success': [], 'failed': [], 'skipped': []}

        try:
            # 加载下载清单
            FileUtils.ensure_dir(course_dir)
            if self.config.manifest_backend == "feishu":
                manifest = FeishuManifest.load(self.config.feishu, product_id, product['product_name'])
            else:
                manifest = DownloadManifest.load(course_dir, product_id)
            transcoder = VideoTranscoder(course_dir)

            # 获取用户信息（缓存复用）
            user_id = self._get_user_id()
            if not user_id:
                return results

            # 获取课程资源列表
            logger.info(f"正在获取课程资源列表 (product_id={product_id})...")
            resource_items = self.api_client.get_column_items(self.config.app_id, product_id)
            if not resource_items:
                logger.warning(f"未找到课程资源: {product['product_name']}")
                return results

            lens = len(resource_items)
            logger.info(f"找到 {lens} 个资源")

            for index, (resource_id, resource_title) in enumerate(resource_items):
                try:
                    # 增量跳过：manifest 中已完成的资源（但仍检查 PPT）
                    if not force and manifest.is_completed(resource_id):
                        logger.info(f"[{index + 1}/{lens}] 跳过 (已下载): {resource_title} ({resource_id})")
                        results['skipped'].append(DownloadResult(
                            Resource(resource_id, resource_title), True, "已下载"
                        ))
                        if resource_id.startswith('l_'):
                            if hasattr(manifest, 'is_ppt_downloaded') and manifest.is_ppt_downloaded(resource_id):
                                continue
                            ppt_count = self._download_ppt_images(
                                Resource(resource_id, resource_title, ResourceType.LIVE),
                                course_dir, user_id
                            )
                            if ppt_count and hasattr(manifest, 'mark_ppt_count'):
                                manifest.mark_ppt_count(resource_id, ppt_count)
                            elif ppt_count == 0 and hasattr(manifest, 'mark_ppt_empty'):
                                manifest.mark_ppt_empty(resource_id)
                        continue

                    if resource_title in self.config.filter:
                        logger.info(f"[{index + 1}/{lens}] 跳过 (filter): {resource_title} ({resource_id})")
                        continue

                    if resource_id.startswith('i_'):
                        logger.info(f"[{index + 1}/{lens}] 笔记/图文，暂不支持下载: {resource_title}")
                        continue
                    elif resource_id.startswith('d_'):
                        resource_type = ResourceType.DOCUMENT
                    elif resource_id.startswith('l_'):
                        resource_type = ResourceType.LIVE
                    elif resource_id.startswith('v_'):
                        resource_type = ResourceType.VIDEO
                    else:
                        logger.info(f"[{index + 1}/{lens}] 未知资源类型: {resource_title} ({resource_id})")
                        continue

                    logger.info(f"[{index + 1}/{lens}] {resource_title} ({resource_id})")

                    resource = Resource(
                        resource_id=resource_id,
                        title=resource_title,
                        resource_type=resource_type
                    )

                    result = self._download_resource(
                        resource, course_dir, user_id, product_id,
                        nocache, auto_transcode, transcoder
                    )
                    if result.success:
                        manifest.mark_completed(
                            resource_id, resource_title,
                            result.file_path, resource_type.value
                        )
                        manifest.save()
                        results['success'].append(result)
                        if resource_type == ResourceType.LIVE:
                            if not hasattr(manifest, 'is_ppt_downloaded') or not manifest.is_ppt_downloaded(resource_id):
                                ppt_count = self._download_ppt_images(resource, course_dir, user_id)
                                if ppt_count and hasattr(manifest, 'mark_ppt_count'):
                                    manifest.mark_ppt_count(resource_id, ppt_count)
                    else:
                        results['failed'].append(result)

                except Exception as e:
                    error_msg = f"处理 {resource_title} 时出错: {str(e)}"
                    logger.error(error_msg)
                    results['failed'].append(DownloadResult(
                        Resource(resource_id, resource_title), False, error_msg
                    ))

        except Exception as e:
            logger.error(f"下载课程时发生错误: {str(e)}")

        self._print_summary(product['product_name'], results)
        return results

    def download_single_video(self, resource_id: str, nocache: bool = False,
                              auto_transcode: bool = True) -> DownloadResult:
        """
        下载单个视频，自动遍历所有课程找到匹配的资源
        """
        try:
            user_id = self._get_user_id()
            if not user_id:
                return DownloadResult(Resource(resource_id, "未知"), False, "无法获取用户ID")

            # 判断资源类型
            if resource_id.startswith('l_'):
                resource_type = ResourceType.LIVE
            elif resource_id.startswith('v_'):
                resource_type = ResourceType.VIDEO
            else:
                resource_type = ResourceType.AUDIO

            # 在所有课程中查找该资源
            title = resource_id
            matched_product = None
            for product in self.config.products:
                try:
                    items = self.api_client.get_column_items(self.config.app_id, product['product_id'])
                    for rid, rtitle in items:
                        if rid == resource_id:
                            title = rtitle
                            matched_product = product
                            break
                    if matched_product:
                        break
                except Exception:
                    pass

            if not matched_product:
                return DownloadResult(Resource(resource_id, title), False, "未找到匹配的课程")

            resource = Resource(resource_id=resource_id, title=title, resource_type=resource_type)
            course_dir = self.config.get_course_dir(matched_product)
            FileUtils.ensure_dir(course_dir)
            transcoder = VideoTranscoder(course_dir)

            result = self._download_resource(
                resource, course_dir, user_id, matched_product['product_id'],
                nocache, auto_transcode, transcoder
            )
            if result.success:
                if self.config.manifest_backend == "feishu":
                    manifest = FeishuManifest.load(self.config.feishu, matched_product['product_id'], matched_product['product_name'])
                else:
                    manifest = DownloadManifest.load(course_dir, matched_product['product_id'])
                manifest.mark_completed(resource_id, title, result.file_path, resource_type.value)
                manifest.save()
                if resource_type == ResourceType.LIVE:
                    if not hasattr(manifest, 'is_ppt_downloaded') or not manifest.is_ppt_downloaded(resource_id):
                        ppt_count = self._download_ppt_images(resource, course_dir, user_id)
                        if ppt_count and hasattr(manifest, 'mark_ppt_count'):
                            manifest.mark_ppt_count(resource_id, ppt_count)
            return result

        except Exception as e:
            logger.error(f"下载视频 {resource_id} 时出错: {str(e)}")
            return DownloadResult(Resource(resource_id, "未知"), False, str(e))

    def _download_resource(self, resource: Resource, course_dir: str, user_id: str,
                           product_id: str, nocache: bool, auto_transcode: bool,
                           transcoder: VideoTranscoder) -> DownloadResult:
        """下载单个资源（文档或视频/直播），返回 DownloadResult"""
        if resource.resource_type == ResourceType.DOCUMENT:
            doc_info = self._get_document_url(resource, product_id)
            if not doc_info:
                return DownloadResult(resource, False, "无法获取文档地址")
            document_title, document_url = doc_info
            final_path = os.path.join(course_dir, document_title)
            if self.downloader.download_document(document_url, final_path):
                return DownloadResult(resource, True, "下载完成", final_path)
            return DownloadResult(resource, False, "文档下载失败")

        # 视频/直播: 获取播放地址
        play_url = None
        if resource.resource_type == ResourceType.LIVE:
            play_url = self._get_live_m3u8_url(resource)
        if not play_url:
            play_url = self._get_play_url(resource, user_id, product_id)
        if not play_url:
            return DownloadResult(resource, False, "无法获取播放地址")

        download_result = self.downloader.download_m3u8_video(
            resource, play_url, course_dir, nocache, self.config.max_workers
        )
        if download_result.success and auto_transcode:
            return transcoder.transcode_video(resource, course_dir)
        return download_result

    def _get_play_url(self, resource: Resource, user_id: str, product_id: str) -> Optional[str]:
        """获取播放URL"""
        try:
            video_details = self.api_client.get_video_detail_info(resource.resource_id, product_id)
            if not video_details:
                logger.warning(f"无法获取视频 {resource.title} 的详情信息")
                return None
            play_sign = video_details.get('play_sign')

            if not play_sign:
                logger.warning(f"无法获取视频 {resource.title} 的播放标识")
                return None

            resource.play_sign = play_sign
            play_list_dict = self.api_client.get_play_url(user_id, play_sign)
            result = self.api_client.get_best_quality_url(play_list_dict)
            if not result:
                logger.warning(f"未找到可用的清晰度: {resource.title}")
                return None
            play_url, quality = result

            if play_url:
                logger.info(f"获取到 {quality} 播放地址")
                resource.play_url = play_url
                return play_url
            else:
                logger.warning(f"无法获取视频 {resource.title} 的播放地址")
                return None

        except Exception as e:
            logger.error(f"获取播放URL时出错: {str(e)}")
            return None

    def _get_document_url(self, resource: Resource, product_id: str):
        """获取文档URL"""
        try:
            document_details = self.api_client.get_document_detail_info(resource.resource_id, product_id)
            file_name = document_details.get('file_name')
            file_url = document_details.get('file_url')
            if not file_name or not file_url:
                logger.warning(f"无法获取文件 {resource.title} 的资源 (file_name={file_name}, file_url={file_url})")
                return None
            return file_name, file_url
        except Exception as e:
            logger.error(f"获取文档URL时出错: {str(e)}")
            return None

    def _get_live_m3u8_url(self, resource: Resource) -> Optional[str]:
        """获取直播回放 m3u8 地址"""
        try:
            live_details = self.api_client.get_lookback_detail_info(resource.resource_id)

            # room_id 由 get_interaction_images 自动从 msg/list 响应中发现，此处无需提取

            if isinstance(live_details, dict):
                # redirect/uRL 是登录重定向，不是视频地址，忽略
                for key in ('line_sharpness',):
                    val = live_details.get(key)
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, dict):
                                url = item.get('url', '')
                                if url and url.startswith('http'):
                                    return url
                            elif isinstance(item, str) and item.startswith('http'):
                                return item
            elif isinstance(live_details, list):
                for item in live_details:
                    if isinstance(item, dict):
                        for sharpness in item.get('line_sharpness', []):
                            url = sharpness.get('url') if isinstance(sharpness, dict) else sharpness
                            if url and url.startswith('http'):
                                return url
                    elif isinstance(item, str) and item.startswith('http'):
                        return item
            logger.debug(f"未从直播回放数据中提取到 m3u8 地址: {resource.resource_id}")
        except Exception as e:
            logger.error(f"获取直播回放URL时出错: {str(e)}")
        return None

    def _download_ppt_images(self, resource: Resource, course_dir: str, user_id: str):
        """下载直播互动区的 PPT 图片（room_id 由 API 层自动发现）"""
        try:
            images = self.api_client.get_interaction_images(
                resource.resource_id, resource.room_id or '', user_id
            )
            if not images:
                return 0

            lesson_dir = os.path.join(course_dir, FileUtils.sanitize_filename(
                FileUtils.sortable_title(resource.title)))
            ppt_dir = os.path.join(lesson_dir, 'ppt')
            FileUtils.ensure_dir(ppt_dir)

            logger.info(f"  下载 {len(images)} 张 PPT 图片...")
            for i, img_url in enumerate(images):
                path_part = urlparse(img_url).path
                ext = os.path.splitext(path_part)[1] or '.png'
                if ext.lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                    ext = '.png'
                img_file = os.path.join(ppt_dir, f'{i+1:02d}{ext}')
                if os.path.exists(img_file):
                    continue
                self.downloader.download_document(img_url, img_file)
            # 统计实际文件数，过滤 macOS ._ 隐藏文件
            actual_count = sum(1 for f in os.listdir(ppt_dir)
                             if os.path.isfile(os.path.join(ppt_dir, f)) and not f.startswith('._'))
            logger.info(f"  PPT 图片已保存到 {ppt_dir} ({actual_count} 张)")
            return actual_count
        except Exception as e:
            logger.warning(f"下载 PPT 图片失败: {e}")
            return 0

    def _print_summary(self, course_name: str, results: Dict[str, List[DownloadResult]]) -> None:
        """打印单个课程处理结果摘要"""
        success_count = len(results.get('success', []))
        failed_count = len(results.get('failed', []))
        skipped_count = len(results.get('skipped', []))
        total = success_count + failed_count + skipped_count

        logger.info(f"\n{course_name} 处理完成:")
        logger.info(f"  新增下载: {success_count}")
        logger.info(f"  跳过(已下载): {skipped_count}")
        if failed_count:
            logger.info(f"  失败: {failed_count}")
            for result in results['failed']:
                logger.error(f"    - {result.resource.title} ({result.resource.resource_id}): {result.message}")

    def _print_all_summary(self, all_results: Dict[str, Any]) -> None:
        """打印所有课程汇总"""
        logger.info(f"\n{'='*50}")
        logger.info("全部课程处理完成:")
        logger.info(f"  总新增下载: {all_results['total_success']}")
        logger.info(f"  总跳过: {all_results['total_skipped']}")
        logger.info(f"  总失败: {all_results['total_failed']}")
        logger.info(f"{'='*50}")

    def check_environment(self) -> bool:
        """检查运行环境"""
        logger.info("检查运行环境...")

        # 检查 ffmpeg
        if VideoTranscoder('').check_ffmpeg_availability():
            logger.info("✓ ffmpeg 可用")
        else:
            logger.warning("⚠ ffmpeg 不可用，将无法进行视频转码")

        # 检查所有课程下载目录
        for product in self.config.products:
            try:
                course_dir = self.config.get_course_dir(product)
                FileUtils.ensure_dir(course_dir)
                logger.info(f"✓ 下载目录已准备: {course_dir}")
            except Exception as e:
                logger.error(f"✗ 无法创建下载目录 {course_dir}: {str(e)}")
                return False

        return True
