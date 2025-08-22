from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, WebSocket


router = APIRouter()


def _get_console_start_command() -> str:
    """构建启动 FISCO 控制台的命令，并启用无缓冲 IO。"""
    start_script = Path.cwd() / "console" / "start.sh"
    # 使用 stdbuf 确保交互体验的无缓冲 I/O
    # 通过 str 引用路径；当作为单个字符串传递给 shell 时，subprocess/pexpect 会正确处理空格
    return f"stdbuf -i0 -o0 -e0 bash {str(start_script)}"


@router.websocket("/ws/console")
async def console_websocket(websocket: WebSocket) -> None:
    """暴露一个 websocket，用于桥接到 FISCO 控制台进程。

    它将进程的输出流式传输到客户端，并将客户端的输入转发到进程。
    """
    await websocket.accept()

    # 懒加载 pexpect 以避免在模块导入时产生硬性依赖
    try:
        import pexpect  # type: ignore
    except Exception as exc:  # pragma: no cover
        await websocket.send_text(f"[ERROR] 服务器需要 pexpect: {exc}\r\n")
        await websocket.close()
        return

    command = _get_console_start_command()

    try:
        child = pexpect.spawn(command, encoding="utf-8", dimensions=(100, 500))

        init_done = False

        async def forward_output() -> None:
            nonlocal init_done
            while child.isalive():
                try:
                    output: str = await asyncio.to_thread(
                        child.read_nonblocking, size=1024, timeout=0.1
                    )
                    if output:
                        await websocket.send_text(output)

                    # 一旦检测到控制台就绪提示符，发送一个示例命令
                    if not init_done and "[group0]: /apps>" in output:
                        init_done = True
                        child.send("getBlockNumber\n")
                except Exception as e:  # noqa: BLE001
                    # TIMEOUT 意味着没有可用的输出；继续循环
                    from pexpect.exceptions import TIMEOUT, EOF  # type: ignore

                    if isinstance(e, TIMEOUT):
                        await asyncio.sleep(0.01)
                        continue
                    if isinstance(e, EOF):
                        break
                    # 未知错误：通知客户端后跳出循环
                    try:
                        await websocket.send_text(f"\r\n[ERROR] {e}\r\n")
                    except Exception:
                        pass
                    break

            # 确保在进程退出时关闭 websocket
            try:
                await websocket.close()
            except Exception:
                pass

        _ = asyncio.create_task(forward_output())

        # 接收来自客户端的输入并转发到子进程
        while True:
            data = await websocket.receive_text()
            child.send(data)

    except Exception as e:  # noqa: BLE001
        try:
            await websocket.send_text(f"\r\n[ERROR] WebSocket 错误: {e}\r\n")
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
