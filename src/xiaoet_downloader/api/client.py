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
    GET_LIVE_LOOK_BACK_DETAILS_INFO_URL = "https://m.zhixuehaoke.com/_alive/api/get_lookback_list"
    GET_MICRO_NAVIGATION_URL = "https://{0}.h5.xiaoeknow.com/xe.micro_page.navigation.get/1.0.0"
    GET_PLAY_URL = "https://{0}.h5.xiaoeknow.com/xe.material-center.play/getPlayUrl"
    
    def __init__(self, config: XiaoetConfig):
        """初始化API客户端"""
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
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
            if p_id == "0":
                return [(item.get('resource_id'), item.get('resource_title'), self.get_column_items(app_id,column_id,item.get('resource_id'))) for item in items]
                # chap = [(items[2].get('resource_id'), items[1].get('resource_title'),
                #          self.get_column_items(app_id, column_id, items[2].get('resource_id'))) ]
                #  chap
            #{'id': 31482586, 'app_id': 'appGhRZuOra6587', 'p_id': 'chap_32leFVtbvbwm4se35OdwYApAol1',
            # 'course_id': 'course_2faMPUe85iHzAukP1xlZxWU1t8Y', 'chapter_id': 'l_68c8f08ae4b0694ca118e8bf', 'resource_id': 'l_68c8f08ae4b0694ca118e8bf',
            # 'chapter_type': 2, 'chapter_title': 'MBA、MPA和MTA择校指导', 'resource_title': 'MBA、MPA和MTA择校指导', 'resource_type': 4, 'chapter_state': 0,
            # 'sort_value': 3, 'unlock_condition': '[{"operate":"JOIN","value":"0"}]', 'unlock_date': '0001-01-01 00:00:00', 'try_length': 0,
            # 'is_elective': 0, 'sub_course_id': '', 'sub_course_sort_value': 0, 'section_num': 0, 'try_num': 0, 'is_try': 0, 'children': [],
            # 'sort_c': '02', 'elective': 0, 'unlock_state': 1, 'study_status': 1, 'learn_progress': 83,
            # 'jump_url': '/v2/course/alive/l_68c8f08ae4b0694ca118e8bf?app_id=appGhRZuOra6587&alive_mode=&pro_id=course_2faMPUe85iHzAukP1xlZxWU1t8Y&type=2',
            # 'alive_status': 3, 'alive_start_time': '2025-09-24 19:00:00', 'img_url': '', 'is_lookback': 1, 'has_breathing_lamp': 0}
            return [(item.get('resource_id'), item.get('resource_title')) for item in items]
        except requests.RequestException as e:
            raise Exception(f"获取专栏项目列表失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析专栏项目列表响应失败: {str(e)}")
    
    def get_video_detail_info(self, resource_id: str) -> Dict[str, Any]:
        """获取视频详情信息"""
        url = self.GET_VIDEO_DETAILS_INFO_URL.format(self.config.app_id)
        payload = {
            'bizData[resource_id]': resource_id,
            'bizData[product_id]': self.config.product_id,
            'bizData[opr_sys]': 'Win32'
        }
        headers = {
            'cookie': self.config.cookie,
        }
        
        try:
            response = requests.post(url, headers=headers, data=payload)
            response.raise_for_status()
            data = response.json().get('data', {}).get('video_info', {})
            return data
        except requests.RequestException as e:
            raise Exception(f"获取视频详情失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析视频详情响应失败: {str(e)}")

    def get_document_detail_info(self, resource_id: str) -> Dict[str, Any]:
        """获取视频详情信息"""
        url = self.GET_DOCUMENT_DETAILS_INFO_URL.format(self.config.app_id)
        payload = {
            "bizData":{
                'resource_id': resource_id,
                'product_id': self.config.product_id
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
        """获取视频详情信息"""
        url = self.GET_LIVE_LOOK_BACK_DETAILS_INFO_URL
        payload = {
            "app_id": self.config.app_id,
            "alive_id": resource_id,
            "course_id": self.config.product_id
        }
        headers = {
            'cookie': self.config.cookie,
        }

        try:
            response = requests.get(url, headers=headers, params=payload)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data
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