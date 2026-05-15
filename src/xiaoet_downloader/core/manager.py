#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import List, Dict, Tuple, Optional, Any

from ..models.config import XiaoetConfig
from ..models.resource import Resource, DownloadResult, ResourceType, DownloadStatus
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
        self.transcoder = VideoTranscoder(config.download_dir)

        # 确保下载目录存在
        FileUtils.ensure_dir(config.download_dir)

    def download_course(self, nocache: bool = False, auto_transcode: bool = True) -> Dict[str, List[DownloadResult]]:
        """
        下载整个课程
        Args:
            nocache: 是否忽略缓存
            auto_transcode: 是否自动转码
            
        Returns:
            Dict[str, List[DownloadResult]]: 下载结果统计
        """
        results = {
            'success': [],
            'failed': []
        }

        try:
            # 获取用户信息
            navigation_info = self.api_client.get_micro_navigation_info()
            user_id = navigation_info.get('user_id')
            if not user_id:
                logger.error("无法获取用户ID")
                return results

            # 获取课程资源列表
            resource_items = self.api_client.get_column_items(self.config.app_id, self.config.product_id)
            if not resource_items:
                logger.warning("未找到课程资源")
                return results
            lens = len(resource_items)
            logger.info(f"找到 {lens} 个资源")

            # 确保下载根目录存在
            FileUtils.ensure_dir(self.config.download_dir)

            for index, (resource_id, resource_title) in enumerate(resource_items):
                try:
                    if resource_title in self.config.filter:
                        logger.info(f"[{index + 1}/{lens}] 跳过: {resource_title} ({resource_id})")
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
                        doc_info = self._get_document_url(resource)
                        if not doc_info:
                            results['failed'].append(DownloadResult(resource, False, "无法获取文档地址"))
                            continue
                        document_title, document_url = doc_info
                        final_path = os.path.join(self.config.download_dir, document_title)
                        if self.downloader.download_document(document_url, final_path):
                            results['success'].append(DownloadResult(resource, True, "下载完成", final_path))
                        else:
                            results['failed'].append(DownloadResult(resource, False, "文档下载失败"))
                    elif resource_type in (ResourceType.VIDEO, ResourceType.LIVE):
                        if resource_type == ResourceType.LIVE:
                            play_url = self._get_live_m3u8_url(resource)
                            if not play_url:
                                play_url = self._get_play_url(resource, user_id)
                        else:
                            play_url = self._get_play_url(resource, user_id)
                        if not play_url:
                            results['failed'].append(DownloadResult(resource, False, "无法获取播放地址"))
                            continue

                        download_result = self.downloader.download_m3u8_video(
                            resource, play_url, self.config.download_dir, nocache
                        )
                        if download_result.success and auto_transcode:
                            transcode_result = self.transcoder.transcode_video(
                                resource, self.config.download_dir, index + 1
                            )
                            if transcode_result.success:
                                results['success'].append(transcode_result)
                            else:
                                results['failed'].append(transcode_result)
                        elif download_result.success:
                            results['success'].append(download_result)
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

        self._print_summary(results)
        return results

    def download_single_video(self, resource_id: str, nocache: bool = False,
                              auto_transcode: bool = True) -> DownloadResult:
        """
        下载单个视频
        
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
                return DownloadResult(
                    Resource(resource_id, "未知"),
                    False,
                    "无法获取用户ID"
                )

            # 创建视频资源对象（标题暂时未知）
            if resource_id.startswith('l_'):
                resource_type = ResourceType.LIVE
            elif resource_id.startswith('v_'):
                resource_type = ResourceType.VIDEO
            else:
                resource_type = ResourceType.AUDIO
            resource = Resource(
                resource_id=resource_id,
                title="未知",
                resource_type=resource_type
            )

            # 获取播放URL
            if resource_type == ResourceType.LIVE:
                play_url = self._get_live_m3u8_url(resource)
            else:
                play_url = self._get_play_url(resource, user_id)
            if not play_url:
                return DownloadResult(resource, False, "无法获取播放地址")

            # 下载视频
            download_result = self.downloader.download_m3u8_video(
                resource, play_url, self.config.download_dir, nocache
            )

            if download_result.success and auto_transcode:
                # 自动转码
                return self.transcoder.transcode_video(resource)

            return download_result

        except Exception as e:
            error_msg = f"下载视频 {resource_id} 时出错: {str(e)}"
            logger.error(error_msg)
            return DownloadResult(
                Resource(resource_id, "未知"),
                False,
                error_msg
            )

    def _get_play_url(self, resource: Resource, user_id: str) -> Optional[str]:
        """获取播放URL"""
        try:
            # 获取视频详情
            video_details = self.api_client.get_video_detail_info(resource.resource_id)
            play_sign = video_details.get('play_sign')

            if not play_sign:
                logger.warning(f"无法获取视频 {resource.title} 的播放标识")
                return None

            # 更新资源的play_sign
            resource.play_sign = play_sign

            # 获取播放URL列表
            play_list_dict = self.api_client.get_play_url(user_id, play_sign)

            # 获取最佳质量的播放URL
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

    def _get_document_url(self, resource: Resource) -> tuple[Any | None, Any | None] | None:
        """获取播放URL"""
        try:
            # 获取视频详情
            document_details = self.api_client.get_document_detail_info(resource.resource_id)
            file_name = document_details.get('file_name')
            file_url = document_details.get('file_url')
            if not file_url:
                logger.warning(f"无法获取文件 {resource.title} 的资源")
                return None
            return file_name, file_url
        except Exception as e:
            logger.error(f"获取播放URL时出错: {str(e)}")
            return None

    def _get_live_m3u8_url(self, resource: Resource) -> tuple[Any | None, Any | None] | None:
        """获取播放URL"""
        try:
            # 获取视频详情
            live_details = self.api_client.get_lookback_detail_info(resource.resource_id)
            for live_detail in live_details:
                for sharpness in live_detail['line_sharpness']:
                    return sharpness['url']
        except Exception as e:
            logger.error(f"获取播放URL时出错: {str(e)}")
            return None
        return None

    def _print_summary(self, results: Dict[str, List[DownloadResult]]) -> None:
        """打印处理结果摘要"""
        total = len(results['success']) + len(results['failed'])
        success_count = len(results['success'])
        failed_count = len(results['failed'])

        logger.info("\n" + "=" * 50)
        logger.info("处理完成:")
        logger.info(f"成功: {success_count}/{total}")
        logger.info(f"失败: {failed_count}/{total}")

        if results['failed']:
            logger.info("\n失败的视频:")
            for result in results['failed']:
                logger.error(f"- {result.resource.title} ({result.resource.resource_id}): {result.message}")

        if results['success']:
            logger.info("\n成功的视频:")
            for result in results['success']:
                logger.info(f"+ {result.resource.title}")

        logger.info("=" * 50)

    def check_environment(self) -> bool:
        """检查运行环境"""
        logger.info("检查运行环境...")

        # # 检查配置
        # try:
        #     self.config.validate()
        #     logger.info("✓ 配置验证通过")
        # except ValueError as e:
        #     logger.error(f"✗ 配置验证失败: {str(e)}")
        #     return False
        #
        # 检查ffmpeg
        if self.transcoder.check_ffmpeg_availability():
            logger.info("✓ ffmpeg 可用")
        else:
            logger.warning("⚠ ffmpeg 不可用，将无法进行视频转码")

        # 检查下载目录
        try:
            FileUtils.ensure_dir(self.config.download_dir)
            logger.info(f"✓ 下载目录已准备: {self.config.download_dir}")
        except Exception as e:
            logger.error(f"✗ 无法创建下载目录: {str(e)}")
            return False

        return True
