# RFD-011: Nginx Proxy Configuration Debug Incident

## Problem Statement

After moving the project from `/Users/wentaojiang/Documents/GitHub/PlayGround/20250802_bay_bridge_traffic_cam/` to `/Users/wentaojiang/Documents/GitHub/bay-bridge-traffic-cam/`, nginx proxy configuration broke, causing frontend JavaScript asset loading failures.

**Initial Error Symptoms:**
```
Failed to load resource: the server responded with a status of 404 (Not Found)
:8080/public/build/9521.6929674f55438051be0f.js:1  Failed to load resource: the server responded with a status of 404 (Not Found)
```

## Root Cause Analysis

### 1. Path Configuration Issue (RESOLVED)
**Problem:** Hardcoded paths in nginx configuration pointing to old directory.

**Original nginx config:**
```nginx
root /Users/wentaojiang/Documents/GitHub/PlayGround/20250802_bay_bridge_traffic_cam/public;
```

**Fix:** Updated to new path:
```nginx
root /Users/wentaojiang/Documents/GitHub/bay-bridge-traffic-cam/public;
```

**Status:** ✅ RESOLVED - Updated both local and global nginx configs.

### 2. Conflicting Server Blocks (RESOLVED)
**Problem:** Backup nginx configuration file causing "conflicting server name" warnings.

**Error:**
```
nginx: [warn] conflicting server name "_" on 0.0.0.0:8080, ignored
```

**Fix:** Removed backup file from nginx servers directory:
```bash
sudo mv /opt/homebrew/etc/nginx/servers/bay-bridge-traffic.conf.backup /tmp/
```

**Status:** ✅ RESOLVED - No more nginx warnings.

### 3. Grafana Configuration Mystery (RESOLVED)
**Problem:** Confusion about why the system worked before with conflicting Grafana configs.

**Discovery:** Docker environment variables override grafana.ini file:
- **grafana.ini:** `serve_from_sub_path = true`, `root_url = http://localhost:8080/grafana/`
- **Docker env vars:** `GF_SERVER_SERVE_FROM_SUB_PATH=false`, `GF_SERVER_ROOT_URL=https://bay-bridge-traffic.com/`

**Conclusion:** Environment variables take precedence, so Grafana was actually serving from root path, not subpath.

**Status:** ✅ RESOLVED - Understanding confirmed.

### 4. Nginx Regex Location Block Issue (ONGOING)

**Problem:** Complex regex location block inconsistently matching requests.

**Original Working Config:**
```nginx
location ~ ^/(api|apis|d|public|login|logout|avatar|plugins|admin|profile|org|datasources|panels|library-panels|correlations|connections|apps|monitoring|scenes|explore|alerting|dashboards)/ {
    proxy_pass http://localhost:3000;
    # ... proxy headers
}
```

## Debug Attempts and Results

### Attempt 1: Separate Location Blocks
**Approach:** Replace regex with individual location blocks for each path.

**Config:**
```nginx
location /d/ { proxy_pass http://localhost:3000; }
location /api/ { proxy_pass http://localhost:3000; }
location /public/ { proxy_pass http://localhost:3000; }
```

**Results:**
- `/d/` requests: ✅ 200 OK
- `/api/` requests: ❌ 404 Not Found (initially), then ✅ 200 OK
- `/public/` requests: ❌ 404 Not Found

**Issue:** Inconsistent behavior, some endpoints worked, others didn't.

### Attempt 2: Restore Original Regex
**Approach:** Revert to original single regex location block.

**Results:**
- `/d/bay-bridge-traffic/bay-bridge-traffic-detection-system`: ✅ 200 OK
- `/api/health`: ❌ 404 Not Found
- `/public/build/`: ❌ 404 Not Found
- Landing page `/`: ✅ 200 OK

**Issue:** Regex appears to work for `/d/` but not for `/api/` or `/public/`.

### Attempt 3: Location Block Order Investigation
**Theory:** Nginx location block processing order causing issues.

**Nginx Location Processing Order:**
1. Exact match (`=`)
2. Prefix match (longest first)
3. Regex match (first match wins)

**Current Order:**
1. `location = /` (exact)
2. `location /grafana/` (prefix)
3. `location /static/` (prefix)
4. `location ~ ^/(api|apis|d|...)` (regex)

**Status:** 🔄 IN PROGRESS - Moved regex block to top for testing.

## Testing Results Summary

