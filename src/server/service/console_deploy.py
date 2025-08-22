"""
控制台部署服务 (v2)。

负责配置和部署 FISCO 控制台。
"""

from __future__ import annotations

import shutil
from pathlib import Path
import re
import subprocess
from typing import Optional
from loguru import logger
from service.paths import get_console_dir, get_build_chain_layout_paths
from cert_client import CertificateClient


def _get_console_dir() -> Path:
    """获取控制台目录。"""
    return get_console_dir()


def _ensure_console_exists() -> None:
    """确保控制台目录存在。"""
    console_dir = _get_console_dir()
    if not console_dir.exists():
        raise RuntimeError(f"控制台目录不存在: {console_dir}")


def download_console_if_not_exists(console_version: str = "latest") -> None:
    """如果控制台目录不存在，则下载控制台。
    
    Args:
        console_version: 要下载的控制台版本。默认为 "latest"。
    """
    console_dir = _get_console_dir()
    
    if console_dir.exists():
        logger.info(f"控制台目录已存在: {console_dir}，跳过下载。")
        return
    
    logger.info(f"控制台目录不存在，开始下载控制台到: {console_dir.parent}")
    
    # 从当前工作目录出发，找到 download_console.sh 脚本的路径
    # cwd is src/server when running python main.py directly
    # / "download_console.sh" is src/server/download_console.sh
    script_path = Path.cwd() / "download_console.sh"
    
    if not script_path.exists():
        raise RuntimeError(f"下载脚本不存在: {script_path}")
    
    # 构建命令
    cmd = ["bash", str(script_path)]
    if console_version != "latest":
        cmd.extend(["-c", console_version])
    
    # 执行命令
    try:
        # 切换到 console_dir 的父目录执行脚本，这样解压后的 console 目录会直接放在正确的位置
        result = subprocess.run(cmd, cwd=console_dir.parent, check=True, capture_output=True, text=True)
        logger.info(f"控制台下载并解压成功。stdout: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logger.error(f"下载控制台失败: {e.stderr}")
        raise RuntimeError(f"下载控制台失败: {e.stderr}") from e
    except Exception as e:
        logger.error(f"下载控制台时发生未知错误: {str(e)}")
        raise RuntimeError(f"下载控制台时发生未知错误: {str(e)}") from e

def _is_console_configured() -> bool:
    """检查控制台是否已配置。"""
    console_dir = _get_console_dir()
    config_file = console_dir / "conf" / "config.toml"
    return config_file.exists()


def _get_console_config_paths() -> dict[str, Path]:
    """获取控制台配置路径。"""
    console_dir = _get_console_dir()
    return {
        "base": console_dir,
        "conf": console_dir / "conf",
        "config_example": console_dir / "conf" / "config-example.toml",
        "config": console_dir / "conf" / "config.toml",
    }



def deploy_console(rpc_port: int = 20200, api_url: Optional[str] = None, node_id: Optional[str] = None) -> None:
    """部署控制台。
    
    1. 拷贝配置文件
    2. 替换配置文件中的默认端口（如果节点未使用默认端口）
    3. 拷贝节点SDK证书到控制台配置目录
    4. 如果提供了 api_url 和 node_id，则重新签发控制台SDK证书
    """
    # 下载控制台（如果不存在）
    download_console_if_not_exists()
    
    # 确保控制台存在（这一步现在应该总是成功的，除非下载失败）
    _ensure_console_exists()
    
    # 获取路径
    console_paths = _get_console_config_paths()
    # 在部署控制台时，SDK目录还在nodes/127.0.0.1/sdk下
    node_paths = get_build_chain_layout_paths()
    
    # 1. 拷贝配置文件
    config_example = console_paths["config_example"]
    config_target = console_paths["config"]
    
    if not config_target.exists():
        logger.info(f"拷贝控制台配置文件: {config_example} -> {config_target}")
        shutil.copy2(config_example, config_target)
    else:
        logger.info("控制台配置文件已存在")
    
    # 2. 替换配置文件中的默认端口
    if rpc_port != 20200:
        logger.info(f"更新配置文件中的RPC端口为: {rpc_port}")
        _update_console_config_port(config_target, rpc_port)
    else:
        logger.info("使用默认RPC端口: 20200")
    
    # 3. 拷贝节点SDK证书到控制台配置目录
    logger.info("拷贝节点SDK证书到控制台配置目录")
    _copy_all_sdk_files(node_paths, console_paths)
    
    # 4. 重新签发控制台SDK证书（如果提供了 api_url 和 node_id）
    if api_url and node_id:
        logger.info("重新签发控制台SDK证书...")
        _reissue_console_certificates(console_paths["conf"], api_url, node_id)
    
    # 5. 部署完成后，自动执行一次合约调用：call Counter increment
    try:
        _execute_console_command_once("call Counter increment")
    except Exception as e:  # noqa: BLE001
        # 不阻塞部署流程，只记录错误
        logger.error(f"部署后自动执行命令失败: {e}")

    logger.info("控制台部署完成")

def _update_console_config_port(config_path: Path, rpc_port: int) -> None:
    """更新控制台配置文件中的RPC端口。"""
    try:
        # 读取配置文件内容
        content = config_path.read_text(encoding="utf-8")
        
        # 使用正则表达式替换端口号
        # 匹配 peers 数组中的 127.0.0.1:20200
        updated_content = re.sub(
            r'"127\.0\.0\.1:20200"', 
            f'"127.0.0.1:{rpc_port}"', 
            content
        )
        
        # 写回文件
        config_path.write_text(updated_content, encoding="utf-8")
        logger.info(f"已更新控制台配置文件中的端口为: {rpc_port}")
        
    except Exception as e:
        logger.error(f"更新控制台配置文件端口时出错: {str(e)}")
        raise RuntimeError(f"更新控制台配置文件端口时出错: {str(e)}")


def _copy_all_sdk_files(node_paths: dict[str, Path], console_paths: dict[str, Path]) -> None:
    """拷贝节点SDK目录下所有文件到控制台配置目录。"""
    try:
        # 确保目标目录存在
        console_conf_dir = console_paths["conf"]
        console_conf_dir.mkdir(parents=True, exist_ok=True)
        
        # SDK源目录
        sdk_dir = node_paths["sdk_dir"]
        if not sdk_dir.exists():
            raise RuntimeError(f"节点SDK目录不存在: {sdk_dir}")
        
        # 拷贝SDK目录下所有文件
        logger.info(f"拷贝SDK目录下所有文件: {sdk_dir} -> {console_conf_dir}")
        for item in sdk_dir.iterdir():
            if item.is_file():
                dst_path = console_conf_dir / item.name
                logger.info(f"拷贝文件: {item} -> {dst_path}")
                shutil.copy2(item, dst_path)
    except Exception as e:
        logger.error(f"拷贝SDK文件时出错: {str(e)}")
        raise RuntimeError(f"拷贝SDK文件时出错: {str(e)}")


def _reissue_console_certificates(console_conf_dir: Path, api_url: str, node_id: str) -> None:
    """为控制台重新签发SDK证书。
    
    Args:
        console_conf_dir: 控制台配置目录路径 (console/conf)。
        api_url: 证书签发服务器的API基础URL。
        node_id: 节点ID，用于证书请求。
    """
    try:
        cert_client = CertificateClient(api_base_url=api_url)
        success, message = cert_client.issue_console_sdk_certificate(
            output_conf_dir=str(console_conf_dir),
            node_id=node_id
        )
        if success:
            logger.info(f"控制台SDK证书重新签发成功: {message}")
        else:
            logger.error(f"控制台SDK证书重新签发失败: {message}")
            raise RuntimeError(f"控制台SDK证书重新签发失败: {message}")
    except Exception as e:
        logger.error(f"重新签发控制台SDK证书时发生异常: {str(e)}")
        raise RuntimeError(f"重新签发控制台SDK证书时发生异常: {str(e)}")


def _get_console_start_command() -> str:
    """构建启动 FISCO 控制台的命令（开启无缓冲 IO）。"""
    # 解析到服务根目录 (src/server)
    server_root = Path(__file__).resolve().parents[1]
    start_script = server_root / "console" / "start.sh"
    # 使用 stdbuf 确保交互式输出不被缓冲
    return f"stdbuf -i0 -o0 -e0 bash {str(start_script)}"


def _execute_console_command_once(command: str, ready_prompt: str = "[group0]: /apps> ", timeout: int = 60) -> None:
    """启动一次控制台、等待就绪提示符后发送一条命令并退出。

    该行为只在部署阶段触发一次，用于自动调用示例合约方法。
    出错时记录日志，不抛出致命异常以免影响整体部署流程。
    """
    try:
        # 延迟导入，避免在未使用该功能时引入硬依赖
        import pexpect  # type: ignore

        cmd = _get_console_start_command()
        child = pexpect.spawn(cmd, encoding="utf-8", dimensions=(100, 500))

        # 等待控制台就绪提示符（优先精确匹配；失败则退回到正则匹配，允许可选空格）
        try:
            child.expect_exact(ready_prompt, timeout=timeout)
        except Exception:
            import re as _re
            child.expect(_re.compile(r"\[group0\]: /apps> ?"), timeout=timeout)

        # 发送目标命令
        logger.info(f"即将自动执行控制台命令: {command}")
        child.sendline(command)

        # 等待命令执行完毕并回到提示符，收集输出
        try:
            child.expect_exact(ready_prompt, timeout=timeout)
        except Exception:
            import re as _re
            child.expect(_re.compile(r"\[group0\]: /apps> ?"), timeout=timeout)
        output = child.before or ""
        if output.strip():
            logger.info(f"自动命令输出:\n{output}")
        else:
            logger.info("自动命令已执行，无可记录输出或输出为空。")

        # 退出控制台
        child.sendline("quit")
        try:
            child.expect(pexpect.EOF, timeout=10)
        except Exception:
            # 如果未能正常 EOF，也尝试强制关闭
            child.close(force=True)

    except Exception as e:  # noqa: BLE001
        # 仅记录错误，不向上抛出
        logger.error(f"自动执行控制台命令时出错: {e}")
