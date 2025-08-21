# -*- coding: utf-8 -*-

"""
测试 LightnodeBuilder：
 - run_build（通过假脚本模拟构建产物）
 - promote_and_cleanup
 - start/stop（仅路径与调用存在性，不实际启动）
"""

import os
import tempfile

from workers.lightnode_builder import LightnodeBuilder


def test_promote_and_cleanup_basic():
    with tempfile.TemporaryDirectory() as tmp:
        nodes = os.path.join(tmp, "nodes")
        src = os.path.join(nodes, "lightnode")
        os.makedirs(os.path.join(src, "conf"), exist_ok=True)
        # 造一些文件
        with open(os.path.join(src, "start.sh"), "w") as f:
            f.write("#!/usr/bin/env bash\necho start\n")
        with open(os.path.join(src, "stop.sh"), "w") as f:
            f.write("#!/usr/bin/env bash\necho stop\n")

        ok, msg = LightnodeBuilder.promote_and_cleanup(tmp)
        assert ok, msg
        assert os.path.isdir(os.path.join(tmp, "lightnode"))
        assert not os.path.exists(nodes)


def test_run_build_checks_missing_files():
    with tempfile.TemporaryDirectory() as tmp:
        # 缺脚本
        ok, msg = LightnodeBuilder.run_build(tmp)
        assert not ok and "构建脚本不存在" in msg


