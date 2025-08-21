# -*- coding: utf-8 -*-
"""
后端 API 服务器

文件功能:
    - 提供基于 FastAPI 的后端服务，用于取代原有的 PyQt UI。
    - 通过 RESTful API 和 SSE 与前端交互。

公开接口:
    - POST /api/deploy: 接收部署请求，异步执行部署流程。
    - POST /api/start: 启动节点。
    - POST /api/stop: 停止节点。
    - GET /api/status: 获取当前节点状态 (Mock)。
    - GET /api/logs/stream: 通过 SSE 实时推送日志。
"""

import asyncio
import json
import os
import re
import subprocess
import uuid
from typing import Dict, Optional
from pathlib import Path

from fastapi import FastAPI, BackgroundTasks, Request
from starlette.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 导入现有的业务逻辑模块
from workers.deploy_coordinator import DeployCoordinator
from workers.schemas import NodeStatus
from config import API_BASE_URL
from service.paths import get_node_dir

# --- 应用和状态管理 ---

app = FastAPI(
    title="FISCO BCOS 轻节点管理后端",
    description="提供节点部署、管理和状态查询的 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义固定的节点目录
NODE_DIR = str(get_node_dir())

class AppState:
    """管理应用程序的全局状态"""
    def __init__(self):
        self.current_node_dir: str = NODE_DIR # 使用固定目录
        self.deployed_node_id: Optional[str] = None
        self.node_pid: Optional[int] = None
        self.log_queue: asyncio.Queue = asyncio.Queue()
        self.load_last_session()

    def _state_path(self) -> str:
        return str(Path.cwd() / "last_session.json")

    def load_last_session(self):
        try:
            path = self._state_path()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.deployed_node_id = data.get("deployed_node_id")
            self.node_pid = data.get("node_pid")
        except Exception as e:
            print(f"[WARN] 读取会话信息失败: {e}")

    def save_session(self):
        try:
            with open(Path.cwd() / "node" / "lightnode" / "conf" / "node.nodeid", "r") as f:
                node_id = f.readline()
            state = {
                "current_node_dir": self.current_node_dir,
                "deployed_node_id": node_id,
                "node_pid": self.node_pid,
            }
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] 保存会话信息失败: {e}")

    async def push_log(self, message: str):
        await self.log_queue.put(message)

    def push_log_sync(self, message: str):
        self.log_queue.put_nowait(message)

def is_pid_alive(pid: Optional[int]) -> bool:
    """检查给定的 PID 是否对应一个正在运行的进程"""
    if pid is None:
        return False
    try:
        # 0 signal does not kill the process but will check if it exists
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

state = AppState()

# --- Pydantic 模型 ---

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict] = None

# --- SSE 日志流 ---

async def log_generator(request: Request):
    while True:
        if await request.is_disconnected():
            break
        log_message = await state.log_queue.get()
        yield f"data: {log_message}\n\n"
        await asyncio.sleep(0.01)

@app.get("/api/logs/stream")
def stream_logs(request: Request):
    return StreamingResponse(log_generator(request), media_type="text/event-stream")

# --- API Endpoints ---

def run_deployment_task():
    state.push_log_sync("[DEPLOY] 后台部署任务已启动...")
    node_id = uuid.uuid4().hex
    output_dir = state.current_node_dir
    
    def progress_callback(message: str):
        state.push_log_sync(f"[DEPLOY] {message}")

    try:
        state.deployed_node_id = node_id
        progress_callback(f"开始部署节点, ID: {node_id}")
        coordinator = DeployCoordinator(progress_callback=progress_callback)
        success, message = coordinator.execute_deployment(
            api_url=API_BASE_URL,
            output_dir=output_dir,
            node_id=node_id
        )
        final_message = f"[RESULT] {message}"
        if success:
            state.save_session()
            final_message = f"[SUCCESS] {message}"
        progress_callback(final_message)
    except Exception as e:
        progress_callback(f"[ERROR] 部署过程中发生意外错误: {e}")

@app.post("/api/deploy", response_model=ApiResponse, summary="一键部署新节点")
async def deploy_node(background_tasks: BackgroundTasks):
    output_dir = state.current_node_dir
    await state.push_log(f"[INFO] 收到部署请求，目标目录: {output_dir}")
    if os.path.exists(output_dir) and os.listdir(output_dir):
        return ApiResponse(success=False, message="部署失败：目标目录不为空。")
    background_tasks.add_task(run_deployment_task)
    return ApiResponse(success=True, message="部署任务已开始，请关注日志输出。")

