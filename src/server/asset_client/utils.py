# -*- coding: utf-8 -*-
"""
资源下载客户端的工具函数
"""
import os
import stat
import sys
import json
import requests

def make_executable(path: str):
    """赋予文件可执行权限"""
    if sys.platform != "win32":
        current = os.stat(path).st_mode
        os.chmod(path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

def parse_text_response(resp: requests.Response) -> str:
    """
    从 requests.Response 中解析文本内容，兼容多种格式。
    """
    content_type = resp.headers.get("Content-Type", "")
    text_content: str | None = None

    if "json" in content_type:
        try:
            data = resp.json()
            if isinstance(data, str):
                text_content = data
            elif isinstance(data, dict):
                for key in ("content", "script", "data", "genesis", "config"):
                    if key in data and isinstance(data[key], str):
                        text_content = data[key]
                        break
        except ValueError:
            pass

    if text_content is None:
        raw_text = resp.text
        stripped = raw_text.strip()
        if (stripped.startswith('"') and stripped.endswith('"')) or \
           (stripped.startswith("'") and stripped.endswith("'")):
            try:
                text_content = json.loads(stripped)
            except Exception:
                text_content = raw_text
        else:
            if "\\n" in raw_text and "\n" not in raw_text:
                try:
                    text_content = bytes(raw_text, "utf-8").decode("unicode_escape")
                except Exception:
                    text_content = raw_text
            else:
                text_content = raw_text
    
    assert text_content is not None
    return text_content.replace("\r\n", "\n").replace("\r", "\n")

def write_binary(content: bytes, dest_path: str):
    """写入二进制文件并赋予可执行权限"""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(content)
    make_executable(dest_path)
