# -*- coding: utf-8 -*-
"""
测试节点 ID 处理逻辑
"""

import unittest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, mock_open

# 添加项目根目录到 Python 路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.server.main import AppState, is_node_deployed

class TestNodeIdHandling(unittest.TestCase):
    
    def setUp(self):
        """测试前的准备工作"""
        self.test_dir = tempfile.mkdtemp()
        self.app_state = AppState()
        self.app_state.current_node_dir = self.test_dir
        
    def tearDown(self):
        """测试后的清理工作"""
        # 清理测试目录
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
    def test_is_node_deployed_when_not_deployed(self):
        """测试节点未部署时的检查"""
        result = is_node_deployed(self.test_dir)
        self.assertFalse(result)
        
    def test_is_node_deployed_when_deployed(self):
        """测试节点已部署时的检查"""
        # 创建模拟的部署目录结构
        lightnode_dir = os.path.join(self.test_dir, "lightnode")
        conf_dir = os.path.join(lightnode_dir, "conf")
        os.makedirs(conf_dir, exist_ok=True)
        
        # 创建 node.nodeid 文件
        node_id_file = os.path.join(conf_dir, "node.nodeid")
        with open(node_id_file, "w") as f:
            f.write("test_node_id_12345")
            
        result = is_node_deployed(self.test_dir)
        self.assertTrue(result)
        
    def test_get_real_node_id_when_file_exists(self):
        """测试从文件获取真实节点 ID"""
        # 创建模拟的部署目录结构
        lightnode_dir = os.path.join(self.test_dir, "lightnode")
        conf_dir = os.path.join(lightnode_dir, "conf")
        os.makedirs(conf_dir, exist_ok=True)
        
        # 创建 node.nodeid 文件
        node_id_file = os.path.join(conf_dir, "node.nodeid")
        test_node_id = "abcdef1234567890"
        with open(node_id_file, "w") as f:
            f.write(test_node_id)
            
        real_node_id = self.app_state.get_real_node_id()
        self.assertEqual(real_node_id, test_node_id)
        
    def test_get_real_node_id_when_file_not_exists(self):
        """测试文件不存在时获取真实节点 ID"""
        real_node_id = self.app_state.get_real_node_id()
        self.assertIsNone(real_node_id)
        
    def test_save_session_with_real_node_id(self):
        """测试保存会话时使用真实节点 ID"""
        # 创建模拟的部署目录结构
        lightnode_dir = os.path.join(self.test_dir, "lightnode")
        conf_dir = os.path.join(lightnode_dir, "conf")
        os.makedirs(conf_dir, exist_ok=True)
        
        # 创建 node.nodeid 文件
        node_id_file = os.path.join(conf_dir, "node.nodeid")
        real_node_id = "real_node_id_abcdef"
        with open(node_id_file, "w") as f:
            f.write(real_node_id)
            
        # 设置一个临时的节点 ID
        self.app_state.deployed_node_id = "temp_id"
        
        # 保存会话
        self.app_state.save_session()
        
        # 验证 deployed_node_id 是否更新为真实 ID
        self.assertEqual(self.app_state.deployed_node_id, real_node_id)
        
    @patch("os.path.exists")
    def test_load_last_session_with_invalid_node(self, mock_exists):
        """测试加载会话时节点无效的情况"""
        # 模拟会话文件存在
        mock_exists.return_value = True
        
        # 创建模拟的会话数据
        session_data = {
            "deployed_node_id": "old_node_id",
            "node_pid": 12345
        }
        
        # 使用 mock_open 来模拟文件读取
        with patch("builtins.open", mock_open(read_data=json.dumps(session_data))):
            # 模拟节点未部署
            with patch("src.server.main.is_node_deployed", return_value=False):
                self.app_state.load_last_session()
                
                # 验证节点 ID 和 PID 被清空
                self.assertIsNone(self.app_state.deployed_node_id)
                self.assertIsNone(self.app_state.node_pid)

if __name__ == "__main__":
    unittest.main()