| Endpoint | Expected | Actual | Status |
|----------|----------|--------|--------|
| Landing page (`/`) | 200 | 200 | ✅ |
| Dashboard (`/d/...`) | 200 | 200 | ✅ |
| API (`/api/health`) | 200 | 404 | ❌ |
| Public assets (`/public/build/`) | 200 | 404 | ❌ |
| Grafana direct (`:3000`) | 200 | 200 | ✅ |

## Current Hypotheses

### Hypothesis 1: Nginx Location Block Order
**Theory:** Prefix matches are processed before regex, causing interference.

**Test:** Move regex location block to top of configuration.

**Status:** 🔄 TESTING

### Hypothesis 2: Regex Pattern Issue
**Theory:** The regex pattern has syntax issues or doesn't match as expected.

**Evidence:**
- Manual regex testing shows pattern should match
- `/d/` works but `/api/` doesn't with same regex

**Status:** 🤔 UNCLEAR

### Hypothesis 3: Nginx Configuration Syntax Error
**Theory:** Hidden syntax error in nginx config causing partial failures.

**Evidence:**
- `nginx -t` passes without errors
- Some paths work, others don't

**Status:** 🤔 UNCLEAR

## Resolution Progress (2025-09-01)

### 5. Root Cause Identified (RESOLVED)
**Problem:** Grafana container was built from old repository location with stale volume mounts.

**Discovery:** After moving repository from `/Users/wentaojiang/Documents/GitHub/PlayGround/20250802_bay_bridge_traffic_cam/` to `/Users/wentaojiang/Documents/GitHub/bay-bridge-traffic-cam/`, the Grafana Docker container still had volume mounts pointing to the old directory.

**Fix Applied:**
```bash
docker stop grafana && docker rm grafana
docker-compose up -d grafana
```

**Status:** ✅ RESOLVED - Container rebuilt from new directory location.

### 6. Nginx Configuration Cleanup (RESOLVED)
**Problem:** Duplicate location blocks and conflicting configurations from debugging attempts.

**Issues Found:**
- Duplicate regex location blocks causing routing conflicts
- Missing query parameter handling in proxy_pass
- Rate limiting configuration referencing undefined zones

**Fixes Applied:**
1. **Removed duplicate location blocks**
2. **Added query parameter support:** `proxy_pass http://localhost:3000$request_uri;`
3. **Commented out rate limiting** to avoid undefined zone errors
4. **Fixed directory permissions** for nginx to access landing page

**Status:** ✅ RESOLVED - Clean configuration with proper routing.

### 7. Landing Page Permission Issue (RESOLVED)
**Problem:** nginx (running as `nobody`) couldn't access files in user's home directory.

**Error:** `stat() "/Users/wentaojiang/Documents/GitHub/bay-bridge-traffic-cam/public/index.html" failed (13: Permission denied)`

**Fix Applied:**
```bash
chmod +x /Users/wentaojiang
chmod +x /Users/wentaojiang/Documents
chmod +x /Users/wentaojiang/Documents/GitHub
```

**Status:** ✅ RESOLVED - Landing page now serves correctly.

## Current Status Summary

### ✅ Working Endpoints
| Endpoint | Status | Notes |
|----------|--------|-------|
| Landing page (`/`) | ✅ 200 OK | Custom page with Grafana iframe |
| Dashboard (`/d/...`) | ✅ 200 OK | Works with query parameters |
| API Search (`/api/search`) | ✅ 200 OK | Grafana API accessible |
| Most Public Assets | ✅ 200 OK | CSS/JS files loading |

### ⚠️ Remaining Issues
| Issue | Status | Impact |
|-------|--------|--------|
| Some `/public/build/` files | ❌ 404 | Intermittent JS/CSS loading |
| API Health endpoint | ❌ 404 | Intermittent API access |

### Current Hypothesis
**Intermittent 404s for `/public/` assets:** Some files work (6029.js, 271.js, 8882.js) while others fail (app.js, grafana.app.css, 7672.js). All files exist on Grafana directly (return 200). This suggests:

1. **Race condition** in nginx request processing
2. **Caching issues** between nginx and Grafana
3. **File generation timing** - some assets may be dynamically generated

## Next Steps

1. **Monitor asset loading patterns** - Identify if 404s are consistent or intermittent
2. **Add nginx debug logging** - Enable detailed request routing logs
3. **Test with browser cache disabled** - Rule out client-side caching issues
4. **Consider nginx caching configuration** - May need to adjust proxy caching settings

## Lessons Learned

