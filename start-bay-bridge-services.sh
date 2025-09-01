#!/bin/bash

# Parse command line arguments
START_PROXY=false
if [[ "$1" == "--with-proxy" ]]; then
    START_PROXY=true
fi

echo "=== Starting Bay Bridge Traffic Services ==="
if [ "$START_PROXY" = true ]; then
    echo "    (including Python proxy server)"
fi
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

# Handle Python proxy
if [ "$START_PROXY" = true ]; then
    if [ -f "working-proxy.py" ]; then
        echo "🚀 Starting Python proxy server..."

        # Check if port 8080 is already in use
        if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "⚠️  Port 8080 is already in use. Skipping proxy startup."
            echo "   If you need to restart the proxy, stop the existing process first."
        else
            # Start proxy in background
            python3 working-proxy.py > proxy.log 2>&1 &
            PROXY_PID=$!

            # Wait a moment for startup
            sleep 3

            # Check if proxy started successfully
            if kill -0 $PROXY_PID 2>/dev/null; then
                echo "✅ Python proxy started (PID: $PROXY_PID)"
                echo "   Log file: proxy.log"
                echo "   To stop: kill $PROXY_PID"

                # Test if proxy is responding
                if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080 | grep -q "200"; then
                    echo "✅ Proxy is responding at http://localhost:8080"
                else
                    echo "⚠️  Proxy started but may still be initializing..."
                fi
            else
                echo "❌ Failed to start Python proxy"
                echo "   Check proxy.log for details"
            fi
        fi
    else
        echo "❌ Python proxy script not found (working-proxy.py)"
        echo "   Cannot start proxy server"
    fi
else
    # Just check if proxy script exists
    if [ -f "working-proxy.py" ]; then
        echo "✅ Python proxy script found (working-proxy.py)"
        echo "ℹ️  To start the proxy server, run: python3 working-proxy.py"
        echo "   Or use: ./start-bay-bridge-services.sh --with-proxy"
    else
        echo "⚠️  Python proxy script not found (working-proxy.py)"
        echo "   The proxy server provides dashboard access on port 8080"
    fi
fi

echo ""
echo "=== Services Started! ==="
echo ""
echo "Services running:"
echo "  📊 Grafana: http://localhost:3000 (admin/admin)"
echo "  📈 Prometheus: http://localhost:9090"
if [ "$START_PROXY" = true ] && kill -0 $PROXY_PID 2>/dev/null; then
    echo "  � Python Proxy: http://localhost:8080 (PID: $PROXY_PID)"
fi
echo "  �📡 Metrics Server: http://localhost:9091 (when app is running)"
echo ""

if [ "$START_PROXY" = true ] && kill -0 $PROXY_PID 2>/dev/null; then
    echo "Next steps:"
    echo "  1. Run './setup-cloudflare-tunnel.sh' to set up the tunnel (one-time)"
    echo "  2. Start the tunnel: cloudflared tunnel run grafana-local"
    echo "  3. Start traffic detection: python motion_detector.py"
    echo "  4. Access your dashboard at: https://bay-bridge-traffic.com"
    echo ""
    echo "Local access:"
    echo "  🏠 Dashboard: http://localhost:8080"
    echo "  📊 Direct Grafana: http://localhost:3000"
    echo ""
    echo "To stop the proxy: kill $PROXY_PID"
else
    echo "Next steps:"
    echo "  1. Start Python proxy: python3 working-proxy.py"
    echo "     (or restart with: ./start-bay-bridge-services.sh --with-proxy)"
    echo "  2. Run './setup-cloudflare-tunnel.sh' to set up the tunnel (one-time)"
    echo "  3. Start the tunnel: cloudflared tunnel run grafana-local"
    echo "  4. Start traffic detection: python motion_detector.py"
    echo "  5. Access your dashboard at: https://bay-bridge-traffic.com"
    echo ""
    echo "Local access:"
    echo "  🏠 Dashboard: http://localhost:8080 (after starting proxy)"
    echo "  📊 Direct Grafana: http://localhost:3000"
fi
