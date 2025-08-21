# -*- coding: utf-8 -*-

"""
测试部署协调器模块

验证 DeployCoordinator 类是否能正确协调部署流程。
"""

import os
import tempfile
import sys
import os.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from deploy_coordinator import DeployCoordinator
from src.server.config import API_BASE_URL


def test_deploy_coordinator():
    """测试部署协调器的基本功能"""
    # 创建临时目录用于测试
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"使用临时目录进行测试: {temp_dir}")
        
        # 创建一个模拟的进度回调函数
        def progress_callback(message):
            print(f"进度: {message}")
        
        # 创建部署协调器实例
        coordinator = DeployCoordinator(progress_callback=progress_callback)
        
        # 由于我们没有实际的API服务器，这里会失败，但我们主要测试代码结构
        success, message = coordinator.execute_deployment(
            api_url=API_BASE_URL,  # 使用配置文件中的URL
            output_dir=temp_dir,
            node_id="test_node_001"
        )
        
        # 验证返回结果（由于没有实际服务器，应该会失败）
        print(f"部署结果: success={success}, message={message}")
        
        # 验证目录结构
        conf_dir = os.path.join(temp_dir, "conf")
        print(f"配置目录是否存在: {os.path.exists(conf_dir)}")


if __name__ == "__main__":
    test_deploy_coordinator()