@app.post("/api/start", response_model=ApiResponse, summary="启动节点")
async def start_node(background_tasks: BackgroundTasks):
    node_dir = state.current_node_dir
    await state.push_log(f"[INFO] 收到启动请求，节点目录: {node_dir}")
    
    # 使用 PID 检查节点是否已在运行
    if is_pid_alive(state.node_pid):
        return ApiResponse(success=False, message="节点已在运行中。")
        
    lightnode_dir = os.path.join(node_dir, "lightnode")
    start_script = os.path.join(lightnode_dir, "start.sh")
    if not os.path.exists(start_script):
        return ApiResponse(success=False, message=f"启动脚本不存在: {start_script}")
    try:
        # 执行脚本并等待其完成，捕获输出
        result = subprocess.run(
            ["bash", "start.sh"], cwd=lightnode_dir, capture_output=True, text=True, timeout=30
        )
        
        # 记录脚本的标准输出和标准错误
        if result.stdout:
            await state.push_log(f"[START_SCRIPT_STDOUT] {result.stdout}")
        if result.stderr:
            await state.push_log(f"[START_SCRIPT_STDERR] {result.stderr}")
            
        if result.returncode != 0:
            await state.push_log(f"[ERROR] 启动脚本执行失败，退出码: {result.returncode}")
            return ApiResponse(success=False, message=f"启动脚本执行失败，退出码: {result.returncode}")

        # 从标准输出中解析 PID
        output = result.stdout
        # Updated regex to match "pid=12345" or "pid is 12345"
        pid_match = re.search(r"pid[=\s]+(\d+)", output)
        if not pid_match:
            await state.push_log("[ERROR] 无法从启动脚本输出中解析出 PID。")
            return ApiResponse(success=False, message="无法从启动脚本输出中解析出 PID。")

        pid = int(pid_match.group(1))
        state.node_pid = pid
        await state.push_log(f"[SUCCESS] 节点启动脚本已执行，解析到 PID: {pid}。")
        state.save_session()
        return ApiResponse(success=True, message="节点启动中...")
    except subprocess.TimeoutExpired:
        await state.push_log("[ERROR] 启动脚本执行超时。")
        return ApiResponse(success=False, message="启动脚本执行超时。")
    except Exception as e:
        await state.push_log(f"[ERROR] 启动节点失败: {e}")
        return ApiResponse(success=False, message=f"启动节点失败: {e}")

@app.post("/api/stop", response_model=ApiResponse, summary="停止节点")
async def stop_node():
    node_dir = state.current_node_dir
    await state.push_log(f"[INFO] 收到停止请求，节点目录: {node_dir}")
    
    # 检查 PID 是否存在
    if not is_pid_alive(state.node_pid):
        state.node_pid = None
        state.save_session()
        return ApiResponse(success=False, message="节点未在运行。")

    lightnode_dir = os.path.join(node_dir, "lightnode")
    stop_script = os.path.join(lightnode_dir, "stop.sh")
    if not os.path.exists(stop_script):
        return ApiResponse(success=False, message=f"停止脚本不存在: {stop_script}")
    try:
        # 执行停止脚本
        result = subprocess.run(["bash", "stop.sh"], cwd=lightnode_dir, capture_output=True, text=True, timeout=10)
        
        # 记录脚本的标准输出和标准错误
        if result.stdout:
            await state.push_log(f"[STOP_SCRIPT_STDOUT] {result.stdout}")
        if result.stderr:
            await state.push_log(f"[STOP_SCRIPT_STDERR] {result.stderr}")
            
        # 清理 PID
        state.node_pid = None
        state.save_session()
        
        if result.returncode != 0:
            await state.push_log(f"[WARN] 停止脚本执行返回非零退出码: {result.returncode}")
            # 即使脚本返回错误，我们也认为节点已停止（因为它可能已经停止了）
            
        await state.push_log("[INFO] 节点已停止。")
        return ApiResponse(success=True, message="节点已停止。")
    except subprocess.TimeoutExpired:
        await state.push_log("[ERROR] 停止脚本执行超时。")
        return ApiResponse(success=False, message="停止脚本执行超时。")
    except Exception as e:
        await state.push_log(f"[ERROR] 停止节点时发生错误: {e}")
        return ApiResponse(success=False, message=f"停止节点时发生错误: {e}")

@app.get("/api/status", response_model=NodeStatus, summary="获取节点状态(Mock)")
def get_status():
    # 使用 PID 检查节点是否在运行
    is_running = is_pid_alive(state.node_pid)
    if is_running:
        return NodeStatus(block_height=-1, node_id=state.deployed_node_id or "请先启动/部署节点", p2p_connection_count=0, running=True)
    else:
        # 如果 PID 无效，则清理它
        if state.node_pid is not None:
            state.node_pid = None
            state.save_session()
        return NodeStatus(block_height=-1, node_id=state.deployed_node_id or "请先启动/部署节点", p2p_connection_count=0, running=False)

@app.get("/api/session", summary="获取当前会话信息")
def get_session():
    return {
        "current_node_dir": state.current_node_dir,
        "deployed_node_id": state.deployed_node_id,
    }

# 挂载前端静态文件
frontend_dist_dir = Path.cwd() / "dist"
if frontend_dist_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist_dir), html=True), name="frontend")
else:
    print(f"[WARN] 前端静态文件目录不存在: {frontend_dist_dir}")

if __name__ == "__main__":
    import uvicorn
    import webbrowser
    import threading
    import time

    def open_browser():
        # 等待服务启动（简单等待几秒）
        time.sleep(2)
        webbrowser.open("http://localhost:1234")

    # 启动一个线程用于打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="localhost", port=1234, reload=False)