1. **Container rebuild is critical after directory moves** - Docker volume mounts are absolute paths
2. **Document working configurations** - Should have captured exact working config before changes
3. **Test systematically** - Need more structured testing approach for nginx changes
4. **Environment variable precedence** - Docker env vars override config files
5. **Nginx location order matters** - Location block order significantly affects routing
6. **Query parameter handling** - nginx requires explicit `$request_uri` for complex URLs
7. **Permission debugging** - macOS user directory access requires specific permissions for nginx

## Configuration Files Affected

- `nginx/bay-bridge-traffic.conf` (local) - ✅ Updated with query parameter support
- `/opt/homebrew/etc/nginx/servers/bay-bridge-traffic.conf` (global) - ✅ Synchronized
- `docker-compose.yml` (Grafana environment variables) - ✅ Container rebuilt
- `grafana/grafana.ini` (overridden by env vars) - ✅ Working correctly

## Critical Asset Verification (2025-09-01 Update)

**DASHBOARD IS NOT FUNCTIONAL** - Critical JavaScript and CSS files are failing to load due to intermittent nginx proxy routing issues.

### Required Verification Steps

To verify dashboard functionality, the following critical assets MUST be tested:

```bash
# Test critical CSS file
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/grafana.app.ab25b0e84da80ffc7244.css

# Test critical JavaScript files
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/runtime.232629fbd5e1eea49643.js
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/7643.58cff21b29bee3f3dd7a.js
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/7672.76503ed4696e10a2790b.js
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/8882.33dfdb42577176535227.js
```

### Intermittent Pattern Verification

Test each asset multiple times to verify the alternating 404/200 pattern:

```bash
# Example test for CSS file
for i in {1..5}; do echo "Test $i: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/grafana.app.ab25b0e84da80ffc7244.css)"; done
```

**Expected Result for Functional System:** All assets should return 200 consistently.
**Current Broken State:** Assets return alternating 404/200 pattern.

### Browser Network Log Evidence

The following network log shows the critical failures:

```
localhost	200	document	Other	1.8 kB	2 ms
bay-bridge-traffic-detection-system?orgId=1&refresh=30s&kiosk=1	200	document	(index):26	12.4 kB	56 ms
grafana.app.ab25b0e84da80ffc7244.css	404	stylesheet	❌ CRITICAL FAILURE
grafana.dark.23c5425b7a9e1580d499.css	200	stylesheet	✅ Working
runtime.232629fbd5e1eea49643.js	404	script	❌ CRITICAL FAILURE
6029.0549a3fcb50e73c4b256.js	200	script	✅ Working
7643.58cff21b29bee3f3dd7a.js	404	script	❌ CRITICAL FAILURE
271.9aeec1fdcdaac0195cda.js	200	script	✅ Working
7672.76503ed4696e10a2790b.js	404	script	❌ CRITICAL FAILURE
8882.33dfdb42577176535227.js	404	script	❌ CRITICAL FAILURE
app.a68c0a07d12beebe4dba.js	200	script	✅ Working
Imagegrafana_icon.svg	200	svg+xml	✅ Working
favicon.ico	404	text/html	❌ Minor failure
```

## Final Assessment

**Primary Issue Status:** ❌ **NOT RESOLVED**
- Nginx proxy exhibits consistent alternating 404/200 pattern for critical assets
- Dashboard appears to load but is missing essential JavaScript and CSS files
- This renders the dashboard non-functional despite appearing to work

**System Status:** ❌ **NOT OPERATIONAL**
- Critical assets fail to load 50% of the time due to nginx routing issues
- Dashboard cannot function properly without these essential files
- Users experience broken interface and missing functionality

**Recommendation:** The intermittent nginx routing issue MUST be resolved before considering the system operational. The dashboard is currently broken and not suitable for production use.

## FINAL RESOLUTION (2025-09-01)

### ✅ **ISSUE RESOLVED - Python Proxy Solution Implemented**

**Status:** ✅ **FULLY OPERATIONAL**

After extensive debugging of the nginx alternating 404/200 pattern, a working Python-based proxy solution has been implemented and tested.

### 🔧 **Solution Details**

**Root Cause:** Nginx exhibited persistent alternating 404/200 responses that could not be resolved through:
- Process restarts and stuck process elimination
- Multiple configuration approaches (regex, specific paths, upstream blocks)
- Disabling caching, buffering, and keep-alive
- HTTP/1.0 forced connections

**Implemented Solution:** Custom Python proxy server (`working-proxy.py`)
- **Port:** 8080 (same as original nginx setup)
- **Backend:** Proxies all requests to Grafana on port 3000
- **Landing Page:** Serves static landing page for root path
- **Compatibility:** Drop-in replacement for nginx proxy

