#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import List, Dict, Tuple, Optional, Any

from ..models.config import XiaoetConfig
from ..models.resource import Resource, DownloadResult, ResourceType, DownloadStatus
from ..models.manifest import DownloadManifest
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

    def download_all_courses(self, nocache: bool = False, auto_transcode: bool = True,
                             force: bool = False) -> Dict[str, Any]:
        """
        下载配置中所有课程的增量内容

        Returns:
            {'courses': {product_name: {...}}, 'total_success': int, 'total_failed': int, 'total_skipped': int}
        """
        all_results = {'courses': {}, 'total_success': 0, 'total_failed': 0, 'total_skipped': 0}

        for i, product in enumerate(self.config.products):
            course_dir = self.config.get_course_dir(product)
            logger.info(f"\n{'='*50}")
            logger.info(f"[{i+1}/{len(self.config.products)}] 课程: {product['product_name']} ({product['product_id']})")
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
            manifest = DownloadManifest.load(course_dir, product_id)
            transcoder = VideoTranscoder(course_dir)

            # 获取用户信息
            navigation_info = self.api_client.get_micro_navigation_info()
            user_id = navigation_info.get('user_id')
            if not user_id:
                logger.error("无法获取用户ID")
                return results

            # 获取课程资源列表
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
                            ppt_dir = os.path.join(course_dir, FileUtils.sanitize_filename(resource_title), 'ppt')
                            if not os.path.exists(ppt_dir):
                                self._download_ppt_images(
                                    Resource(resource_id, resource_title, ResourceType.LIVE),
                                    course_dir, user_id
                                )
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

                    if resource_type == ResourceType.DOCUMENT:
                        doc_info = self._get_document_url(resource, product_id)
                        if not doc_info:
                            results['failed'].append(DownloadResult(resource, False, "无法获取文档地址"))
                            continue
                        document_title, document_url = doc_info
                        final_path = os.path.join(course_dir, document_title)
                        if self.downloader.download_document(document_url, final_path):
                            manifest.mark_completed(resource_id, resource_title, final_path, 'document')
                            manifest.save()
                            results['success'].append(DownloadResult(resource, True, "下载完成", final_path))
                        else:
                            results['failed'].append(DownloadResult(resource, False, "文档下载失败"))
                    elif resource_type in (ResourceType.VIDEO, ResourceType.LIVE):
                        if resource_type == ResourceType.LIVE:
                            play_url = self._get_live_m3u8_url(resource)
                            if not play_url:
                                play_url = self._get_play_url(resource, user_id, product_id)
                        else:
                            play_url = self._get_play_url(resource, user_id, product_id)
                        if not play_url:
                            results['failed'].append(DownloadResult(resource, False, "无法获取播放地址"))
                            continue

                        download_result = self.downloader.download_m3u8_video(
                            resource, play_url, course_dir, nocache, self.config.max_workers
                        )
                        if download_result.success and auto_transcode:
                            transcode_result = transcoder.transcode_video(
                                resource, course_dir, index + 1
                            )
                            if transcode_result.success:
                                manifest.mark_completed(
                                    resource_id, resource_title,
                                    transcode_result.file_path, resource_type.value
                                )
                                manifest.save()
                                results['success'].append(transcode_result)
                                # 下载 PPT 图片
                                if resource_type == ResourceType.LIVE:
                                    self._download_ppt_images(resource, course_dir, user_id)
                            else:
                                results['failed'].append(transcode_result)
                        elif download_result.success:
                            manifest.mark_completed(
                                resource_id, resource_title,
                                download_result.file_path, resource_type.value
                            )
                            manifest.save()
                            results['success'].append(download_result)
                            if resource_type == ResourceType.LIVE:
                                self._download_ppt_images(resource, course_dir, user_id)
                        else:
                            results['failed'].append(download_result)

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

        Args:
            resource_id: 资源ID
            nocache: 是否忽略缓存
            auto_transcode: 是否自动转码

        Returns:
            DownloadResult: 下载结果
        """
        try:
            # 获取用户信息
            navigation_info = self.api_client.get_micro_navigation_info()
            user_id = navigation_info.get('user_id')
            if not user_id:
                return DownloadResult(Resource(resource_id, "未知"), False, "无法获取用户ID")

            # 判断资源类型
            if resource_id.startswith('l_'):
                resource_type = ResourceType.LIVE
            elif resource_id.startswith('v_'):
                resource_type = ResourceType.VIDEO
            else:
                resource_type = ResourceType.AUDIO

            # 在所有课程中查找该资源的标题
            title = resource_id  # 默认用 ID
            for product in self.config.products:
                try:
                    items = self.api_client.get_column_items(self.config.app_id, product['product_id'])
                    for rid, rtitle in items:
                        if rid == resource_id:
                            title = rtitle
                            break
                except Exception:
                    pass

            resource = Resource(
                resource_id=resource_id,
                title=title,
                resource_type=resource_type
            )

            # 尝试在所有课程中获取播放地址
            play_url = None
            matched_product = None
            for product in self.config.products:
                try:
                    if resource_type == ResourceType.LIVE:
                        play_url = self._get_live_m3u8_url(resource)
                    if not play_url:
                        play_url = self._get_play_url(resource, user_id, product['product_id'])
                    if play_url:
                        matched_product = product
                        break
                except Exception:
                    continue

            if not play_url:
                return DownloadResult(resource, False, "无法获取播放地址")
            if not matched_product:
                return DownloadResult(resource, False, "未找到匹配的课程")

            course_dir = self.config.get_course_dir(matched_product)
            FileUtils.ensure_dir(course_dir)

            # 下载视频
            download_result = self.downloader.download_m3u8_video(
                resource, play_url, course_dir, nocache, self.config.max_workers
            )

            if download_result.success and auto_transcode:
                transcoder = VideoTranscoder(course_dir)
                result = transcoder.transcode_video(resource, course_dir, 0)
                if result.success:
                    manifest = DownloadManifest.load(course_dir, matched_product['product_id'])
                    manifest.mark_completed(resource_id, resource.title, result.file_path, resource_type.value)
                    manifest.save()
                return result

            if download_result.success:
                manifest = DownloadManifest.load(course_dir, matched_product['product_id'])
                manifest.mark_completed(resource_id, resource.title, download_result.file_path, resource_type.value)
                manifest.save()

            return download_result

        except Exception as e:
            error_msg = f"下载视频 {resource_id} 时出错: {str(e)}"
            logger.error(error_msg)
            return DownloadResult(Resource(resource_id, "未知"), False, error_msg)

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
            play_url, quality = self.api_client.get_best_quality_url(play_list_dict)

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
            if not file_url:
                logger.warning(f"无法获取文件 {resource.title} 的资源")
                return None
            return file_name, file_url
        except Exception as e:
            logger.error(f"获取文档URL时出错: {str(e)}")
            return None

    def _get_live_m3u8_url(self, resource: Resource) -> Optional[str]:
        """获取直播回放 m3u8 地址"""
        try:
            live_details = self.api_client.get_lookback_detail_info(resource.resource_id)
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
        except Exception as e:
            logger.error(f"获取直播回放URL时出错: {str(e)}")
        return None

    def _download_ppt_images(self, resource: Resource, course_dir: str, user_id: str):
        """下载直播互动区的 PPT 图片"""
        room_id = 'XET#3ef612fbf00761c10'  # 固定 room_id，同 app 下复用
        try:
            images = self.api_client.get_interaction_images(
                resource.resource_id, room_id, user_id
            )
            if not images:
                return

            lesson_dir = os.path.join(course_dir, FileUtils.sanitize_filename(resource.title))
            ppt_dir = os.path.join(lesson_dir, 'ppt')
            FileUtils.ensure_dir(ppt_dir)

            logger.info(f"  下载 {len(images)} 张 PPT 图片...")
            for i, img_url in enumerate(images):
                ext = '.png'
                if '.jpg' in img_url or '.jpeg' in img_url:
                    ext = '.jpg'
                img_file = os.path.join(ppt_dir, f'{i+1:02d}{ext}')
                if os.path.exists(img_file):
                    continue
                self.downloader.download_document(img_url, img_file)
            logger.info(f"  PPT 图片已保存到 {ppt_dir}")
        except Exception as e:
            logger.warning(f"下载 PPT 图片失败: {e}")

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
