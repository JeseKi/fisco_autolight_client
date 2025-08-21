# -*- coding: utf-8 -*-

"""
部署流程集成测试（轻量 mock）：只验证编排顺序与关键文件是否被写入。

仅测试公开接口 DeployCoordinator.execute_deployment。
"""

import os
import tempfile
from types import SimpleNamespace

from workers.deploy_coordinator import DeployCoordinator


class DummyResp:
    def __init__(self, headers=None, text="", content=b"", json_obj=None, status=200):
        self.headers = headers or {}
        self._text = text
        self._content = content
        self._json = json_obj
        self.status_code = status
    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError("http")
    @property
    def text(self):
        return self._text
    @property
    def content(self):
        return self._content
    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_execute_deployment_happy_path(monkeypatch):
    # Mock cert issuance: create conf/node.key, conf/node.crt, conf/ca.crt
    import cert_client as cert_mod
    def fake_issue(self, output_dir: str, node_id: str):
        conf = os.path.join(output_dir, "conf")
        os.makedirs(conf, exist_ok=True)
        with open(os.path.join(conf, "node.key"), "w") as f:
            f.write("key")
        with open(os.path.join(conf, "node.crt"), "w") as f:
            f.write("crt")
        with open(os.path.join(conf, "ca.crt"), "w") as f:
            f.write("ca")
        return True, "ok"
    monkeypatch.setattr(cert_mod.CertificateClient, "issue_new_certificate", fake_issue)

    # Mock asset_client requests for build_chain.sh, binaries, genesis, nodes
    import asset_client as ac_mod

    def fake_get(url, timeout=0):
        if url.endswith("/lightnode/build_chain.sh"):
            return DummyResp(headers={"Content-Type": "text/plain"}, text="#!/usr/bin/env bash\nmkdir -p nodes/lightnode\nmkdir -p nodes/lightnode/conf\n: > nodes/lightnode/start.sh\n: > nodes/lightnode/stop.sh\n")
        if url.endswith("/lightnode/executions/linux"):
            # 统一接口，返回直链字符串
            return DummyResp(headers={"Content-Type": "application/json"}, json_obj="http://cdn.example/fisco-bcos.bin")
        if url == "http://cdn.example/fisco-bcos.bin":
            # 二次下载真实二进制
            return DummyResp(headers={"Content-Type": "application/octet-stream"}, content=b"\x7fELFbin-real")
        if url.endswith("/lightnode/genesis"):
            return DummyResp(headers={"Content-Type": "text/plain"}, text="[genesis]\n")
        if url.endswith("/lightnode/nodes"):
            return DummyResp(headers={"Content-Type": "application/json"}, json_obj=["127.0.0.1:20200"])
        raise AssertionError("unexpected url: " + url)

    monkeypatch.setattr(ac_mod, "requests", SimpleNamespace(get=fake_get))

    # Run coordinator
    with tempfile.TemporaryDirectory() as tmp:
        coord = DeployCoordinator(progress_callback=lambda s: None)
        ok, msg = coord.execute_deployment(api_url="http://example/v1", output_dir=tmp, node_id="n1")
        assert ok, msg
        ln = os.path.join(tmp, "lightnode")
        assert os.path.isdir(ln)
        assert os.path.exists(os.path.join(ln, "config.genesis"))
        assert os.path.exists(os.path.join(ln, "nodes.json"))
        conf = os.path.join(ln, "conf")
        assert os.path.exists(os.path.join(conf, "ssl.key"))
        assert os.path.exists(os.path.join(conf, "ssl.crt"))


