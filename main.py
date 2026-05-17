#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
小鹅通视频下载器主程序

使用方法:
    python main.py                   # 下载整个课程
    python main.py --single <id>     # 下载单个视频
    python main.py --check           # 检查环境
    python main.py --help            # 显示帮助
"""

import argparse
import json
import os
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from xiaoet_downloader import XiaoetConfig, XiaoetDownloadManager, logger


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='小鹅通视频下载器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python main.py                           # 下载所有课程
  python main.py --login                   # 仅扫码登录，保存 cookie 后退出
  python main.py --single v_123456        # 下载单个视频
  python main.py --config custom.json     # 使用自定义配置文件
  python main.py --force                  # 忽略清单强制全量下载
  python main.py --no-cache               # 忽略缓存重新下载
  python main.py --no-transcode           # 只下载不转码
  python main.py --check                  # 检查运行环境
        """
    )

    parser.add_argument(
        '--config', '-c',
        default='config.json',
        help='配置文件路径 (默认: config.json)'
    )

    parser.add_argument(
        '--single', '-s',
        help='下载单个视频资源ID'
    )

    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='忽略缓存，重新下载所有文件'
    )

    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='忽略下载清单，强制重新下载全部资源'
    )

    parser.add_argument(
        '--no-transcode',
        action='store_true',
        help='只下载不转码'
    )

    parser.add_argument(
        '--check',
        action='store_true',
        help='检查运行环境'
    )

    parser.add_argument(
        '--login',
        action='store_true',
        help='仅执行微信扫码登录，保存 cookie 后退出'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='显示详细日志'
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        import logging
        logger.set_level(logging.DEBUG)

    try:
        # 加载配置
        if not os.path.exists(args.config):
            logger.error(f"配置文件不存在: {args.config}")
            logger.info("请创建配置文件，参考 config.json.example")
            return 1

        from xiaoet_downloader.auth.login import check_cookie_valid, qrcode_login

        config = XiaoetConfig.from_file(args.config)

        # 验证配置完整性
        try:
            config.validate()
        except ValueError as e:
            logger.error(f"配置无效: {e}")
            return 1

        # 检查 cookie 有效性
        if not check_cookie_valid(config.cookie, config.app_id, config.user_agent):
            logger.info("Cookie 无效或已过期，需要重新登录")
            pid = config.products[0]['product_id'] if config.products else ''
            new_cookie = qrcode_login(config.app_id, pid, config.user_agent)
            if not new_cookie:
                logger.error("登录失败，请重试")
                return 1

            # 更新内存中的 config
            config.cookie = new_cookie

            # 写回配置文件（原子写入）
            with open(args.config, 'r', encoding='utf-8') as f:
                cfg_json = json.load(f)
            cfg_json['cookie'] = new_cookie
            tmp_path = args.config + '.tmp'
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(cfg_json, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, args.config)
            logger.info("✓ Cookie 已更新到配置文件")

        # 仅登录模式
        if args.login:
            logger.info("登录完成")
            return 0

        manager = XiaoetDownloadManager(config)

        # 检查环境
        if args.check:
            if manager.check_environment():
                logger.info("环境检查通过")
                return 0
            else:
                logger.error("环境检查失败")
                return 1

        # 检查环境（静默）
        if not manager.check_environment():
            logger.error("环境检查失败，请先解决环境问题")
            return 1

        # 下载单个视频
        if args.single:
            logger.info(f"开始下载单个视频: {args.single}")
            result = manager.download_single_video(
                args.single,
                nocache=args.no_cache,
                auto_transcode=not args.no_transcode
            )

            if result.success:
                logger.info(f"下载成功: {result.message}")
                return 0
            else:
                logger.error(f"下载失败: {result.message}")
                return 1

        # 下载所有课程
        logger.info("开始下载所有课程")
        results = manager.download_all_courses(
            nocache=args.no_cache,
            auto_transcode=not args.no_transcode,
            force=args.force
        )

        # 返回适当的退出码
        if results['total_failed']:
            return 1
        else:
            return 0

    except KeyboardInterrupt:
        logger.info("用户中断下载")
        return 130
    except Exception as e:
        logger.error(f"程序执行出错: {str(e)}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


if __name__ == '__main__':
    sys.exit(main())
