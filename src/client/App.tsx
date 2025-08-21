import { useState, useEffect, useRef } from 'react';
import { Input, Button, Card, Typography, Space, message, Spin } from 'antd';
import axios from 'axios';
import ConsoleTerminal from './ConsoleTerminal';

const { Title, Text } = Typography;
const { TextArea } = Input;

const API_URL = 'http://localhost:1234';

// 节点状态的数据结构
interface NodeStatus {
  block_height: number;
  node_id: string;
  p2p_connection_count: number;
  running: boolean;
}

function App() {
  const [nodeDir, setNodeDir] = useState('');
  const [logs, setLogs] = useState<string[]>([]);
  const [status, setStatus] = useState<NodeStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isNodeRunning, setIsNodeRunning] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  const logContainerRef = useRef<any>(null);

  // 自动滚动日志
  useEffect(() => {
    if (logContainerRef.current) {
      // 对于 antd TextArea，我们需要访问实际的 textarea 元素
      const textarea = logContainerRef.current.resizableTextArea?.textArea || logContainerRef.current.textArea || logContainerRef.current;
      if (textarea && textarea instanceof HTMLTextAreaElement) {
        textarea.scrollTop = textarea.scrollHeight;
      }
    }
  }, [logs]);

  // SSE 连接和状态轮询
  useEffect(() => {
    // 初始化 SSE 连接
    const connectSSE = () => {
      const es = new EventSource(`${API_URL}/api/logs/stream`);
      es.onopen = () => {
        addLog('[SSE] SSE 连接成功');
      };
      es.onmessage = (event) => {
        addLog(event.data);
      };
      es.onerror = () => {
        // EventSource 会自动重连，这里可以记录错误或关闭
        addLog('[SSE] SSE 连接发生错误，将自动重连。');
        es.close(); // 关闭旧的，允许自动重连创建新的
        setTimeout(connectSSE, 3000); // 手动辅助重连
      };
      eventSourceRef.current = es;
    };

    connectSSE();

    // 设置状态轮询
    const statusInterval = setInterval(fetchStatus, 3000);

    // 组件卸载时清理
    return () => {
      clearInterval(statusInterval);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // 获取初始会话
  useEffect(() => {
    const fetchSession = async () => {
      try {
        const response = await axios.get(`${API_URL}/api/session`);
        if (response.data.current_node_dir) {
          setNodeDir(response.data.current_node_dir);
          addLog(`[INFO] 恢复上次节点目录: ${response.data.current_node_dir}`);
        }
      } catch (error) {
        message.error('获取会话信息失败');
      }
    };
    fetchSession();
  }, []);

  const addLog = (log: string) => {
    setLogs(prevLogs => [...prevLogs, log]);
  };

  const fetchStatus = async () => {
    try {
      const response = await axios.get<NodeStatus>(`${API_URL}/api/status`);
      setStatus(response.data);
      setIsNodeRunning(response.data.running);
    } catch (error) {
      setStatus(null);
      setIsNodeRunning(false);
    }
  };

  const handleDeploy = async () => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/api/deploy`);
      if (response.data.success) {
        message.success(response.data.message);
      } else {
        message.error(response.data.message);
      }
    } catch (error: any) {
      message.error(`部署请求失败: ${error.response?.data?.message || error.message}`);
    }
    setIsLoading(false);
  };

  const handleStart = async () => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/api/start`);
      if (response.data.success) {
        message.success(response.data.message);
      } else {
        message.error(response.data.message);
      }
    } catch (error: any) {
      message.error(`启动请求失败: ${error.response?.data?.message || error.message}`);
    }
    setIsLoading(false);
    setTimeout(fetchStatus, 1000);
  };

  const handleStop = async () => {
    setIsLoading(true);
    try {
      const response = await axios.post(`${API_URL}/api/stop`);
      if (response.data.success) {
        message.success(response.data.message);
      } else {
        message.error(response.data.message);
      }
    } catch (error: any) {
      message.error(`停止请求失败: ${error.response?.data?.message || error.message}`);
    }
    setIsLoading(false);
    setTimeout(fetchStatus, 1000);
  };

  return (
    <div className="min-h-screen bg-gray-100 flex justify-center items-center p-4">
      <Spin spinning={isLoading} tip="操作执行中...">
        <div className="w-[90vw] max-w-4xl mx-auto">
          <Title level={2} className="text-center mb-6">FISCO BCOS 轻节点管理工具</Title>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Left Column: Controls and Status */}
            <div className="flex flex-col gap-6">
              <Card title="核心操作">
                <Space direction="vertical" className="w-full">
                  <div>
                    <Text type="secondary">节点将部署在固定目录:</Text>
                    <Text code>{nodeDir || '加载中...'}</Text>
                  </div>
                  <div className="flex justify-between flex-wrap gap-2 pt-2">
                    <Button type="primary" onClick={handleDeploy} disabled={isNodeRunning}>
                      一键部署
                    </Button>
                    <Button type="primary" ghost onClick={handleStart} disabled={isNodeRunning}>
                      启动节点
                    </Button>
                    <Button danger onClick={handleStop} disabled={!isNodeRunning}>
                      停止节点
                    </Button>
                  </div>
                </Space>
              </Card>
              <Card title="节点状态 (Mock)">
                <Space direction="vertical" className="w-full">
                  <div className="flex justify-between"><Text strong>连接状态:</Text> <Text>{status ? (isNodeRunning ? '🟢 运行中' : '🔴 已断开') : '⚪ 未知'}</Text></div>
                  {/*<div className="flex justify-between"><Text strong>当前区块高度:</Text> <Text>{status?.block_height ?? 'N/A'}</Text></div>*/}
                  <div className="flex justify-between"><Text strong>本节点ID:</Text> <Text className="break-all">{status?.node_id ?? 'N/A'}</Text></div>
                  {/*<div className="flex justify-between"><Text strong>P2P连接数:</Text> <Text>{status?.p2p_connection_count ?? 'N/A'}</Text></div>*/}
                </Space>
              </Card>
            </div>

            {/* Right Column: Logs + Console */}
            <Card title="日志输出" className="md:col-span-1">
              <TextArea
                ref={logContainerRef}
                readOnly
                value={logs.join('\n')}
                className="h-96 font-mono text-xs"
                placeholder="日志输出..."
                style={{ minHeight : 300}}
              />
            </Card>
            <div className="md:col-span-2">
              <ConsoleTerminal apiBaseUrl={API_URL} height={360}/>
            </div>
          </div>
        </div>
      </Spin>
    </div>
  );
}

export default App;
