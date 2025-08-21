import asyncio
import pexpect
import sys  # <--- [修改 1] 导入 sys 模块

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

# ---- 配置 ----
FISCO_CONSOLE_COMMAND = "stdbuf -i0 -o0 -e0 bash console/start.sh"
# ---- FastAPI 应用设置 ----
app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        child = pexpect.spawn(FISCO_CONSOLE_COMMAND, encoding='utf-8', dimensions=(100, 500))
        # child.logfile_read = sys.stdout # 保留调试日志

        # 标志位：用于判断是否已发送自动命令
        init_done = False

        # 后台任务：从子进程读取并转发
        async def forward_output():
            nonlocal init_done
            while child.isalive():
                try:
                    # --- 核心修改在这里 ---
                    # 使用 read_nonblocking，有输出就读，没输出就快速超时
                    # 这可以防止 I/O 阻塞，让 asyncio 事件循环可以去刷新网络缓冲
                    output = await asyncio.to_thread(
                        child.read_nonblocking, 
                        size=1024, 
                        timeout=0.1 # 设置一个短超时
                    )
                    await websocket.send_text(output)
                    
                    # 检查初始化是否完成，并发送自动命令
                    # 使用更具体的提示符 '[group0]: /apps>' 作为启动完成的标志
                    if not init_done and "[group0]: /apps>" in output:
                        init_done = True
                        child.send("getBlockNumber\n") # 发送获取区块高度命令， 需要加上 `\n` 来保证执行，而非单纯的换行或发送
                
                except pexpect.exceptions.TIMEOUT:
                    # 这是一个正常情况！表示子进程暂时没有输出，我们什么都不用做
                    # 让循环继续，给其他任务执行的机会
                    await asyncio.sleep(0.01) # 短暂休眠避免空转CPU
                    continue
                
                except pexpect.exceptions.EOF:
                    # 子进程已关闭
                    break
                
                except Exception as e:
                    print(f"读取转发时发生未知错误: {e}")
                    break
            
            await websocket.close()

        forward_task = asyncio.create_task(forward_output())

        # 主任务：接收前端输入
        while True:
            data = await websocket.receive_text()
            child.send(data)

    except Exception as e:
        print(f"❌ WebSocket 交互期间发生错误，通常是客户端断开: {e}")