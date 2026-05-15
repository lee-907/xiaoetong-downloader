# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 [baby2431/xiaoetong-downloader](https://github.com/baby2431/xiaoetong-downloader) 的小鹅通课程下载工具。下载已购买课程的视频（m3u8→mp4）、文档和直播回放。

## 环境与命令

```bash
# 安装依赖（Python 3.8+）
pip install -r requirements.txt    # ffmpy, m3u8, requests

# 需要 ffmpeg
brew install ffmpeg                # macOS

# 运行
cp config.json.example config.json # 先配置 cookie 等
python main.py                     # 下载整个课程
python main.py --single v_xxx      # 下载单个视频
python main.py --check             # 检查环境
python main.py --no-cache          # 忽略缓存重新下载
python main.py --no-transcode      # 只下载不合并

# 测试
python -m pytest tests/ -v
make test
```

## 架构

```
main.py                          # CLI 入口，argparse 参数解析
src/xiaoet_downloader/
  ├── api/client.py              # 小鹅通 API 封装
  ├── core/manager.py            # 下载管理器，流程编排
  ├── core/downloader.py         # m3u8 视频下载（TS 分片+断点续传）和文档下载
  ├── core/transcoder.py         # ffmpeg 合并 TS→mp4
  ├── models/config.py           # XiaoetConfig dataclass
  └── models/resource.py         # Resource, DownloadResult 等数据类
```

## 下载流程

1. `get_micro_navigation_info()` → 获取 `user_id`
2. `get_column_items(app_id, product_id)` → 获取课程三层树结构（章节→节→资源）
3. 对每个资源：`v_` 开头=视频，`d_` 开头=文档，`l_` 开头=直播回放
4. 视频：`get_video_detail_info()` → 拿 `play_sign` → `get_play_url()` → 拿 m3u8 地址
5. `download_m3u8_video()` 逐片下载 TS 分片，生成本地 m3u8
6. `transcode_video()` 调 ffmpeg 合并 TS → mp4

## 配置

`config.json`（参考 `config.json.example`）：

| 字段 | 说明 | 来源 |
|------|------|------|
| `app_id` | 店铺标识 | 课程 URL 中提取：`https://{app_id}.h5.xiaoeknow.com/...` |
| `cookie` | 登录态 | 浏览器 DevTools → Network → 复制请求 Cookie |
| `product_id` | 课程 ID | 课程 URL 中 `product_id=` 后的值 |
| `download_dir` | 输出目录 | 默认 `download` |
| `filter` | 要跳过的章节名列表 | 可选 |

API 域名硬编码在 `api/client.py` 中（`h5.xiaoeknow.com`, `h5.xet.citv.cn`），无需配置。

## 注意事项

- 仅支持已购买课程，需有效的登录 cookie
- cookie 过期后需重新从浏览器获取
- 下载目录保持章节层级：`课程名/01-章节名/[1]-视频名.mp4`
