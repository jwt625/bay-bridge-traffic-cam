#!/bin/bash

echo "=== Starting Bay Bridge Traffic Services ==="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Check if containers exist (running or stopped)
GRAFANA_RUNNING=$(docker ps -q -f name=grafana)
PROMETHEUS_RUNNING=$(docker ps -q -f name=prometheus)
GRAFANA_EXISTS=$(docker ps -aq -f name=grafana)
PROMETHEUS_EXISTS=$(docker ps -aq -f name=prometheus)

if [ -n "$GRAFANA_RUNNING" ] && [ -n "$PROMETHEUS_RUNNING" ]; then
    echo "✅ Docker services are already running"
elif [ -n "$GRAFANA_EXISTS" ] || [ -n "$PROMETHEUS_EXISTS" ]; then
    echo "🔄 Containers exist but are stopped. Starting existing containers..."
    docker start grafana prometheus 2>/dev/null || true
    echo "✅ Docker services started"
else
    echo "🚀 Creating and starting Prometheus and Grafana..."
    docker-compose up -d
    if [ $? -ne 0 ]; then
        echo "❌ Failed to start Docker services"
        exit 1
    fi
    echo "✅ Docker services started"
fi

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if Grafana is responding
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "302"; then
    echo "✅ Grafana is ready at http://localhost:3000"
else
    echo "⚠️  Grafana might still be starting up..."
fi

# Check if Prometheus is responding
if curl -s -o /dev/null -w "%{http_code}" http://localhost:9090 | grep -q "200"; then
    echo "✅ Prometheus is ready at http://localhost:9090"
else
    echo "⚠️  Prometheus might still be starting up..."
fi

# Start Nginx if not already running
if ! pgrep nginx > /dev/null; then
    echo "🚀 Starting Nginx reverse proxy..."
    nginx
    if [ $? -eq 0 ]; then
        echo "✅ Nginx started on port 8080"
    else
        echo "❌ Failed to start Nginx"
        exit 1
    fi
else
    echo "✅ Nginx is already running"
fi

# Check if reverse proxy is working
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 | grep -q "302"; then
    echo "✅ Reverse proxy is working at http://localhost:8080"
else
    echo "❌ Reverse proxy is not responding correctly"
fi

echo ""
echo "=== All Services Started! ==="
echo ""
echo "Services running:"
echo "  📊 Grafana: http://localhost:3000 (admin/admin)"
echo "  📈 Prometheus: http://localhost:9090"
echo "  🔄 Nginx Proxy: http://localhost:8080"
echo "  📡 Metrics Server: http://localhost:9091"
echo ""
echo "Next steps:"
echo "  1. Run './setup-cloudflare-tunnel.sh' to set up the tunnel"
echo "  2. Start the tunnel with: cloudflared tunnel run grafana-local"
echo "  3. Access your dashboard at: https://bay-bridge-traffic.com"
