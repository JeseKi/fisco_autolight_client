# -*- coding: utf-8 -*-

"""
部署协调器

文件功能:
    - 提供一个用于协调轻节点部署新流程的类，串联证书签发、脚本/二进制下载、脚本构建、目录提升、证书覆盖、链配置覆盖。

公开接口:
    - 类 DeployCoordinator:
        - 方法: execute_deployment(api_url, output_dir, node_id)
        - 方法: start_lightnode(lightnode_dir)
        - 方法: stop_lightnode(lightnode_dir)

内部方法:
    - _run_step(): 执行单个部署步骤

公开接口的 pydantic 模型:
    - 无。公开接口通过简单数据类型进行交互，不需要键值对模型。
"""

from typing import Callable, Tuple
import os

# 导入配置
from config import API_BASE_URL

# 动态导入客户端模块，避免在模块缺失时直接崩溃
try:
    from cert_client import CertificateClient
except ImportError:
    CertificateClient = None

try:
    from asset_client import AssetClient
except ImportError:
    AssetClient = None

from workers.cert_utils import copy_ssl_certificates, overlay_lightnode_certificates
from workers.lightnode_builder import LightnodeBuilder


class DeployCoordinator:
    """协调一键部署流程的类"""
    
    def __init__(self, progress_callback: Callable[[str], None] = None):
        """
        初始化部署协调器
        
        :param progress_callback: 进度回调函数，用于报告部署进度
        """
        self.progress_callback = progress_callback or (lambda x: None)
    
    def _report_progress(self, message: str) -> None:
        """报告进度的内部方法"""
        self.progress_callback(message)
    
    def _run_step(self, step_name: str, step_func: Callable[[], Tuple[bool, str]]) -> Tuple[bool, str]:
        """
        执行单个部署步骤
        
        :param step_name: 步骤名称
        :param step_func: 执行步骤的函数
        :return: (success, message) 元组
        """
        self._report_progress(step_name)
        return step_func()
    
    def execute_deployment(self, api_url: str = API_BASE_URL, output_dir: str = "", node_id: str = "") -> Tuple[bool, str]:
        """
        执行完整的轻节点部署流程：
            1) 申请并下载证书到 {output_dir}/conf
            2) 下载 build_chain.sh
            3) 下载 fisco-bcos / fisco-bcos-lightnode
            4) 使用脚本构建轻节点
            5) 提升 nodes/lightnode -> lightnode 并清理 nodes
            6) 覆盖轻节点证书
            7) 下载并覆盖 config.genesis / nodes.json
        
        :param api_url: API服务器地址，默认使用配置文件中的地址
        :param output_dir: 输出目录
        :param node_id: 节点ID
        :return: (success, message) 元组
        """
        if CertificateClient is None or AssetClient is None:
            return False, "错误: 客户端模块 (cert_client.py 或 asset_client.py) 未找到。"
        
        # 步骤 1: 申请和下载证书
        def cert_step():
            cert_client = CertificateClient(api_base_url=api_url)
            return cert_client.issue_new_certificate(
                output_dir=output_dir,
                node_id=node_id,
            )
        
        success, message = self._run_step("[1/7] 正在申请和下载证书...", cert_step)
        if not success:
            return False, f"证书部署失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 2: 下载 build_chain.sh
        def script_step():
            asset_client = AssetClient(api_base_url=api_url)
            return asset_client.download_build_script(output_dir)

        success, message = self._run_step("[2/7] 正在下载 build_chain.sh...", script_step)
        if not success:
            return False, f"脚本下载失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 3: 直接下载二进制（fisco-bcos 与 fisco-bcos-lightnode）
        def binaries_step():
            asset_client = AssetClient(api_base_url=api_url)
            return asset_client.download_binaries(output_dir)

        success, message = self._run_step("[3/7] 正在下载二进制文件...", binaries_step)
        if not success:
            return False, f"二进制下载失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 4: 构建轻节点
        def build_step():
            return LightnodeBuilder.run_build(output_dir)

        success, message = self._run_step("[4/7] 正在使用脚本构建轻节点...", build_step)
        if not success:
            return False, f"构建失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 5: 目录提升与清理
        def promote_step():
            return LightnodeBuilder.promote_and_cleanup(output_dir)

        success, message = self._run_step("[5/7] 正在调整目录结构...", promote_step)
        if not success:
            return False, f"目录调整失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 6: 覆盖轻节点证书（从 output_dir/conf 到 output_dir/lightnode/conf）
        def overlay_step():
            source_conf = os.path.join(output_dir, "conf")
            target_conf = os.path.join(output_dir, "lightnode", "conf")
            return overlay_lightnode_certificates(source_conf, target_conf)

        success, message = self._run_step("[6/7] 正在覆盖轻节点证书...", overlay_step)
        if not success:
            return False, f"证书覆盖失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 7: 下载并覆盖 config.genesis 与 nodes.json 到 lightnode/
        def chain_assets_step():
            asset_client = AssetClient(api_base_url=api_url)
            ln_dir = os.path.join(output_dir, "lightnode")
            s1, m1 = asset_client.download_genesis(ln_dir)
            if not s1:
                return False, m1
            s2, m2 = asset_client.download_nodes_json(ln_dir)
            if not s2:
                return False, m2
            return True, f"{m1}; {m2}"

        success, message = self._run_step("[7/7] 正在覆盖 config.genesis 与 nodes.json...", chain_assets_step)
        if not success:
            return False, f"链配置下载失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        return True, "一键部署成功完成！"

    # 可选: 启停封装（供 UI 使用）
    def start_lightnode(self, lightnode_dir: str) -> Tuple[bool, str]:
        return LightnodeBuilder.start(lightnode_dir)

    def stop_lightnode(self, lightnode_dir: str) -> Tuple[bool, str]:
        return LightnodeBuilder.stop(lightnode_dir)