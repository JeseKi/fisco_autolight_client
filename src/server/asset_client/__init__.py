# -*- coding: utf-8 -*-
"""
资源下载客户端

负责从服务器下载节点的静态资源，如 build_chain.sh、二进制可执行文件、config.genesis、nodes.json 等。

公开接口:
    - 类 AssetClient
        - 方法: download_build_script(output_dir) -> tuple[bool, str]
        - 方法: download_binaries(output_dir) -> tuple[bool, str]
        - 方法: download_nodes_json(output_dir) -> tuple[bool, str]
        - 方法: download_genesis(output_dir) -> tuple[bool, str]
        - 方法: download_config(output_dir) -> tuple[bool, str]  (兼容保留，部署流程不再依赖)
        - 方法: download_binary(output_dir) -> tuple[bool, str] (旧版方法)
"""
from .build_script import download_build_script as download_build_script_func
from .binaries import download_binaries as download_binaries_func, download_binary as download_binary_func
from .configs import download_genesis as download_genesis_func, \
                     download_nodes_json as download_nodes_json_func, \
                     download_config as download_config_func

class AssetClient:
    """封装了静态资源下载逻辑的客户端"""

    def __init__(self, api_base_url: str):
        self.base_url = api_base_url.rstrip('/')

    def download_build_script(self, output_dir: str) -> tuple[bool, str]:
        return download_build_script_func(self.base_url, output_dir)

    def download_binaries(self, output_dir: str) -> tuple[bool, str]:
        return download_binaries_func(self.base_url, output_dir)

    def download_nodes_json(self, output_dir: str) -> tuple[bool, str]:
        return download_nodes_json_func(self.base_url, output_dir)

    def download_genesis(self, output_dir: str) -> tuple[bool, str]:
        return download_genesis_func(self.base_url, output_dir)

    def download_config(self, output_dir: str) -> tuple[bool, str]:
        return download_config_func(self.base_url, output_dir)
    
    def download_binary(self, output_dir: str) -> tuple[bool, str]:
        return download_binary_func(self.base_url, output_dir)
