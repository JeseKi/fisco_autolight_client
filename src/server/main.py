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
import subprocess
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, BackgroundTasks, Request
from starlette.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入现有的业务逻辑模块
from src.server.workers.deploy_coordinator import DeployCoordinator
from src.server.workers.schemas import NodeStatus
from src.server.config import API_BASE_URL

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
NODE_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "node")

class AppState:
    """管理应用程序的全局状态"""
    def __init__(self):
        self.current_node_dir: str = NODE_DIR # 使用固定目录
        self.deployed_node_id: Optional[str] = None
        self.node_process: Optional[subprocess.Popen] = None
        self.log_queue: asyncio.Queue = asyncio.Queue()
        self.load_last_session()

    def _state_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "last_session.json")

    def load_last_session(self):
        try:
            path = self._state_path()
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.deployed_node_id = data.get("deployed_node_id")
        except Exception as e:
            print(f"[WARN] 读取会话信息失败: {e}")

    def save_session(self):
        try:
            state = {
                "current_node_dir": self.current_node_dir,
                "deployed_node_id": self.deployed_node_id,
            }
            with open(self._state_path(), "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] 保存会话信息失败: {e}")

    async def push_log(self, message: str):
        await self.log_queue.put(message)

    def push_log_sync(self, message: str):
        self.log_queue.put_nowait(message)

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

@app.get("/", summary="根路径")
def read_root():
    return {"message": "FISCO BCOS 轻节点管理后端已启动"}

@app.post("/api/deploy", response_model=ApiResponse, summary="一键部署新节点")
async def deploy_node(background_tasks: BackgroundTasks):
    output_dir = state.current_node_dir
    await state.push_log(f"[INFO] 收到部署请求，目标目录: {output_dir}")
    if os.path.exists(output_dir) and os.listdir(output_dir):
        return ApiResponse(success=False, message="部署失败：目标目录不为空。")
    background_tasks.add_task(run_deployment_task)
    return ApiResponse(success=True, message="部署任务已开始，请关注日志输出。")

async def stream_process_logs(process: subprocess.Popen):
    while process.poll() is None:
        if process.stdout:
            line = await asyncio.to_thread(process.stdout.readline)
            if line:
                await state.push_log(f"[NODE] {line.decode('utf-8', errors='ignore').strip()}")
        await asyncio.sleep(0.1)
    state.node_process = None
    await state.push_log("[INFO] 节点进程已停止。")

@app.post("/api/start", response_model=ApiResponse, summary="启动节点")
async def start_node(background_tasks: BackgroundTasks):
    node_dir = state.current_node_dir
    await state.push_log(f"[INFO] 收到启动请求，节点目录: {node_dir}")
    if state.node_process and state.node_process.poll() is None:
        return ApiResponse(success=False, message="节点已在运行中。")
    lightnode_dir = os.path.join(node_dir, "lightnode")
    start_script = os.path.join(lightnode_dir, "start.sh")
    if not os.path.exists(start_script):
        return ApiResponse(success=False, message=f"启动脚本不存在: {start_script}")
    try:
        process = subprocess.Popen(
            ["bash", "start.sh"], cwd=lightnode_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=False
        )
        state.node_process = process
        await state.push_log("[SUCCESS] 节点启动脚本已执行。开始监听日志...")
        background_tasks.add_task(stream_process_logs, process)
        state.save_session()
        return ApiResponse(success=True, message="节点启动中...")
    except Exception as e:
        await state.push_log(f"[ERROR] 启动节点失败: {e}")
        return ApiResponse(success=False, message=f"启动节点失败: {e}")

@app.post("/api/stop", response_model=ApiResponse, summary="停止节点")
async def stop_node():
    node_dir = state.current_node_dir
    await state.push_log(f"[INFO] 收到停止请求，节点目录: {node_dir}")
    lightnode_dir = os.path.join(node_dir, "lightnode")
    stop_script = os.path.join(lightnode_dir, "stop.sh")
    if not os.path.exists(stop_script):
        return ApiResponse(success=False, message=f"停止脚本不存在: {stop_script}")
    try:
        subprocess.run(["bash", "stop.sh"], cwd=lightnode_dir, capture_output=True, text=True, timeout=10)
        if state.node_process and state.node_process.poll() is None:
            state.node_process.terminate()
            state.node_process.wait(timeout=5)
        state.node_process = None
        state.save_session()
        await state.push_log("[INFO] 节点已停止。")
        return ApiResponse(success=True, message="节点已停止。")
    except Exception as e:
        await state.push_log(f"[ERROR] 停止节点时发生错误: {e}")
        return ApiResponse(success=False, message=f"停止节点时发生错误: {e}")

@app.get("/api/status", response_model=NodeStatus, summary="获取节点状态(Mock)")
def get_status():
    is_running = state.node_process is not None and state.node_process.poll() is None
    if is_running:
        return NodeStatus(block_height=12345, node_id=state.deployed_node_id or "mock_node_id_running_xxxx", p2p_connection_count=5)
    else:
        return NodeStatus(block_height=-1, node_id=state.deployed_node_id or "mock_node_id_stopped_yyyy", p2p_connection_count=0)

@app.get("/api/session", summary="获取当前会话信息")
def get_session():
    return {
        "current_node_dir": state.current_node_dir,
        "deployed_node_id": state.deployed_node_id,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=1234, reload=True)
