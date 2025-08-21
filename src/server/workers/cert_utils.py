# -*- coding: utf-8 -*-

"""
证书工具模块

提供证书处理相关的辅助函数，例如复制证书文件。
"""

import os
import shutil
from typing import Tuple


def copy_ssl_certificates(output_dir: str) -> Tuple[bool, str]:
    """
    复制证书为 ssl.key/ssl.crt（若不存在）
    
    :param output_dir: 输出目录
    :return: (success, message) 元组
    """
    try:
        conf_dir = os.path.join(output_dir, "conf")
        src_key = os.path.join(conf_dir, "node.key")
        src_crt = os.path.join(conf_dir, "node.crt")
        dst_key = os.path.join(conf_dir, "ssl.key")
        dst_crt = os.path.join(conf_dir, "ssl.crt")
        
        if not os.path.exists(src_key) or not os.path.exists(src_crt):
            return False, "证书文件缺失：期望 conf/node.key 与 conf/node.crt 存在"
        
        copied = []
        if not os.path.exists(dst_key):
            shutil.copy2(src_key, dst_key)
            try:
                os.chmod(dst_key, 0o600)
            except Exception:
                pass
            copied.append("ssl.key")
        if not os.path.exists(dst_crt):
            shutil.copy2(src_crt, dst_crt)
            copied.append("ssl.crt")
        
        if copied:
            return True, f"已生成 {', '.join(copied)} 以兼容网关证书命名。"
        else:
            return True, "证书文件已存在，无需复制。"
    except Exception as e:
        return False, f"复制 ssl.key/ssl.crt 失败: {e}"


def overlay_lightnode_certificates(source_conf_dir: str, target_conf_dir: str) -> Tuple[bool, str]:
    """
    覆盖轻节点证书：
        - 将 source_conf_dir 下的 node.key/node.crt/ca.crt 复制到 target_conf_dir：
          - node.key -> ssl.key
          - node.crt -> ssl.crt
          - ca.crt   -> ca.crt

    :param source_conf_dir: 源证书目录（通常为 output_dir/conf）
    :param target_conf_dir: 轻节点证书目录（通常为 output_dir/lightnode/conf）
    :return: (success, message)
    """
    try:
        src_key = os.path.join(source_conf_dir, "node.key")
        src_crt = os.path.join(source_conf_dir, "node.crt")
        src_ca = os.path.join(source_conf_dir, "ca.crt")

        if not (os.path.exists(src_key) and os.path.exists(src_crt) and os.path.exists(src_ca)):
            return False, "源证书缺失：期望存在 node.key/node.crt/ca.crt"

        os.makedirs(target_conf_dir, exist_ok=True)

        dst_key = os.path.join(target_conf_dir, "ssl.key")
        dst_crt = os.path.join(target_conf_dir, "ssl.crt")
        dst_ca = os.path.join(target_conf_dir, "ca.crt")

        for s, d in ((src_key, dst_key), (src_crt, dst_crt), (src_ca, dst_ca)):
            shutil.copy2(s, d)
            if d.endswith(".key"):
                try:
                    os.chmod(d, 0o600)
                except Exception:
                    pass
        return True, f"已覆盖轻节点证书到 {target_conf_dir}"
    except Exception as e:
        return False, f"覆盖轻节点证书失败: {e}"