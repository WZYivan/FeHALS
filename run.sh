#!/usr/bin/env bash

PROJ="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PID_FILE="/tmp/fehals-backend.pid"
FRONTEND_PID_FILE="/tmp/fehals-frontend.pid"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

start_backend() {
  rm -f "$BACKEND_PID_FILE"
  # 检查端口占用（跳过 ss 表头）
  if ss -tlnp "sport = :$BACKEND_PORT" 2>/dev/null | grep -q "LISTEN.*python"; then
    echo "端口 $BACKEND_PORT 已被占用，执行 ./run.sh stop 后重试"
    return 1
  fi
  cd "$PROJ/backend"
  echo "启动后端 (端口 $BACKEND_PORT)..."
  nohup conda run -n FeHALS python run.py > /tmp/fehals-backend.log 2>&1 &
  echo $! > "$BACKEND_PID_FILE"
  sleep 3
  if kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
    echo "后端已启动 (PID $(cat "$BACKEND_PID_FILE"))"
  else
    echo "后端启动失败，查看日志: cat /tmp/fehals-backend.log"
    return 1
  fi
}

start_frontend() {
  rm -f "$FRONTEND_PID_FILE"
  cd "$PROJ/frontend"
  echo "启动前端 (端口 $FRONTEND_PORT)..."
  nohup npx vite --port "$FRONTEND_PORT" > /tmp/fehals-frontend.log 2>&1 &
  echo $! > "$FRONTEND_PID_FILE"
  sleep 3
  if kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
    echo "前端已启动 (PID $(cat "$FRONTEND_PID_FILE"))"
  else
    echo "前端启动失败，查看日志: cat /tmp/fehals-frontend.log"
  fi
}

stop_backend() {
  local pid=""
  if [ -f "$BACKEND_PID_FILE" ]; then
    pid=$(cat "$BACKEND_PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
      echo "停止后端 (PID $pid)..."
      kill "$pid" 2>/dev/null
    fi
    rm -f "$BACKEND_PID_FILE"
  fi
  # 补杀 python run.py（可能由 conda run 派生）
  local bp
  bp=$(pgrep -f "python run\.py" 2>/dev/null || true)
  if [ -n "$bp" ]; then
    for p in $bp; do
      kill "$p" 2>/dev/null || true
    done
  fi
  echo "后端已停止"
}

stop_frontend() {
  local pid=""
  if [ -f "$FRONTEND_PID_FILE" ]; then
    pid=$(cat "$FRONTEND_PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
      echo "停止前端 (PID $pid)..."
      kill "$pid" 2>/dev/null
    fi
    rm -f "$FRONTEND_PID_FILE"
  fi
  # 补杀 vite（可能由 npx 派生）
  local vt_pid
  vt_pid=$(pgrep -f "vite.*--port $FRONTEND_PORT" 2>/dev/null || true)
  if [ -n "$vt_pid" ]; then
    kill "$vt_pid" 2>/dev/null || true
  fi
  echo "前端已停止"
}

status() {
  echo "--- 状态 ---"
  local bp
  bp=$(pgrep -f "python run\.py" 2>/dev/null | head -1 || true)
  local fp
  fp=$(pgrep -f "vite" 2>/dev/null | grep -v "grep" | head -1 || true)
  if [ -n "$bp" ]; then
    echo "后端: 运行中 (PID $bp) → http://localhost:$BACKEND_PORT"
  else
    echo "后端: 未运行"
  fi
  if [ -n "$fp" ]; then
    echo "前端: 运行中 (PID $fp) → http://localhost:$FRONTEND_PORT"
  else
    echo "前端: 未运行"
  fi
}

case "${1:-start}" in
  start)
    start_backend
    start_frontend
    echo "---"
    echo "后端: http://localhost:$BACKEND_PORT (接口文档 /docs)"
    echo "前端: http://localhost:$FRONTEND_PORT"
    echo "运行 ./run.sh stop 停止服务"
    ;;
  stop)
    stop_frontend
    stop_backend
    # 等待确认无残留
    sleep 2
    leftover=$(pgrep -f "python run\.py|vite" 2>/dev/null | grep -v "grep" || true)
    if [ -z "$leftover" ]; then
      echo "所有服务已停止"
    else
      echo "警告: 仍有残留进程，尝试强制终止..."
      pkill -9 -f "vite.*--port $FRONTEND_PORT" 2>/dev/null || true
      pkill -9 -f "uvicorn app.main" 2>/dev/null || true
      echo "已强制清理"
    fi
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
    ;;
  restart)
    "$0" stop
    sleep 1
    "$0" start
    ;;
  status)
    status
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac