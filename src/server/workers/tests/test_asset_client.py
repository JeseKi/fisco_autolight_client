# -*- coding: utf-8 -*- 

"""
测试 AssetClient 新增接口：
 - download_build_script
 - download_binaries
 - download_nodes_json
 - download_genesis

仅测试公开接口，通过 monkeypatch/stub 隔离网络调用。
"""

import os
import stat
import tempfile
from types import SimpleNamespace
import json

from asset_client import AssetClient


class FakeResponse:
    def __init__(self, *, status=200, headers=None, text="", content=b"", json_obj=None):
        self.status_code = status
        self.headers = headers or {}
        self._text = text
        self._content = content
        self._json_obj = json_obj

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError(f"HTTP {self.status_code}")

    @property
    def text(self):
        return self._text

    @property
    def content(self):
        return self._content

    def json(self):
        if self._json_obj is None:
            if self._text:
                return json.loads(self._text)
            raise ValueError("not json")
        return self._json_obj


def test_download_build_script_with_json_string(monkeypatch):
    client = AssetClient(api_base_url="http://example/v1")

    def fake_get(url, timeout=0):
        assert url.endswith("/lightnode/build_chain.sh")
        return FakeResponse(
            headers={"Content-Type": "application/json"},
            json_obj="#!/usr/bin/env bash\necho build\n",
        )

    monkeypatch.setattr("asset_client.build_script.requests", SimpleNamespace(get=fake_get))

    with tempfile.TemporaryDirectory() as tmp:
        ok, msg = client.download_build_script(tmp)
        assert ok, msg
        path = os.path.join(tmp, "build_chain.sh")
        assert os.path.exists(path)
        mode = os.stat(path).st_mode
        assert (mode & stat.S_IXUSR) != 0


def test_download_binaries_octet_stream(monkeypatch):
    client = AssetClient(api_base_url="http://example/v1")

    def fake_get(url, timeout=0, **kwargs):
        if "linux" in url:
            return FakeResponse(headers={"Content-Type": "application/json"}, json_obj="http://cdn.example/fisco-bcos.bin")
        if url == "http://cdn.example/fisco-bcos.bin":
            return FakeResponse(headers={"Content-Type": "application/octet-stream"}, content=b"\x7fELF...bin")
        raise AssertionError("unexpected url: " + url)

    monkeypatch.setattr("asset_client.binaries.requests", SimpleNamespace(get=fake_get))

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr("sys.platform", "linux")
        ok, msg = client.download_binaries(tmp)
        assert ok, msg
        p1 = os.path.join(tmp, "bin", "fisco-bcos")
        p2 = os.path.join(tmp, "fisco-bcos-lightnode")
        assert os.path.exists(p1) and os.path.exists(p2)
        assert os.stat(p1).st_size > 0 and os.stat(p2).st_size > 0
        assert (os.stat(p1).st_mode & stat.S_IXUSR) != 0
        assert (os.stat(p2).st_mode & stat.S_IXUSR) != 0


def test_download_nodes_json_list_form(monkeypatch):
    client = AssetClient(api_base_url="http://example/v1")

    def fake_get(url, timeout=0):
        assert url.endswith("/lightnode/nodes")
        return FakeResponse(headers={"Content-Type": "application/json"}, json_obj=["127.0.0.1:20200"])

    monkeypatch.setattr("asset_client.configs.requests", SimpleNamespace(get=fake_get))

    with tempfile.TemporaryDirectory() as tmp:
        ok, msg = client.download_nodes_json(tmp)
        assert ok, msg
        nodes_path = os.path.join(tmp, "nodes.json")
        assert os.path.exists(nodes_path)
        with open(nodes_path) as f:
            data = json.load(f)
            assert data == {"nodes": ["127.0.0.1:20200"]}


def test_download_genesis_text(monkeypatch):
    client = AssetClient(api_base_url="http://example/v1")

    def fake_get(url, timeout=0):
        assert url.endswith("/lightnode/genesis")
        return FakeResponse(headers={"Content-Type": "text/plain"}, text="[genesis]\nconf=1\n")

    monkeypatch.setattr("asset_client.configs.requests", SimpleNamespace(get=fake_get))

    with tempfile.TemporaryDirectory() as tmp:
        ok, msg = client.download_genesis(tmp)
        assert ok, msg
        path = os.path.join(tmp, "config.genesis")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
            assert content == "[genesis]\nconf=1\n"