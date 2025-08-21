import { useEffect, useRef } from 'react';
import { Card } from 'antd';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

interface ConsoleTerminalProps {
  apiBaseUrl: string; // e.g., http://localhost:1234
  height?: number; // px
}

export default function ConsoleTerminal({ apiBaseUrl, height = 360 }: ConsoleTerminalProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitRef = useRef<FitAddon | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      theme: { background: '#1e1e1e', foreground: '#d4d4d4' },
      fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
      fontSize: 12,
      convertEol: true,
    });
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();
    term.focus();

    // Connect websocket to backend
    const wsProtocol = apiBaseUrl.startsWith('https') ? 'wss' : 'ws';
    const wsUrl = apiBaseUrl.replace(/^https?/, wsProtocol) + '/ws/console';
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      term.writeln('\u001b[32m[Connected to backend]\u001b[0m');
    };
    ws.onmessage = (event) => {
      term.write(String(event.data));
    };
    ws.onerror = () => {
      term.writeln('\u001b[31m[WebSocket error]\u001b[0m');
    };
    ws.onclose = () => {
      term.writeln('\r\n\u001b[31m[Disconnected]\u001b[0m');
    };

    const dataDisposable = term.onData((data) => {
      ws.send(data);
    });

    const onResize = () => fitAddon.fit();
    window.addEventListener('resize', onResize);

    wsRef.current = ws;
    termRef.current = term;
    fitRef.current = fitAddon;

    return () => {
      dataDisposable.dispose();
      window.removeEventListener('resize', onResize);
      try { ws.close(); } catch {}
      try { term.dispose(); } catch {}
    };
  }, [apiBaseUrl]);

  return (
    <Card title="交互控制台" bodyStyle={{ padding: 8, width: '100%'}}>
      <div
        ref={containerRef}
        style={{ height, minHeight: height, width: '100%', background: '#1e1e1e', border: '1px solid #555', borderRadius: 4 }}
      />
    </Card>
  );
}
