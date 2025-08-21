# -*- coding: utf-8 -*-

"""
轻节点构建器（LightnodeBuilder）

文件功能:
    - 提供使用 build_chain.sh 构建轻节点的能力
    - 提供将 nodes/lightnode 提升为 lightnode 并清理 nodes 的能力
    - 提供轻节点的启动与停止能力（调用 start.sh/stop.sh）

公开接口:
    - 类 LightnodeBuilder
        - 方法: run_build(output_dir, ports="30300,20200", layout="127.0.0.1:4") -> tuple[bool, str]
        - 方法: promote_and_cleanup(output_dir) -> tuple[bool, str]
        - 方法: start(lightnode_dir) -> tuple[bool, str]
        - 方法: stop(lightnode_dir) -> tuple[bool, str]

内部方法:
    - _ensure_executable(path): 确保文件有可执行权限

公开接口的 pydantic 模型:
    - 无。
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from typing import Tuple


class LightnodeBuilder:
    """负责执行 build_chain.sh 及目录提升清理的帮助类"""

    @staticmethod
    def _ensure_executable(path: str) -> None:
        try:
            mode = os.stat(path).st_mode
            os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except Exception:
            # 权限失败不应中断流程，但记录由上层处理
            pass

    @staticmethod
    def run_build(output_dir: str, ports: str = "30300,20200", layout: str = "127.0.0.1:4") -> Tuple[bool, str]:
        """
        在 output_dir 下执行构建命令：
        bash build_chain.sh -p {ports} -l {layout} -e ./bin/fisco-bcos -L ./fisco-bcos-lightnode

        要求：
        - {output_dir}/build_chain.sh 存在且可执行
        - {output_dir}/bin/fisco-bcos 存在
        - {output_dir}/fisco-bcos-lightnode 存在
        """
        try:
            script_path = os.path.join(output_dir, "build_chain.sh")
            if not os.path.exists(script_path):
                return False, f"构建脚本不存在: {script_path}"
            bcos_path = os.path.join(output_dir, "bin", "fisco-bcos")
            lightnode_bin_path = os.path.join(output_dir, "fisco-bcos-lightnode")
            if not os.path.exists(bcos_path):
                return False, f"缺少 fisco-bcos 可执行文件: {bcos_path}"
            if not os.path.exists(lightnode_bin_path):
                return False, f"缺少 fisco-bcos-lightnode 可执行文件: {lightnode_bin_path}"

            # 确保脚本与二进制可执行
            LightnodeBuilder._ensure_executable(script_path)
            LightnodeBuilder._ensure_executable(bcos_path)
            LightnodeBuilder._ensure_executable(lightnode_bin_path)

            cmd = [
                "bash",
                "build_chain.sh",
                "-p", ports,
                "-l", layout,
                "-e", "./bin/fisco-bcos",
                "-L", "./fisco-bcos-lightnode",
            ]
            result = subprocess.run(
                cmd,
                cwd=output_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False, f"构建失败: {result.stderr.strip() or result.stdout.strip()}"

            # 验证是否生成了 nodes/lightnode 目录
            expected_dir = os.path.join(output_dir, "nodes", "lightnode")
            if not os.path.isdir(expected_dir):
                # 兼容部分脚本可能将 lightnode 置于 nodes/127.0.0.1/lightnode 等路径
                # 尝试在 nodes 下查找名为 lightnode 的目录
                fallback_dir = None
                nodes_root = os.path.join(output_dir, "nodes")
                if os.path.isdir(nodes_root):
                    for root, dirs, _files in os.walk(nodes_root):
                        if "lightnode" in dirs:
                            fallback_dir = os.path.join(root, "lightnode")
                            break
                if not (fallback_dir and os.path.isdir(fallback_dir)):
                    return False, "构建完成但未找到 nodes 内的 lightnode 目录"
            # 构建完成
            return True, "轻节点构建完成"
        except Exception as e:
            return False, f"执行构建失败: {e}"

    @staticmethod
    def promote_and_cleanup(output_dir: str) -> Tuple[bool, str]:
        """
        将 {output_dir}/nodes/lightnode 提升为 {output_dir}/lightnode 并删除 {output_dir}/nodes。
        若 nodes 下的 lightnode 不在第一层，自动搜索其位置。
        """
        try:
            nodes_root = os.path.join(output_dir, "nodes")
            if not os.path.isdir(nodes_root):
                return False, f"未找到 nodes 目录: {nodes_root}"

            # 默认路径
            src_lightnode = os.path.join(nodes_root, "lightnode")
            if not os.path.isdir(src_lightnode):
                # 搜索备选
                src_lightnode = None
                for root, dirs, _files in os.walk(nodes_root):
                    if "lightnode" in dirs:
                        src_lightnode = os.path.join(root, "lightnode")
                        break
                if src_lightnode is None:
                    return False, "未在 nodes 下找到 lightnode 目录"

            dst_lightnode = os.path.join(output_dir, "lightnode")
            # 如果目标已存在，先删除以确保干净
            if os.path.exists(dst_lightnode):
                shutil.rmtree(dst_lightnode, ignore_errors=True)
            try:
                shutil.move(src_lightnode, dst_lightnode)
            except Exception:
                # 回退到 copytree（跨设备/权限问题时）
                shutil.copytree(src_lightnode, dst_lightnode, dirs_exist_ok=True)

            # 拷贝SDK目录
            # 查找nodes目录下的sdk目录
            sdk_src_dir = None
            for root, dirs, _files in os.walk(nodes_root):
                if "sdk" in dirs:
                    sdk_src_dir = os.path.join(root, "sdk")
                    break
            
            if sdk_src_dir and os.path.isdir(sdk_src_dir):
                sdk_dst_dir = os.path.join(dst_lightnode, "sdk")
                # 如果目标sdk目录已存在，先删除
                if os.path.exists(sdk_dst_dir):
                    shutil.rmtree(sdk_dst_dir, ignore_errors=True)
                try:
                    shutil.copytree(sdk_src_dir, sdk_dst_dir)
                    print(f"SDK目录已拷贝: {sdk_src_dir} -> {sdk_dst_dir}")
                except Exception as e:
                    print(f"拷贝SDK目录失败: {e}")
                    # 即使拷贝失败，也不应该中断整个流程
            else:
                print("未找到SDK目录")

            # 确保 start/stop/lightnode 可执行
            for name in ("start.sh", "stop.sh", "fisco-bcos-lightnode"):
                p = os.path.join(dst_lightnode, name)
                if os.path.exists(p):
                    LightnodeBuilder._ensure_executable(p)

            # 清理 nodes 目录
            shutil.rmtree(nodes_root, ignore_errors=True)
            return True, f"目录提升完成: {dst_lightnode}"
        except Exception as e:
            return False, f"目录提升失败: {e}"

    @staticmethod
    def start(lightnode_dir: str) -> Tuple[bool, str]:
        """调用 lightnode/start.sh 启动节点"""
        try:
            script = os.path.join(lightnode_dir, "start.sh")
            if not os.path.exists(script):
                return False, f"未找到启动脚本: {script}"
            LightnodeBuilder._ensure_executable(script)
            result = subprocess.run([
                "bash", "start.sh"
            ], cwd=lightnode_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if result.returncode != 0:
                return False, f"启动失败: {result.stderr.strip() or result.stdout.strip()}"
            return True, "轻节点已启动"
        except Exception as e:
            return False, f"启动异常: {e}"

    @staticmethod
    def stop(lightnode_dir: str) -> Tuple[bool, str]:
        """调用 lightnode/stop.sh 停止节点"""
        try:
            script = os.path.join(lightnode_dir, "stop.sh")
            if not os.path.exists(script):
                return False, f"未找到停止脚本: {script}"
            LightnodeBuilder._ensure_executable(script)
            result = subprocess.run([
                "bash", "stop.sh"
            ], cwd=lightnode_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if result.returncode != 0:
                return False, f"停止失败: {result.stderr.strip() or result.stdout.strip()}"
            return True, "轻节点已停止"
        except Exception as e:
            return False, f"停止异常: {e}"


