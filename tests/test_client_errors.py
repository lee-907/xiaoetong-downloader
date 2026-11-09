#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import requests

from xiaoet_downloader.api.client import XiaoetAPIClient, XiaoetAPIError


class FakeResponse:
    def __init__(self, payload=None, json_error=False):
        self.payload = payload
        self.json_error = json_error

    def raise_for_status(self):
        return None

    def json(self):
        if self.json_error:
            raise json.JSONDecodeError("Expecting value", "", 0)
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response

    def post(self, *args, **kwargs):
        return self.response

    def get(self, *args, **kwargs):
        return self.response


def make_client(response):
    config = SimpleNamespace(app_id='app_test', cookie='cookie_test', user_agent='test-agent')
    client = XiaoetAPIClient(config)
    client.session = FakeSession(response)
    return client


class TestParseBizData(unittest.TestCase):
    """覆盖 code != 0 / data 类型异常等小鹅通业务错误"""

    def test_business_error_raises_clear_exception(self):
        resp = FakeResponse({"code": 19, "msg": "invalid access token", "data": ""})
        with self.assertRaises(XiaoetAPIError) as ctx:
            XiaoetAPIClient._parse_biz_data(resp, "专栏资源列表")
        self.assertIn("code=19", str(ctx.exception))
        self.assertIn("invalid access token", str(ctx.exception))

    def test_success_returns_data_dict(self):
        resp = FakeResponse({"code": 0, "data": {"list": [{"resource_id": "v_1"}]}})
        data = XiaoetAPIClient._parse_biz_data(resp, "专栏资源列表")
        self.assertEqual(data["list"][0]["resource_id"], "v_1")

    def test_empty_data_returns_empty_dict(self):
        resp = FakeResponse({"code": 0, "data": ""})
        self.assertEqual(XiaoetAPIClient._parse_biz_data(resp, "专栏资源列表"), {})

    def test_non_dict_payload_raises_value_error(self):
        resp = FakeResponse(["unexpected"])
        with self.assertRaises(ValueError):
            XiaoetAPIClient._parse_biz_data(resp, "专栏资源列表")

    def test_non_json_raises_value_error(self):
        resp = FakeResponse(json_error=True)
        with self.assertRaises(ValueError):
            XiaoetAPIClient._parse_biz_data(resp, "专栏资源列表")


class TestColumnItemsError(unittest.TestCase):
    """p_ 专栏接口鉴权失败时不能抛出 AttributeError"""

    def test_invalid_token_surfaces_as_api_error(self):
        client = make_client(FakeResponse({"code": 19, "msg": "invalid access token", "data": ""}))
        with self.assertRaises(XiaoetAPIError) as ctx:
            client.get_column_items('app_test', 'p_65bc9702e4b064a8cb20a1e0')
        self.assertIn("invalid access token", str(ctx.exception))


class TestLookbackDetail(unittest.TestCase):
    """直播回放 data 为 null 时应返回 None，业务错误应抛出"""

    def test_null_data_returns_none(self):
        client = make_client(FakeResponse({"code": 0, "data": None}))
        self.assertIsNone(client.get_lookback_detail_info('l_test'))

    def test_business_error_raises(self):
        client = make_client(FakeResponse({"code": 19, "msg": "invalid access token", "data": ""}))
        with self.assertRaises(Exception) as ctx:
            client.get_lookback_detail_info('l_test')
        self.assertIn("invalid access token", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()
