# -*- coding: utf-8 -*-
"""
下载配置文件 (genesis, nodes.json, config.ini)
"""
import os
import json
import requests
from requests.exceptions import RequestException
from .utils import parse_text_response

def download_genesis(base_url: str, output_dir: str) -> tuple[bool, str]:
    """
    下载并保存 config.genesis 文件。
    """
    genesis_url = f"{base_url}/lightnode/genesis"
    genesis_path = os.path.join(output_dir, "config.genesis")
    try:
        response = requests.get(genesis_url, timeout=30)
        response.raise_for_status()

        genesis_text = parse_text_response(response)
        
        with open(genesis_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(genesis_text)
        return True, f"config.genesis 已保存到 {output_dir}"
    except RequestException as e:
        return False, f"获取 config.genesis 失败: {e}"
    except Exception as e:
        return False, f"保存 config.genesis 失败: {e}"

def download_nodes_json(base_url: str, output_dir: str) -> tuple[bool, str]:
    """
    单独下载并保存 nodes.json 文件，兼容 List[str] 或 {"nodes": List[str]}。
    """
    nodes_url = f"{base_url}/lightnode/nodes"
    nodes_path = os.path.join(output_dir, "nodes.json")
    try:
        os.makedirs(output_dir, exist_ok=True)
        resp = requests.get(nodes_url, timeout=30)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        parsed_nodes = None

        if "json" in content_type:
            try:
                parsed_nodes = resp.json()
            except ValueError:
                parsed_nodes = None

        if parsed_nodes is None:
            raw_text = resp.text.strip()
            if (raw_text.startswith('"') and raw_text.endswith('"')) or \
               (raw_text.startswith("'") and raw_text.endswith("'")):
                try:
                    raw_text = json.loads(raw_text)
                except Exception:
                    pass
            try:
                parsed_nodes = raw_text if isinstance(raw_text, (list, dict)) else json.loads(raw_text)
            except Exception:
                parsed_nodes = None

        nodes_obj: dict[str, list[str]] | None = None
        if isinstance(parsed_nodes, list) and all(isinstance(item, str) for item in parsed_nodes):
            nodes_obj = {"nodes": parsed_nodes}
        elif isinstance(parsed_nodes, dict) and isinstance(parsed_nodes.get("nodes"), list) and all(isinstance(item, str) for item in parsed_nodes["nodes"]):
            nodes_obj = {"nodes": parsed_nodes["nodes"]}
        else:
            return False, "节点列表格式错误：期望为 List[str] 或 {\"nodes\": List[str]}"

        with open(nodes_path, "w", encoding="utf-8") as nf:
            json.dump(nodes_obj, nf, ensure_ascii=False, indent=2)
        return True, f"nodes.json 已保存到 {output_dir}"
    except RequestException as e:
        return False, f"获取 nodes.json 失败: {e}"
    except Exception as e:
        return False, f"保存 nodes.json 失败: {e}"

def download_config(base_url: str, output_dir: str) -> tuple[bool, str]:
    """
    获取 config.ini 配置文件内容并保存到本地。
    (兼容保留)
    """
    config_url = f"{base_url}/lightnode/config"
    config_path = os.path.join(output_dir, "config.ini")
    
    try:
        response = requests.get(config_url, timeout=30)
        response.raise_for_status()
        
        config_text = parse_text_response(response)

        with open(config_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(config_text)

        success, message = download_nodes_json(base_url, output_dir)
        if not success:
            return False, message

        return True, f"config.ini 和 nodes.json 已成功保存到 {output_dir}"
    except RequestException as e:
        return False, f"获取 config.ini 失败: {e}"
    except Exception as e:
        return False, f"保存 config.ini 失败: {e}"