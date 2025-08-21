# -*- coding: utf-8 -*-

"""
通用数据模型（schemas）

文件功能:
    - 定义跨模块使用的 pydantic 模型。

公开接口:
    - 类 NodeStatus(BaseModel): 用于表示节点状态信息（区块高度、节点ID、P2P连接数）。

内部方法:
    - 无。

公开接口的 pydantic 模型:
    - NodeStatus
"""

from pydantic import BaseModel


class NodeStatus(BaseModel):
    """节点状态信息模型"""
    block_height: int
    node_id: str
    p2p_connection_count: int


