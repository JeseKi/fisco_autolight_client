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

from typing import Callable, Tuple, Optional
import os
import re
import stat
import subprocess
from loguru import logger

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

from .cert_utils import overlay_lightnode_certificates
from .lightnode_builder import LightnodeBuilder

# 导入控制台部署服务
from service.console_deploy import deploy_console


class DeployCoordinator:
    """协调一键部署流程的类"""
    
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None, pid_callback: Optional[Callable[[int], None]] = None):
        """
        初始化部署协调器
        
        :param progress_callback: 进度回调函数，用于报告部署进度
        """
        self.progress_callback = progress_callback or (lambda x: None)
        self.pid_callback: Optional[Callable[[int], None]] = pid_callback
    
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
        
        # 步骤 1/9: 申请和下载证书
        def cert_step():
            if CertificateClient is None:
                return False, "证书客户端模块未正确导入"
            cert_client = CertificateClient(api_base_url=api_url)
            return cert_client.issue_new_certificate(
                output_dir=output_dir,
                node_id=node_id,
            )
        
        success, message = self._run_step("[1/9] 正在申请和下载证书...", cert_step)
        if not success:
            return False, f"证书部署失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 2/9: 下载 build_chain.sh
        def script_step():
            if AssetClient is None:
                return False, "资源客户端模块未正确导入"
            asset_client = AssetClient(api_base_url=api_url)
            return asset_client.download_build_script(output_dir)

        success, message = self._run_step("[2/9] 正在下载 build_chain.sh...", script_step)
        if not success:
            return False, f"脚本下载失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 3/9: 直接下载二进制（fisco-bcos 与 fisco-bcos-lightnode）
        def binaries_step():
            if AssetClient is None:
                return False, "资源客户端模块未正确导入"
            asset_client = AssetClient(api_base_url=api_url)
            return asset_client.download_binaries(output_dir)

        success, message = self._run_step("[3/9] 正在下载二进制文件...", binaries_step)
        if not success:
            return False, f"二进制下载失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 4/9: 构建轻节点
        def build_step():
            return LightnodeBuilder.run_build(output_dir)

        success, message = self._run_step("[4/9] 正在使用脚本构建轻节点...", build_step)
        if not success:
            return False, f"构建失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 5/9: 目录提升与清理
        def promote_step():
            return LightnodeBuilder.promote_and_cleanup(output_dir)

        success, message = self._run_step("[5/9] 正在调整目录结构...", promote_step)
        if not success:
            return False, f"目录调整失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 6/9: 覆盖轻节点证书（从 output_dir/conf 到 output_dir/lightnode/conf）
        def overlay_step():
            source_conf = os.path.join(output_dir, "conf")
            target_conf = os.path.join(output_dir, "lightnode", "conf")
            return overlay_lightnode_certificates(source_conf, target_conf)

        success, message = self._run_step("[6/9] 正在覆盖轻节点证书...", overlay_step)
        if not success:
            return False, f"证书覆盖失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 7/9: 下载并覆盖 config.genesis 与 nodes.json 到 lightnode/
        def chain_assets_step():
            if AssetClient is None:
                return False, "资源客户端模块未正确导入"
            asset_client = AssetClient(api_base_url=api_url)
            ln_dir = os.path.join(output_dir, "lightnode")
            s1, m1 = asset_client.download_genesis(ln_dir)
            if not s1:
                return False, m1
            s2, m2 = asset_client.download_nodes_json(ln_dir)
            if not s2:
                return False, m2
            return True, f"{m1}; {m2}"

        success, message = self._run_step("[7/9] 正在覆盖 config.genesis 与 nodes.json...", chain_assets_step)
        if not success:
            return False, f"链配置下载失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 8/9: 启动轻节点（确保控制台后续可连接）
        def start_lightnode_step():
            """参考 main.py 的启动逻辑：调用 start.sh、检查返回码、解析 PID。"""
            ln_dir = os.path.join(output_dir, "lightnode")
            script = os.path.join(ln_dir, "start.sh")
            logger.info(f"[START] 轻节点启动准备: ln_dir={ln_dir}")
            if not os.path.exists(script):
                logger.error(f"未找到启动脚本: {script}")
                return False, f"启动脚本不存在: {script}"

            # 记录权限与大小等元信息
            try:
                st = os.stat(script)
                mode = stat.S_IMODE(st.st_mode)
                logger.info(f"start.sh 权限: {oct(mode)}, 大小: {st.st_size} 字节")
            except Exception as e:
                logger.warning(f"无法读取 start.sh 元信息: {e}")

            try:
                result = subprocess.run([
                    "bash", "start.sh"
                ], cwd=ln_dir, capture_output=True, text=True, timeout=30)

                stdout = (result.stdout or "").strip()
                stderr = (result.stderr or "").strip()

                logger.info(f"start.sh 返回码: {result.returncode}")
                if stdout:
                    logger.info(f"start.sh STDOUT:\n{stdout}")
                if stderr:
                    logger.info(f"start.sh STDERR:\n{stderr}")

                if result.returncode != 0:
                    return False, f"启动脚本执行失败，退出码: {result.returncode}，stderr: {stderr}"

                # 解析 PID（匹配 pid=12345 或 pid is 12345）
                pid_match = re.search(r"pid[=\s]+(\d+)", stdout)
                if not pid_match:
                    logger.error("未从启动输出解析到 PID，正则 pid[=\\s]+(\\d+) 未命中。")
                    return False, "无法从启动脚本输出中解析出 PID。"

                pid = int(pid_match.group(1))
                logger.info(f"解析到 PID: {pid}")
                # 通过回调让调用方（main.py）记录 PID
                if self.pid_callback is not None:
                    try:
                        self.pid_callback(pid)
                    except Exception:
                        # 回调失败不应影响启动结果
                        logger.warning("pid_callback 回调执行失败，已忽略。")

                return True, f"轻节点启动成功，PID: {pid}"
            except subprocess.TimeoutExpired:
                logger.error("start.sh 执行超时 (30s)")
                return False, "启动脚本执行超时。"
            except Exception as e:
                logger.exception("启动异常")
                return False, f"启动异常: {e}"

        success, message = self._run_step("[8/9] 正在启动轻节点...", start_lightnode_step)
        if not success:
            return False, f"启动轻节点失败: {message}"
        self._report_progress(f"[SUCCESS] {message}")

        # 步骤 9/9: 部署控制台（部署时将自动执行一次命令）
        def console_deploy_step():
            try:
                self._report_progress("正在部署控制台...")
                deploy_console(api_url=api_url, node_id=node_id) # 默认使用 20200 端口
                return True, "控制台部署成功"
            except Exception as e:
                return False, f"控制台部署失败: {str(e)}"
        
        success, message = self._run_step("[9/9] 正在部署控制台...", console_deploy_step)
        if not success:
            # 这里可以选择是否将整个部署标记为失败，暂时只记录错误
            self._report_progress(f"[WARN] {message}")
        else:
            self._report_progress(f"[SUCCESS] {message}")

        return True, "一键部署成功完成！"

    # 可选: 启停封装（供 UI 使用）
    def start_lightnode(self, lightnode_dir: str) -> Tuple[bool, str]:
        return LightnodeBuilder.start(lightnode_dir)

    def stop_lightnode(self, lightnode_dir: str) -> Tuple[bool, str]:
        return LightnodeBuilder.stop(lightnode_dir)