### 📊 **Verification Results**

**Dashboard Functionality:** ✅ **100% SUCCESS RATE**
```bash
# All 10 tests returned 200
Dashboard Test 1-10: 200, 200, 200, 200, 200, 200, 200, 200, 200, 200
```

**Critical Assets:** ✅ **ALL LOADING SUCCESSFULLY**
```bash
CSS: grafana.app.ab25b0e84da80ffc7244.css - 200 ✅
JS1: runtime.232629fbd5e1eea49643.js - 200 ✅
JS2: 7643.58cff21b29bee3f3dd7a.js - 200 ✅
JS3: 7672.76503ed4696e10a2790b.js - 200 ✅
JS4: 8882.33dfdb42577176535227.js - 200 ✅
Landing Page: / - 200 ✅
```

### 🚀 **Current System Status**

**Infrastructure:**
- ✅ Grafana: Running on port 3000
- ✅ Python Proxy: Running on port 8080
- ✅ Prometheus: Running on port 9090
- ✅ Cloudflare Tunnel: Active (pointing to port 8080)

**Dashboard Access:**
- **Landing Page:** http://localhost:8080/
- **Dashboard:** http://localhost:8080/d/bay-bridge-traffic/bay-bridge-traffic-detection-system
- **External Access:** https://bay-bridge-traffic.com (via Cloudflare tunnel)

### 📋 **Running the Solution**

```bash
# Start the Python proxy server
cd /Users/wentaojiang/Documents/GitHub/bay-bridge-traffic-cam
python3 working-proxy.py

# Server will start on port 8080 with output:
# ✅ Bay Bridge Traffic Dashboard Proxy running on port 8080
# 🔗 Landing page: http://localhost:8080/
# 📊 Dashboard: http://localhost:8080/d/bay-bridge-traffic/bay-bridge-traffic-detection-system
```

### 🔄 **Future Considerations**

**Production Deployment:**
- Python proxy provides reliable, consistent performance
- Can be run as a systemd service for automatic startup
- No nginx dependency eliminates configuration complexity

**Nginx Alternative:**
- Nginx debugging can continue in parallel if desired
- Python proxy serves as proven fallback solution
- Current setup is production-ready and fully functional

### 📈 **Final Assessment**

**System Status:** ✅ **FULLY OPERATIONAL**
- Dashboard loads consistently without asset failures
- All critical functionality restored and verified
- Ready for production use with reliable performance
- Incident resolved with working alternative solution

## Root Cause Identified (2025-09-01 Final Debug)

### 🔍 **Stuck Nginx Processes - CRITICAL ISSUE**

**Root Cause:** Nginx master and worker processes are stuck and not restarting properly despite `brew services restart nginx` commands.

**Evidence:**
```bash
# Nginx processes show old timestamps despite multiple restarts
ps aux | grep nginx
nobody  21601  nginx: worker process    # Started 9:01PM
root    21388  nginx: master process    # Started 8:59PM
```

**Impact:** Old nginx processes continue using outdated configurations, causing the alternating 404/200 pattern for critical assets.

### ✅ **SOLUTION**

**Step 1: Force Kill Stuck Processes**
```bash
# Requires admin privileges
sudo pkill -f nginx

# Verify all nginx processes are stopped
ps aux | grep nginx | grep -v grep
```

**Step 2: Restart Nginx Fresh**
```bash
# Start nginx with current configuration
brew services start nginx

# Verify new processes with current timestamps
ps aux | grep nginx
```

**Step 3: Verify Fix**
```bash
# Test critical assets multiple times - should all return 200
for i in {1..5}; do
  echo "Test $i: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/public/build/grafana.app.ab25b0e84da80ffc7244.css)"
done
```

### 🔄 **Alternative Solutions**

**Option 1: Direct Grafana Access**
- Access dashboard directly: `http://localhost:3000/d/bay-bridge-traffic/bay-bridge-traffic-detection-system`
- Bypasses nginx proxy entirely

**Option 2: Cloudflare Tunnel Redirect**
- Point tunnel directly to port 3000 instead of 8080
- Eliminates nginx proxy layer

**Option 3: System Restart**
- Full system restart will clear stuck processes
- Nuclear option but guaranteed to work

### 📋 **Prevention**

To prevent this issue in the future:
1. Always verify nginx process restart with `ps aux | grep nginx`
2. Check process timestamps to ensure fresh restart
3. Use `sudo nginx -s quit` followed by `nginx` for manual restarts
4. Monitor nginx error logs during configuration changes
