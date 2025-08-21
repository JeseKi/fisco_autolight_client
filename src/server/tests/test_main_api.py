# -*- coding: utf-8 -*-
"""
针对后端 API 的部署覆盖逻辑测试：
- 当节点目录非空时，/api/deploy 返回明确提示码，供前端弹窗确认
- 当 force_overwrite=True 时，接口应清空目录并返回成功（仅验证接口与副作用，
  不真正执行部署任务）

仅测试公开接口：FastAPI 路由 /api/deploy
"""

import os
import tempfile

from fastapi.testclient import TestClient

import main as main_mod


def test_deploy_check_and_overwrite(monkeypatch):
    # 使用一个临时目录作为节点目录
    with tempfile.TemporaryDirectory() as tmp:
        # 在临时目录写入一个文件，模拟“非空”
        with open(os.path.join(tmp, "dummy.txt"), "w", encoding="utf-8") as f:
            f.write("x")

        # 替换全局状态中的目录
        main_mod.state.current_node_dir = tmp

        # 避免真的执行部署任务
        monkeypatch.setattr(main_mod, "run_deployment_task", lambda: None)

        client = TestClient(main_mod.app)

        # 1) 先检查：应显示被占用
        r0 = client.get("/api/deploy/check_dir")
        assert r0.status_code == 200
        body0 = r0.json()
        assert body0["success"] is True
        assert body0["data"]["occupied"] is True

        # 2) 确认覆盖：调用 overwrite 接口，应清空目录并返回成功
        r2 = client.post("/api/deploy/overwrite", json={})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["success"] is True
        # 目录会被清空并重建
        assert os.path.exists(tmp)
        assert os.listdir(tmp) == []



