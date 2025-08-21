# -*- coding: utf-8 -*-

"""
测试证书工具模块

验证 cert_utils.py 中的函数是否能正确工作。
"""

import os
import tempfile
from workers.cert_utils import copy_ssl_certificates


def test_copy_ssl_certificates():
    """测试复制SSL证书的功能"""
    # 创建临时目录用于测试
    with tempfile.TemporaryDirectory() as temp_dir:
        conf_dir = os.path.join(temp_dir, "conf")
        os.makedirs(conf_dir, exist_ok=True)
        
        # 创建模拟的证书文件
        node_key_path = os.path.join(conf_dir, "node.key")
        node_crt_path = os.path.join(conf_dir, "node.crt")
        
        with open(node_key_path, "w") as f:
            f.write("-----BEGIN PRIVATE KEY-----\\nMOCK PRIVATE KEY CONTENT\\n-----END PRIVATE KEY-----\\n")
        
        with open(node_crt_path, "w") as f:
            f.write("-----BEGIN CERTIFICATE-----\\nMOCK CERTIFICATE CONTENT\\n-----END CERTIFICATE-----\\n")
        
        # 测试复制功能
        success, message = copy_ssl_certificates(temp_dir)
        
        # 验证结果
        ssl_key_path = os.path.join(conf_dir, "ssl.key")
        ssl_crt_path = os.path.join(conf_dir, "ssl.crt")
        
        print(f"复制成功: {success}")
        print(f"消息: {message}")
        print(f"ssl.key 存在: {os.path.exists(ssl_key_path)}")
        print(f"ssl.crt 存在: {os.path.exists(ssl_crt_path)}")
        
        # 验证文件内容
        if os.path.exists(ssl_key_path):
            with open(ssl_key_path, "r") as f:
                content = f.read()
                print(f"ssl.key 内容: {content[:50]}...")


if __name__ == "__main__":
    test_copy_ssl_certificates()