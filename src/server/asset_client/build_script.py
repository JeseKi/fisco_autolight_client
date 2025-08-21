# -*- coding: utf-8 -*-
"""
下载 build_chain.sh 脚本
"""
import os
import requests
from requests.exceptions import RequestException
from .utils import make_executable, parse_text_response

def download_build_script(base_url: str, output_dir: str) -> tuple[bool, str]:
    """
    获取 build_chain.sh 文本并保存为可执行脚本。

    :param base_url: API 基础 URL
    :param output_dir: 目标目录（脚本保存在此目录下）。
    :return: (success, message)
    """
    url = f"{base_url}/lightnode/build_chain.sh"
    path = os.path.join(output_dir, "build_chain.sh")
    try:
        os.makedirs(output_dir, exist_ok=True)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()

        script_text = parse_text_response(resp)

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(script_text)
        
        make_executable(path)
        return True, f"build_chain.sh 已保存到 {path} 并授予可执行权限"
    except RequestException as e:
        return False, f"获取 build_chain.sh 失败: {e}"
    except Exception as e:
        return False, f"保存 build_chain.sh 失败: {e}"

