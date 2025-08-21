# -*- coding: utf-8 -*-
"""
统一的路径管理服务。

文件功能:
    - 为项目的不同部分提供统一、可靠的路径查找功能。
    - 集中管理项目中的关键目录，如节点目录、控制台目录等。

公开接口:
    - get_node_dir(): 获取节点的根目录。
    - get_console_dir(): 获取控制台的安装目录。
    - get_build_chain_layout_paths(): 获取节点构建后的相关路径布局。
"""

from pathlib import Path

def get_node_dir() -> Path:
    """获取节点部署的根目录。
    
    该路径基于 main.py 中定义的 `NODE_DIR`。
    """
    # 从当前文件 (__file__) 出发，向上回溯到 src/server/ 目录，然后拼接 node
    # __file__ is src/server/service/paths.py
    # .parent is src/server/service/
    # .parent.parent is src/server/
    # / "node" is src/server/node
    server_dir = Path(__file__).parent.parent
    return server_dir / "node"

def get_console_dir() -> Path:
    """获取控制台的安装目录。"""
    # 控制台位于 node 目录平级的 console 目录
    # 比如 src/server/console
    return get_node_dir().parent / "console"


def get_build_chain_layout_paths() -> dict[str, Path]:
    """获取节点构建后的相关路径布局。
    
    Returns:
        一个字典，包含基础目录、轻节点目录和SDK目录的路径。
        注意：SDK目录现在位于 lightnode/sdk。
    """
    node_dir = get_node_dir()
    lightnode_dir = node_dir / "lightnode"
    sdk_dir = lightnode_dir / "sdk"
    
    return {
        "base": node_dir,
        "lightnode_dir": lightnode_dir,
        "sdk_dir": sdk_dir,
    }