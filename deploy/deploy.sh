#!/bin/sh
set -eu

# ── 設定 ──
REMOTE="my_server"
REMOTE_DIR="/home/lzrong/tw-futures-lab"
COMPOSE_FILE="docker-compose.prod.yml"

echo "=== 1. 同步專案到遠端伺服器 ==="
rsync -avz --delete \
  --exclude '.venv' \
  --exclude 'node_modules' \
  --exclude '.next' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'src/data/cache' \
  --exclude 'backtest_results.db' \
  --exclude '.git' \
  -e "ssh" \
  "$(dirname "$0")/../" \
  "${REMOTE}:${REMOTE_DIR}/"

echo "=== 2. 在遠端建置並啟動容器 ==="
ssh "${REMOTE}" "cd ${REMOTE_DIR} && docker-compose -f ${COMPOSE_FILE} build && docker-compose -f ${COMPOSE_FILE} up -d"

echo "=== 3. 等待 health check ==="
sleep 5
ssh "${REMOTE}" "curl -sf http://127.0.0.1:8200/health && echo ' API OK' || echo ' API FAIL'"
ssh "${REMOTE}" "curl -sf http://127.0.0.1:3200/ > /dev/null && echo 'Frontend OK' || echo 'Frontend FAIL'"

echo ""
echo "=== 部署完成 ==="
echo "請確認 nginx 已加入 location 設定（見 deploy/nginx-futures-lab.conf）"
echo "https://plusform.mathison.com.tw/"
