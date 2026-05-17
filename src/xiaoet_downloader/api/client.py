#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import requests
from typing import Dict, List, Tuple, Optional, Any
from ..models.config import XiaoetConfig
from ..models.resource import Resource


class XiaoetAPIClient:
    """小鹅通API客户端"""
    
    # API URL模板
    GET_COLUMN_ITEMS_URL = "https://{0}.h5.xet.citv.cn/xe.course.business.avoidlogin.e_course.resource_catalog_list.get/1.0.0"
    GET_COLUMN_ITEMS_URL_P = "https://{0}.h5.xiaoeknow.com/xe.course.business.column.items.get/2.0.0"
    GET_VIDEO_DETAILS_INFO_URL = "https://{0}.h5.xiaoeknow.com/xe.course.business.video.detail_info.get/2.0.0"
    GET_DOCUMENT_DETAILS_INFO_URL = "https://{0}.h5.xet.citv.cn/xe.course.business.e_course.document_info.get/1.0.0"
    GET_LIVE_LOOK_BACK_DETAILS_INFO_URL = "https://{0}.h5.xiaoeknow.com/_alive/v3/get_lookback_list"
    GET_MICRO_NAVIGATION_URL = "https://{0}.h5.xiaoeknow.com/xe.micro_page.navigation.get/1.0.0"
    GET_PLAY_URL = "https://{0}.h5.xiaoeknow.com/xe.material-center.play/getPlayUrl"
    
    def __init__(self, config: XiaoetConfig):
        """初始化API客户端"""
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.user_agent
        })
    
    def get_micro_navigation_info(self) -> Dict[str, Any]:
        """获取微页面导航信息"""
        url = self.GET_MICRO_NAVIGATION_URL.format(self.config.app_id)
        payload = json.dumps({
            "app_id": self.config.app_id,
            "agent_type": 1,
            "app_version": 0
        })
        headers = {
            'cookie': self.config.cookie,
            'Content-Type': 'application/json'
        }
        
        try:
            response = self.session.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data
        except requests.RequestException as e:
            raise Exception(f"获取导航信息失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析导航信息响应失败: {str(e)}")
    
    def get_column_items(self, app_id: str, column_id: str, p_id="0", page_index: int = 1,
                        page_size: int = 100, sort: str = 'desc'):
        """获取课程/专栏资源列表"""
        headers = {'cookie': self.config.cookie}

        try:
            # 根据前缀选择 API：p_ 走 column API，其他走 course API
            if column_id.startswith('p_'):
                url = self.GET_COLUMN_ITEMS_URL_P.format(self.config.app_id)
                all_items = []
                current_page = page_index
                while True:
                    payload = {
                        'bizData[column_id]': column_id,
                        'bizData[page_index]': str(current_page),
                        'bizData[page_size]': str(page_size),
                        'bizData[sort]': sort
                    }
                    response = self.session.post(url, headers=headers, data=payload)
                    response.raise_for_status()
                    data = response.json().get('data', {})
                    items = data.get('list', [])
                    if not items:
                        break
                    all_items.extend(items)
                    if len(items) < page_size:
                        break
                    current_page += 1
                return [(item.get('resource_id'), item.get('resource_title')) for item in all_items]
            else:
                url = self.GET_COLUMN_ITEMS_URL.format(self.config.app_id)
                all_items = []
                current_page = page_index
                while True:
                    payload = {
                        'bizData[app_id]': app_id,
                        'bizData[p_id]': p_id,
                        'bizData[course_id]': column_id,
                        'bizData[page_index]': str(current_page),
                        'bizData[page_size]': str(page_size),
                        'bizData[sort]': sort
                    }
                    response = self.session.post(url, headers=headers, data=payload)
                    response.raise_for_status()
                    data = response.json().get('data', {})
                    items = data.get('list', [])
                    if not items:
                        break
                    all_items.extend(items)
                    if len(items) < page_size:
                        break
                    current_page += 1

                result = []
                for item in all_items:
                    children = item.get('children', [])
                    if children:
                        sub = self.get_column_items(app_id, column_id, item.get('resource_id'))
                        result.extend(sub)
                    else:
                        result.append((item.get('resource_id'), item.get('resource_title')))
                return result
        except requests.RequestException as e:
            raise Exception(f"获取专栏项目列表失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析专栏项目列表响应失败: {str(e)}")
    
    def get_video_detail_info(self, resource_id: str, product_id: str) -> Dict[str, Any]:
        """获取视频详情信息"""
        url = self.GET_VIDEO_DETAILS_INFO_URL.format(self.config.app_id)
        payload = {
            'bizData[resource_id]': resource_id,
            'bizData[product_id]': product_id,
            'bizData[opr_sys]': 'Win32'
        }
        headers = {
            'cookie': self.config.cookie,
        }
        
        try:
            response = self.session.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data.get('video_info', {})
        except requests.RequestException as e:
            raise Exception(f"获取视频详情失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析视频详情响应失败: {str(e)}")

    def get_document_detail_info(self, resource_id: str, product_id: str) -> Dict[str, Any]:
        """获取文档详情信息"""
        url = self.GET_DOCUMENT_DETAILS_INFO_URL.format(self.config.app_id)
        payload = {
            "bizData":{
                'resource_id': resource_id,
                'product_id': product_id
            }
        }
        headers = {
            'cookie': self.config.cookie,
        }

        try:
            response = self.session.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data
        except requests.RequestException as e:
            raise Exception(f"获取文件详情失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析文件详情响应失败: {str(e)}")

    def get_lookback_detail_info(self, resource_id: str) -> List:
        """获取直播回放列表（含 m3u8 地址）"""
        url = self.GET_LIVE_LOOK_BACK_DETAILS_INFO_URL.format(self.config.app_id)
        payload = {
            "app_id": self.config.app_id,
            "alive_id": resource_id,
            "protection": "0"
        }
        headers = {
            'cookie': self.config.cookie,
            'Referer': f'https://{self.config.app_id}.h5.xiaoeknow.com/',
        }

        try:
            response = self.session.get(url, headers=headers, params=payload)
            response.raise_for_status()
            return response.json().get('data', [])
        except requests.RequestException as e:
            raise Exception(f"获取文件详情失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析文件详情响应失败: {str(e)}")

    def get_play_url(self, user_id: str, play_sign: str) -> Dict[str, Any]:
        """获取播放URL"""
        url = self.GET_PLAY_URL.format(self.config.app_id)
        payload = json.dumps({
            "org_app_id": self.config.app_id,
            "app_id": self.config.app_id,
            "user_id": user_id,
            "play_sign": [play_sign],
            "play_line": "A",
            "opr_sys": "MacIntel"
        })
        headers = {
            'cookie': self.config.cookie,
            'Content-Type': 'application/json'
        }
        
        try:
            response = self.session.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            play_list_dict = data.get(play_sign, {}).get('play_list', {})
            return play_list_dict
        except requests.RequestException as e:
            raise Exception(f"获取播放URL失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析播放URL响应失败: {str(e)}")
    
    def get_best_quality_url(self, play_list_dict: Dict[str, Any]) -> Optional[Tuple[str, str]]:
        """获取最佳质量的播放URL"""
        quality_order = ['1080p_hls', '720p_hls', '480p_hls', '360p_hls']

        for quality in quality_order:
            if quality in play_list_dict and play_list_dict.get(quality, {}).get('play_url'):
                return play_list_dict.get(quality, {}).get('play_url'), quality

    def get_interaction_images(self, resource_id: str, room_id: str = '', user_id: str = '') -> List[str]:
        """获取互动区的 PPT 图片 URL 列表。若 room_id 为空则从首次响应中自动发现。"""
        url = f"https://{self.config.app_id}.h5.xiaoeknow.com/_alive/bff_h5/msg/list"
        headers = {
            'cookie': self.config.cookie,
            'Content-Type': 'application/json',
        }
        images = []
        seen_urls = set()
        seen_msg_ids = set()
        cursor = ''
        max_pages = 20
        for _ in range(max_pages):
            body = {
                'load_order': 1,
                'info_type': 0,
                'comment_id': cursor,
                'size': 50,
                'alive_id': resource_id,
                'room_id': room_id or '',
                'app_id': self.config.app_id,
                'load_history': 1,
                'user_id': user_id,
            }
            try:
                response = self.session.post(url, headers=headers, json=body, timeout=30)
                response.raise_for_status()
                data = response.json().get('data', {})
                msgs = data.get('msgs', []) or []
                if not msgs:
                    break
                # 首次请求时若 room_id 为空，从消息中自动发现
                if not room_id and msgs:
                    room_id = msgs[0].get('room_id', '') or room_id
                new_msgs = [m for m in msgs if m.get('id') not in seen_msg_ids]
                if not new_msgs:
                    break
                for msg in new_msgs:
                    seen_msg_ids.add(msg.get('id'))
                    if msg.get('content_type') == 2:
                        try:
                            urls = json.loads(msg.get('org_msg_content', '[]'))
                            for item in urls:
                                img_url = item.get('DownUrl', '')
                                if img_url and img_url not in seen_urls:
                                    seen_urls.add(img_url)
                                    images.append(img_url)
                        except (json.JSONDecodeError, TypeError):
                            pass
                cursor = str(msgs[-1].get('id', ''))
            except (requests.RequestException, json.JSONDecodeError):
                break
        return images