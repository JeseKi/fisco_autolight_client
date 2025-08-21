# FISCO BCOS 轻节点管理工具

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/FISCO-BCOS/lightnode-manager/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-19-blue.svg)](https://reactjs.org/)

FISCO BCOS 轻节点管理工具是一个基于 Web 的图形化界面工具，用于简化 FISCO BCOS 轻节点的部署、启动和管理流程。通过该工具，用户可以轻松地一键部署轻节点，而无需深入了解复杂的命令行操作。

## 功能特性

- ✅ **一键部署**：自动化完成证书申请、脚本下载、节点构建和配置覆盖等全流程
- ✅ **可视化管理**：通过直观的 Web UI 管理轻节点的启动和停止
- ✅ **实时日志**：通过 Server-Sent Events (SSE) 实时查看部署和运行日志
- ✅ **状态监控**：实时监控节点运行状态
- ✅ **控制台集成**：自动部署和配置 FISCO BCOS 控制台

## 技术栈

### 前端
- [React 19](https://reactjs.org/) - 前端框架
- [TypeScript](https://www.typescriptlang.org/) - 类型安全的 JavaScript
- [Vite](https://vitejs.dev/) - 构建工具
- [Ant Design](https://ant.design/) - UI 组件库
- [Tailwind CSS](https://tailwindcss.com/) - CSS 框架
- [Axios](https://axios-http.com/) - HTTP 客户端

### 后端
- [Python 3.8+](https://www.python.org/) - 后端语言
- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的 Web 框架
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证和设置管理
- [Uvicorn](https://www.uvicorn.org/) - ASGI 服务器

## 快速开始

### 环境要求

- Python 3.8 或更高版本
- Node.js 16 或更高版本
- pnpm (推荐) 或 npm

### 安装

1. 克隆项目代码：

```bash
git clone <repository-url>
cd fisco_autocrt
```

2. 安装后端依赖：

```bash
# 推荐使用 conda 创建虚拟环境
conda create -n fisco-manager python=3.8
conda activate fisco-manager

# 安装 Python 依赖
pip install -r requirements.txt
```

3. 安装前端依赖：

```bash
# 使用 pnpm 安装依赖
pnpm install
```

### 运行

1. 构建前端资源：

```bash
pnpm build
```

2. 启动后端服务：

```bash
cd src/server
python main.py
```

服务将启动在 `http://localhost:1234`，浏览器会自动打开。

## 项目结构

```
fisco_autocrt/
├── src/
│   ├── client/              # 前端代码
│   │   ├── App.tsx          # 主应用组件
│   │   ├── main.tsx         # 应用入口
│   │   └── ...
│   └── server/              # 后端代码
│       ├── main.py          # 后端主入口
│       ├── config.py        # 配置文件
│       ├── workers/         # 核心工作模块
│       │   ├── deploy_coordinator.py  # 部署协调器
│       │   ├── lightnode_builder.py   # 轻节点构建器
│       │   └── schemas.py             # 数据模型
│       ├── service/         # 服务模块
│       ├── asset_client/    # 资源客户端
│       └── cert_client/     # 证书客户端
├── dist/                    # 前端构建产物
├── requirements.txt         # Python 依赖
├── package.json             # Node.js 依赖
└── README.md
```

## API 接口文档

后端服务提供以下 RESTful API 接口：

### 部署相关

- `POST /api/deploy` - 一键部署新节点
- `POST /api/start` - 启动节点
- `POST /api/stop` - 停止节点
- `GET /api/status` - 获取节点状态
- `GET /api/logs/stream` - 实时日志流 (SSE)
- `GET /api/session` - 获取当前会话信息

### 数据模型

```python
class NodeStatus(BaseModel):
    block_height: int
    node_id: str
    p2p_connection_count: int
    running: bool
```

## 开发指南

### 前端开发

```bash
# 启动开发服务器
pnpm dev
```

### 后端开发

```bash
# 在开发模式下启动后端服务
cd src/server
python main.py
```

### 代码规范

- Python 代码遵循 PEP 8 规范
- TypeScript 代码使用 ESLint 进行检查
- 提交代码前请确保通过所有测试

## 测试

后端测试使用 pytest 框架，测试文件位于 `src/server/tests/` 和 `src/server/workers/tests/` 目录中。

运行测试：

```bash
# 运行所有测试
cd src/server
python -m pytest

# 运行特定模块测试
python -m pytest tests/test_main_api.py
```

## 部署流程详解

一键部署流程包含以下 8 个步骤：

1. 申请并下载证书到 `{output_dir}/conf`
2. 下载 `build_chain.sh` 构建脚本
3. 下载 `fisco-bcos` 和 `fisco-bcos-lightnode` 二进制文件
4. 使用脚本构建轻节点
5. 提升 `nodes/lightnode` -> `lightnode` 并清理 `nodes` 目录
6. 覆盖轻节点证书
7. 下载并覆盖 `config.genesis` 和 `nodes.json`
8. 部署控制台

## 许可证

本项目采用 Apache 2.0 许可证，详见 [LICENSE](LICENSE) 文件。
