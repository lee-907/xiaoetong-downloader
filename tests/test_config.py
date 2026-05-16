#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import tempfile
import json
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from xiaoet_downloader.models.config import XiaoetConfig


class TestXiaoetConfig(unittest.TestCase):
    """测试XiaoetConfig类"""

    def setUp(self):
        """设置测试环境"""
        self.test_config = {
            "app_id": "test_app_id",
            "cookie": "test_cookie",
            "products": [
                {"product_name": "测试课程", "product_id": "test_product_id"}
            ],
            "download_dir": "test_download",
            "max_workers": 5
        }

    def test_from_dict(self):
        """测试从字典创建配置"""
        config = XiaoetConfig(
            app_id=self.test_config["app_id"],
            cookie=self.test_config["cookie"],
            products=self.test_config["products"],
            download_dir=self.test_config["download_dir"],
            max_workers=self.test_config["max_workers"]
        )

        self.assertEqual(config.app_id, "test_app_id")
        self.assertEqual(config.cookie, "test_cookie")
        self.assertEqual(config.products[0]["product_id"], "test_product_id")
        self.assertEqual(config.products[0]["product_name"], "测试课程")
        self.assertEqual(config.download_dir, "test_download")
        self.assertEqual(config.max_workers, 5)

    def test_from_file(self):
        """测试从文件加载配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(self.test_config, f)
            temp_file = f.name

        try:
            config = XiaoetConfig.from_file(temp_file)
            self.assertEqual(config.app_id, "test_app_id")
            self.assertEqual(config.cookie, "test_cookie")
            self.assertEqual(config.products[0]["product_id"], "test_product_id")
            self.assertEqual(config.products[0]["product_name"], "测试课程")
        finally:
            os.unlink(temp_file)

    def test_validate_success(self):
        """测试配置验证成功"""
        config = XiaoetConfig(
            app_id="test_app_id",
            cookie="test_cookie",
            products=[{"product_name": "课程", "product_id": "p_123"}]
        )

        self.assertTrue(config.validate())

    def test_validate_failure_empty_app_id(self):
        """测试配置验证失败 - 空 app_id"""
        config = XiaoetConfig(
            app_id="",
            cookie="test_cookie",
            products=[{"product_name": "课程", "product_id": "p_123"}]
        )

        with self.assertRaises(ValueError):
            config.validate()

    def test_validate_failure_empty_products(self):
        """测试配置验证失败 - 空 products"""
        config = XiaoetConfig(
            app_id="test_app_id",
            cookie="test_cookie",
            products=[]
        )

        with self.assertRaises(ValueError):
            config.validate()

    def test_to_dict(self):
        """测试转换为字典"""
        config = XiaoetConfig(
            app_id="test_app_id",
            cookie="test_cookie",
            products=[{"product_name": "课程", "product_id": "p_123"}],
            download_dir="/absolute/path",
            max_workers=3
        )

        result = config.to_dict()
        self.assertEqual(result['app_id'], 'test_app_id')
        self.assertEqual(result['cookie'], 'test_cookie')
        self.assertEqual(result['products'], [{"product_name": "课程", "product_id": "p_123"}])
        self.assertEqual(result['download_dir'], '/absolute/path')
        self.assertEqual(result['max_workers'], 3)

    def test_old_format_compat(self):
        """测试兼容旧格式 (product_id → products)"""
        old_config = {
            "app_id": "test_app_id",
            "cookie": "test_cookie",
            "product_id": "old_product_id",
            "download_dir": "download"
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(old_config, f)
            temp_file = f.name

        try:
            config = XiaoetConfig.from_file(temp_file)
            self.assertEqual(len(config.products), 1)
            self.assertEqual(config.products[0]["product_id"], "old_product_id")
            self.assertEqual(config.products[0]["product_name"], "default")
        finally:
            os.unlink(temp_file)


if __name__ == '__main__':
    unittest.main()
