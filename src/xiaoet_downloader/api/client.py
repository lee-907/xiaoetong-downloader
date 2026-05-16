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
    # GET_COLUMN_ITEMS_URL = "https://{0}.h5.xiaoeknow.com/xe.course.business.column.items.get/2.0.0"
    GET_COLUMN_ITEMS_URL = "https://{0}.h5.xet.citv.cn/xe.course.business.avoidlogin.e_course.resource_catalog_list.get/1.0.0"
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
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data
        except requests.RequestException as e:
            raise Exception(f"获取导航信息失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析导航信息响应失败: {str(e)}")
    
    def get_column_items(self, app_id: str,column_id: str,p_id="0", page_index: int = 1,
                        page_size: int = 100, sort: str = 'desc') :
        """获取专栏项目列表"""
        url = self.GET_COLUMN_ITEMS_URL.format(self.config.app_id)
        payload = {
            'bizData[app_id]': app_id,
            # 'bizData[resource_id]': "v_67cedf2de4b0694ca0767527",
            'bizData[p_id]':p_id,
            'bizData[course_id]': column_id,
            'bizData[page_index]': str(page_index),
            'bizData[page_size]': str(page_size),
            'bizData[sort]': sort
        }

        headers = {
            'cookie': self.config.cookie,
        }
        
        try:
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            items = data.get('list', [])

            result = []
            for item in items:
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
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data.get('video_info', {}) if isinstance(data, dict) else None
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
            response = requests.post(url, headers=headers, json=payload)
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
            response = requests.get(url, headers=headers, params=payload)
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
            response = requests.post(url, headers=headers, data=payload)
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
        
        return None, None