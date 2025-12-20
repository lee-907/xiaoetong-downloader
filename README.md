# 小鹅通视频下载器 

# 写在最前面
**本工具仅用于下载用户已购买的课程内容，请遵守相关法律法规和平台使用条款。**
> 解决遇到买的课程快到期来不及学，或者没网时想复习却看不了回放的尴尬？因为我就是这样子，所以完善了此下载器<br/>
> 基本代码来自 [miaoyc666/xiaoetong-video-downloader](https://github.com/miaoyc666/xiaoetong-video-downloader) 完善并且更新了此仓库问题


## 👀 功能特点
- 增加改进了目录分类，
- 支持视频下载和转码
- 支持过滤不想下载的章节
- 支持下载视频，附件，直播，（没有音频素材，所以没有开发）
![运行中的日志](ScreenShot_2025-12-21_032103_368.png)

## 🌏小鹅通下载器
> 小鹅通资源下载工具
> 本工具仅支持用户已购买课程的下载，并不存在付费课程的破解
> 本工具仅供自用和学习交流使用，请勿用于商业用途



## 📁 项目结构
```
xiaoetong-video-downloader/
├── src/xiaoet_downloader/         # 主要源代码
│   ├── models/                    # 数据模型
│   │   ├── config.py              # 配置模型
│   │   └── resource.py            # 资源模型
│   ├── api/                       # API客户端
│   │   └── client.py              # 小鹅通API客户端
│   ├── core/                      # 核心功能
│   │   ├── downloader.py          # 视频下载器
│   │   ├── transcoder.py          # 视频转码器
│   │   └── manager.py             # 下载管理器
│   ├── utils/                     # 工具类
│   │   ├── file_utils.py          # 文件工具
│   │   └── logger.py              # 日志工具
│   └── __init__.py                # 包初始化
├── tests/                         # 测试文件
├── scripts/                       # 脚本文件
├── main.py                        # 主程序入口
├── config.json.example            # 配置文件示例
├── requirements.txt               # 依赖列表
└── README.md                      # 说明文档
```

## 🚀 快速开始

### 1. 环境准备

#### 安装Python依赖

# 自动安装（推荐）
```bash
python scripts/setup.py
```

# 或手动安装
pip install -r requirements.txt
```

#### 安装ffmpeg
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 从 https://ffmpeg.org/download.html 下载并安装
```

### 2. 配置设置

复制配置文件模板并填入你的信息：
```bash
cp config.json.example config.json
```

编辑 `config.json`：
```json
{
  "app_id": "你的app_id",
  "cookie": "你的cookie",
  "product_id": "你的product_id",
  "download_dir": "download",
  "filter":["过滤的章节1","过滤的章节2"]
}
```

#### 📋 配置项说明
> 需要将浏览器调整为H5模式，小鹅通会转为 xxxxxx.xet.citv.cn模式

| 字段 | 说明 | 获取方式                                                                                                             |
|------|------|------------------------------------------------------------------------------------------------------------------|
| app_id | 店铺唯一标识 | 课程链接URL中获取，如 `https://appisb9y2un7034.xet.citv.cn/...` 中的 `appisb9y2un7034`                                      |
| cookie | 小鹅通web端的Cookie | 浏览器开发者工具中获取                                                                                                      |
| product_id | 课程唯一标识 | 课程链接URL中获取，如 `https://...xet.citv.cn/p/course/column/p_608baa19e4b071a81eb6ebbc` 中的 `p_608baa19e4b071a81eb6ebbc` |
| download_dir | 下载目录 | 可选，默认为 `download`                                                                                                |
| filter | 章节过滤 | 可选，默认为 `[]`                                                                                                      |


### 3. 使用方法

#### 基本用法
```bash
# 下载整个课程
python main.py

# 下载单个视频
python main.py --single v_123456789

# 检查环境
python main.py --check

# 显示帮助
python main.py --help
```

#### 高级选项
```bash
# 使用自定义配置文件
python main.py --config my_config.json

# 忽略缓存重新下载
python main.py --no-cache

# 只下载不转码
python main.py --no-transcode

# 显示详细日志
python main.py --verbose
```

## 🔧 开发指南

### 运行测试
```bash
# 运行所有测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_config.py
```

### 代码结构说明

- **models**: 数据模型，定义配置、视频资源等数据结构
- **api**: API客户端，处理与小鹅通服务器的通信
- **core**: 核心功能，包括下载器、转码器和管理器
- **utils**: 工具类，提供文件处理、日志等通用功能

## 🐛 故障排除

### 常见问题

1. **ffmpeg未找到**
   ```
   解决方案: 确保ffmpeg已安装并在PATH中
   ```

2. **配置文件错误**
   ```
   解决方案: 检查config.json格式是否正确，参考config.json.example
   ```

3. **网络连接问题**
   ```
   解决方案: 检查网络连接，确保可以访问小鹅通服务器
   ```

4. **Cookie过期**
   ```
   解决方案: 重新获取Cookie并更新配置文件
   ```

### 日志查看

程序运行时会在 `logs/` 目录下生成日志文件，可以查看详细的运行信息：

```bash
# 查看今天的日志
cat logs/xiaoet_$(date +%Y%m%d).log

# 实时查看日志
tail -f logs/xiaoet_$(date +%Y%m%d).log
```

## 📜 许可证
本项目仅供学习和个人使用，请勿用于商业用途。


## ⚠️ 免责声明

本工具仅用于下载用户已购买的课程内容，请遵守相关法律法规和平台使用条款。
=======
- [miaoyc666/xiaoetong-video-downloader](https://github.com/miaoyc666/xiaoetong-video-downloader)
