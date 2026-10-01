#!/usr/bin/env python3
"""
Working HTTP proxy for Bay Bridge Traffic Dashboard
Routes all requests to Grafana on port 3000
Serves landing page for root requests
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import urllib.error
import os
import sys

class WorkingProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def handle_request(self):
        # Serve landing page for root path
        if self.path == '/':
            self.serve_landing_page()
            return
        
        # Proxy everything else to Grafana
        self.proxy_to_grafana()
    
    def serve_landing_page(self):
        try:
            landing_page_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public', 'index.html')
            with open(landing_page_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(f"Landing page not found: {str(e)}".encode())
    
    def proxy_to_grafana(self):
        # Target Grafana directly
        target_host = "localhost:3000"
        target_url = f"http://{target_host}{self.path}"
        
        try:
            # Create request
            req = urllib.request.Request(target_url)
            
            # Copy headers from original request
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection']:
                    req.add_header(header, value)
            
            # Add proper host header
            req.add_header('Host', target_host)
            
            # Handle POST data
            if self.command == 'POST':
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                req.data = post_data
            
            # Make request to Grafana
            with urllib.request.urlopen(req) as response:
                # Send response status
                self.send_response(response.getcode())
                
                # Copy response headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()
                
                # Copy response body
                self.wfile.write(response.read())
                
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Proxy Error: {str(e)}".encode())

if __name__ == "__main__":
    PORT = 8080
    
    with socketserver.TCPServer(("", PORT), WorkingProxyHandler) as httpd:
        print(f"✅ Bay Bridge Traffic Dashboard Proxy running on port {PORT}")
        print(f"🔗 Landing page: http://localhost:{PORT}/")
        print(f"📊 Dashboard: http://localhost:{PORT}/d/bay-bridge-traffic/bay-bridge-traffic-detection-system")
        print(f"🔄 Proxying all requests to Grafana on localhost:3000")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down proxy server...")
            httpd.shutdown()
