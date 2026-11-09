#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import requests
from typing import Dict, List, Tuple, Optional, Any
from ..models.config import XiaoetConfig
from ..models.resource import Resource
from ..utils.logger import logger


class XiaoetAPIError(Exception):
    """小鹅通业务接口返回错误（HTTP 200 但 code != 0）"""


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

    @staticmethod
    def _parse_biz_data(resp: requests.Response, api_name: str) -> Dict[str, Any]:
        """校验业务响应并返回 data 字典。

        小鹅通鉴权失败等场景仍返回 HTTP 200，body 为
        {"code": 19, "msg": "invalid access token", "data": ""}。
        直接 data.get('list') 会抛 AttributeError，掩盖真实原因，这里统一转成
        带 code/msg 的 XiaoetAPIError。
        """
        try:
            payload = resp.json()
        except json.JSONDecodeError as e:
            raise ValueError(f"{api_name} 返回非 JSON 响应: {e}")

        if not isinstance(payload, dict):
            raise ValueError(f"{api_name} 返回格式异常: {type(payload).__name__}")

        code = payload.get('code', 0)
        if code != 0:
            msg = payload.get('msg') or payload.get('message') or '未知错误'
            raise XiaoetAPIError(f"{api_name} 业务错误 (code={code}): {msg}")

        data = payload.get('data')
        if data is None or data == [] or data == "":
            return {}
        if not isinstance(data, dict):
            raise ValueError(f"{api_name} 返回 data 类型异常: {type(data).__name__}")
        return data

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
            response = self.session.post(url, headers=headers, data=payload, timeout=30)
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
                max_pages = 50  # 安全上限
                while current_page <= max_pages:
                    payload = {
                        'bizData[column_id]': column_id,
                        'bizData[page_index]': str(current_page),
                        'bizData[page_size]': str(page_size),
                        'bizData[sort]': sort
                    }
                    response = self.session.post(url, headers=headers, data=payload, timeout=30)
                    response.raise_for_status()
                    data = self._parse_biz_data(response, "专栏资源列表")
                    items = data.get('list', [])
                    if not isinstance(items, list):
                        raise ValueError(f"专栏资源列表 list 类型异常: {type(items).__name__}")
                    if not items:
                        break
                    all_items.extend(items)
                    if len(items) < page_size:
                        break
                    current_page += 1
                return [(item.get('resource_id'), item.get('resource_title')) for item in all_items]
            else:
                # citv.cn 主域名；若 TLS/反爬故障则回退到 xiaoeknow.com 同接口
                urls = [
                    self.GET_COLUMN_ITEMS_URL.format(self.config.app_id),
                    f"https://{self.config.app_id}.h5.xiaoeknow.com/xe.course.business.avoidlogin.e_course.resource_catalog_list.get/1.0.0",
                ]
                logger.info(f"请求课程资源 API: {urls[0][:80]}...")
                all_items = []
                seen_ids = set()

                def _fetch(page_size_to_use: int):
                    payload = {
                        'bizData[app_id]': app_id,
                        'bizData[p_id]': p_id,
                        'bizData[course_id]': column_id,
                        'bizData[page_index]': '1',
                        'bizData[page_size]': str(page_size_to_use),
                        'bizData[sort]': sort,
                    }
                    last_exc = None
                    for u in urls:
                        try:
                            resp = self.session.post(u, headers=headers, data=payload, timeout=30)
                            resp.raise_for_status()
                            return self._parse_biz_data(resp, "课程资源列表")
                        except (requests.RequestException, ValueError) as e:
                            last_exc = e
                            logger.warning(f"课程资源 API 请求失败 ({u[:70]}...)，尝试备用域名: {e}")
                    raise last_exc if last_exc is not None else Exception("课程资源 API 请求全部失败")

                # 先探一次拿 total，再按 total 一次性拉全量（此 API 忽略 page_index）
                data = _fetch(200)
                items = data.get('list', [])
                total = data.get('total') or len(items)
                fetched = len(items)
                for i in items:
                    rid = i.get('resource_id')
                    if rid not in seen_ids:
                        seen_ids.add(rid)
                        all_items.append(i)

                if fetched < total:
                    data = _fetch(total)
                    items = data.get('list', [])
                    for i in items:
                        rid = i.get('resource_id')
                        if rid not in seen_ids:
                            seen_ids.add(rid)
                            all_items.append(i)

                logger.info(f"  获取到 {len(all_items)} 条 (total={total})")

                result = []
                for item in all_items:
                    children = item.get('children', [])
                    if children:
                        logger.info(f"  递归获取子资源: {item.get('resource_id')} ({len(children)} 个子项)")
                        sub = self.get_column_items(app_id, column_id, item.get('resource_id'))
                        result.extend(sub)
                    else:
                        result.append((item.get('resource_id'), item.get('resource_title')))
                logger.info(f"课程资源获取完成: {len(result)} 个资源")
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
            response = self.session.post(url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()
            resp_json = response.json()
            if isinstance(resp_json, dict) and resp_json.get('code', 0) != 0:
                raise Exception(f"API返回错误: {resp_json.get('msg', '未知错误')}")
            data = resp_json.get('data', {}) if isinstance(resp_json, dict) else {}
            return data.get('video_info', {}) if isinstance(data, dict) else {}
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
            response = self.session.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json().get('data', {})
            return data
        except requests.RequestException as e:
            raise Exception(f"获取文件详情失败: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"解析文件详情响应失败: {str(e)}")

    def get_lookback_detail_info(self, resource_id: str):
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
            response = self.session.get(url, headers=headers, params=payload, timeout=30)
            response.raise_for_status()
            resp_json = response.json()
            if not isinstance(resp_json, dict):
                raise Exception(f"获取直播回放详情响应格式异常: {type(resp_json).__name__}")
            if resp_json.get('code', 0) != 0:
                raise Exception(f"API返回错误: {resp_json.get('msg', '未知错误')}")
            # data 为 null 表示回放尚未生成/不可用，交由调用方给出明确提示
            return resp_json.get('data')
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
            response = self.session.post(url, headers=headers, data=payload, timeout=30)
            response.raise_for_status()
            resp_json = response.json()
            if isinstance(resp_json, dict) and resp_json.get('code', 0) != 0:
                raise Exception(f"API返回错误: {resp_json.get('msg', '未知错误')}")
            data = resp_json.get('data', {}) if isinstance(resp_json, dict) else {}
            play_list_dict = data.get(play_sign, {}).get('play_list', {}) if isinstance(data, dict) else {}
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
                # 首次请求时若 room_id 为空，遍历消息自动发现
                if not room_id:
                    for m in msgs:
                        rid = m.get('room_id', '')
                        if rid:
                            room_id = rid
                            break
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