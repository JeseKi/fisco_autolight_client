from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, WebSocket


router = APIRouter()


def _get_console_start_command() -> str:
    """Build the command to start the FISCO console with unbuffered IO."""
    # Resolve to the server root directory (src/server)
    server_root = Path(__file__).resolve().parents[1]
    start_script = server_root / "console" / "start.sh"
    # Use stdbuf to ensure unbuffered I/O for interactive experience
    # Quote path via str; subprocess/pexpect will handle spaces properly when passed as a single string to the shell
    return f"stdbuf -i0 -o0 -e0 bash {str(start_script)}"


@router.websocket("/ws/console")
async def console_websocket(websocket: WebSocket) -> None:
    """Expose a websocket that bridges to the FISCO console process.

    It streams process output to the client and forwards client input to the process.
    """
    await websocket.accept()

    # Import pexpect lazily to avoid hard import dependency at module import time
    try:
        import pexpect  # type: ignore
    except Exception as exc:  # pragma: no cover
        await websocket.send_text(f"[ERROR] pexpect is required on server: {exc}\r\n")
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

                    # Detect console ready prompt once and send a sample command
                    if not init_done and "[group0]: /apps>" in output:
                        init_done = True
                        child.send("getBlockNumber\n")
                except Exception as e:  # noqa: BLE001
                    # TIMEOUT means no output available; keep looping
                    from pexpect.exceptions import TIMEOUT, EOF  # type: ignore

                    if isinstance(e, TIMEOUT):
                        await asyncio.sleep(0.01)
                        continue
                    if isinstance(e, EOF):
                        break
                    # Unknown error: break the loop after notifying client
                    try:
                        await websocket.send_text(f"\r\n[ERROR] {e}\r\n")
                    except Exception:
                        pass
                    break

            # Ensure websocket is closed when process exits
            try:
                await websocket.close()
            except Exception:
                pass

        forward_task = asyncio.create_task(forward_output())

        # Receive input from client and forward to child process
        while True:
            data = await websocket.receive_text()
            child.send(data)

    except Exception as e:  # noqa: BLE001
        try:
            await websocket.send_text(f"\r\n[ERROR] WebSocket error: {e}\r\n")
        except Exception:
            pass
        try:
            await websocket.close()
        except Exception:
            pass
