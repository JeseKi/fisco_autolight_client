# -*- coding: utf-8 -*-
"""
下载 fisco-bcos 二进制文件
"""
import os
import sys
import requests
from requests.exceptions import RequestException
import tarfile
import tempfile
import shutil
from .utils import write_binary, make_executable

def download_binaries(base_url: str, output_dir: str) -> tuple[bool, str]:
    """
    依据 API 文档，仅调用 /v1/lightnode/executions/{platform} 获取可执行文件（或其直链），
    并将同一份二进制分别保存为：
      - {output_dir}/bin/fisco-bcos
      - {output_dir}/fisco-bcos-lightnode
    注：根据业务约定，两者当前内容相同。

    :param base_url: API 基础 URL
    :param output_dir: 目标根目录。
    :return: (success, message)
    """
    if sys.platform == "win32":
        return False, "Windows 系统不支持轻节点部署"

    try:
        platform_param = "linux" if sys.platform.startswith("linux") else ("macos" if sys.platform == "darwin" else None)
        if platform_param is None:
            return False, f"不支持的操作系统: {sys.platform}"

        endpoint = f"{base_url}/lightnode/executions/{platform_param}"
        resp = requests.get(endpoint, timeout=60)
        resp.raise_for_status()
        ct = resp.headers.get("Content-Type", "")

        binary_bytes: bytes | None = None
        if "octet-stream" in ct or (resp.content and len(resp.content) > 0 and not resp.text.strip()):
            binary_bytes = resp.content
        else:
            url_text: str | None = None
            if "json" in ct:
                try:
                    parsed = resp.json()
                    if isinstance(parsed, str):
                        url_text = parsed
                except Exception:
                    url_text = None
            if url_text is None:
                url_text = resp.text
            url_text = (url_text or "").strip().strip('"')
            if not url_text:
                return False, "执行文件下载链接为空"
            
            resp2 = requests.get(url_text, timeout=180)
            resp2.raise_for_status()
            binary_bytes = resp2.content

        if not binary_bytes:
            return False, "执行文件内容为空"

        dest_bcos = os.path.join(output_dir, "bin", "fisco-bcos")
        dest_light = os.path.join(output_dir, "fisco-bcos-lightnode")
        write_binary(binary_bytes, dest_bcos)
        write_binary(binary_bytes, dest_light)

        return True, "二进制文件已下载并设置可执行权限"
    except RequestException as e:
        return False, f"下载二进制失败: {e}"
    except Exception as e:
        return False, f"保存二进制失败: {e}"

def download_binary(base_url: str, output_dir: str) -> tuple[bool, str]:
    """
    根据当前操作系统，下载 fisco-bcos 可执行文件（从 tar.gz 压缩包中解压）。
    (旧版方法)
    """
    if sys.platform == "win32":
        return False, "Windows 系统不支持下载二进制文件"
    
    platform = ""
    platform_param = ""
    if sys.platform == "darwin":
        platform = "mac"
        platform_param = "macos"
    elif sys.platform.startswith("linux"):
        platform = "linux"
        platform_param = "linux"
    else:
        return False, f"不支持的操作系统: {sys.platform}"

    if platform == "linux":
        compressed_name = "fisco-bcos-linux-x86_64.tar.gz"
    elif platform == "mac":
        compressed_name = "fisco-bcos-macOS-x86_64.tar.gz"
    else:
        return False, f"不支持的操作系统: {sys.platform}"

    binary_url = f"{base_url}/lightnode/executions/{platform_param}"
    binary_path = os.path.join(output_dir, "fisco-bcos")
    compressed_path = os.path.join(output_dir, compressed_name)

    try:
        response = requests.get(binary_url, timeout=30)
        response.raise_for_status()
        
        actual_download_url = response.text.strip().strip('"')

        response = requests.get(actual_download_url, timeout=180)
        response.raise_for_status()

        with open(compressed_path, "wb") as f:
            f.write(response.content)

        with tarfile.open(compressed_path, "r:gz") as tar:
            with tempfile.TemporaryDirectory() as tmpdir:
                tar.extractall(path=tmpdir)
                
                extracted_binary = None
                for root, _, files in os.walk(tmpdir):
                    if "fisco-bcos" in files:
                        extracted_binary = os.path.join(root, "fisco-bcos")
                        break
                
                if extracted_binary and os.path.exists(extracted_binary):
                    if os.path.exists(binary_path):
                        os.remove(binary_path)
                    shutil.copy2(extracted_binary, binary_path)
                else:
                    for root, _, files in os.walk(tmpdir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.access(file_path, os.X_OK):
                                extracted_binary = file_path
                                if os.path.exists(binary_path):
                                    os.remove(binary_path)
                                shutil.copy2(extracted_binary, binary_path)
                                break
                        if os.path.exists(binary_path):
                            break
                    else:
                        return False, "在压缩包中未找到可执行文件"

        if os.path.exists(compressed_path):
            os.remove(compressed_path)

        make_executable(binary_path)

        return True, "fisco-bcos 已成功下载、解压并设置权限。"
    except RequestException as e:
        return False, f"下载 {compressed_name} 失败: {e}"
    except tarfile.TarError as e:
        return False, f"解压 {compressed_name} 失败: {e}"
    except Exception as e:
        return False, f"保存 fisco-bcos 失败: {e}"
