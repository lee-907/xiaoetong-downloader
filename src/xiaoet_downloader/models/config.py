#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class XiaoetConfig:
    """小鹅通配置类"""
    app_id: str
    cookie: str
    user_agent: str = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    products: list = field(default_factory=list)
    download_dir: str = 'download'
    filter: list = field(default_factory=list)
    max_workers: int = 3

    @classmethod
    def from_file(cls, config_path: str) -> 'XiaoetConfig':
        """从配置文件加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config_data = json.load(file)

            products = config_data.get('products', [])

            # 兼容旧格式: 有 product_id 时自动包装为 products 列表
            if not products and 'product_id' in config_data:
                products = [{
                    'product_name': config_data.get('product_name', 'default'),
                    'product_id': config_data['product_id']
                }]

            # 确保 download_dir 为绝对路径
            download_dir = config_data.get('download_dir', 'download')
            if not os.path.isabs(download_dir):
                download_dir = os.path.abspath(download_dir)

            user_agent = config_data.get('user_agent') or cls.user_agent

            return cls(
                app_id=config_data.get('app_id', ''),
                cookie=config_data.get('cookie', ''),
                user_agent=user_agent,
                products=products,
                download_dir=download_dir,
                filter=config_data.get('filter', []),
                max_workers=config_data.get('max_workers', 3)
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")
        except json.JSONDecodeError:
            raise ValueError("配置文件内容不是有效的 JSON 格式")
        except Exception as e:
            raise Exception(f"读取配置文件时发生错误: {e}")

    def validate(self) -> bool:
        """验证配置是否完整"""
        if not self.app_id:
            raise ValueError("app_id 不能为空")
        if not self.cookie:
            raise ValueError("cookie 不能为空，可通过扫码登录自动获取")
        if not self.products:
            raise ValueError("products 不能为空")
        for i, p in enumerate(self.products):
            if not p.get('product_id'):
                raise ValueError(f"products[{i}].product_id 不能为空")
            if not p.get('product_name'):
                raise ValueError(f"products[{i}].product_name 不能为空")
        return True

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'app_id': self.app_id,
            'cookie': self.cookie,
            'user_agent': self.user_agent,
            'products': self.products,
            'download_dir': self.download_dir,
            'max_workers': self.max_workers
        }

    def get_course_dir(self, product: dict) -> str:
        """获取课程下载目录路径"""
        return os.path.join(self.download_dir, product['product_name'])
