#!/bin/bash
# ==============================================================================
# 🚀 PRE-DEPLOYMENT ORCHESTRATOR & SELF-HEALING DIAGNOSTIC ENGINE (PHASE 3)
# ==============================================================================
# Final validation suite: Uvicorn backgrounding, recursive health probing,
# base64 payload injection, explicit telemetry parsing, and self-healing.
# Cross-platform compatible for local Windows testing and Render Linux.
# ==============================================================================

export PYTHONUNBUFFERED=1
set -e
set -o pipefail

LOG_FILE="deploy.log"
MAX_RETRIES=3
PORT=10000

log_trace() {
    local level=$1
    local module=$2
    local message=$3
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    local log_line="[$timestamp] [$level] [$module] -> $message"
    echo "$log_line"
    echo "$log_line" >> "$LOG_FILE"
}

log_trace "INFO" "deploy.sh/init" "Initializing Phase 3 Orchestrator and Unbuffered Diagnostic Engine..."
> "$LOG_FILE"

# Cross-platform Python detection
PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi
# Hardcoded override for Windows testing environment if python is the store alias
if [ -f "/c/Python314/python.exe" ]; then
    PYTHON_CMD="/c/Python314/python.exe"
fi

# ------------------------------------------------------------------------------
# 1. DEPENDENCY & SYNTAX SCAN
# ------------------------------------------------------------------------------
for cmd in curl $PYTHON_CMD pip base64 grep; do
    if ! command -v $cmd &> /dev/null; then
        log_trace "CRITICAL" "deploy.sh/scan" "Missing critical dependency: $cmd. Halting."
        exit 1
    fi
done

log_trace "INFO" "deploy.sh/compile" "Running rigorous syntax check on Python application..."
if ! $PYTHON_CMD -m compileall backend/app/; then
    log_trace "CRITICAL" "deploy.sh/compile" "Syntax corruption detected! Halting deployment."
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. CREATE DUMMY TEST IMAGE (BASE64)
# ------------------------------------------------------------------------------
log_trace "INFO" "deploy.sh/setup" "Generating 1x1 JPEG dummy test image via Base64 payload..."
echo "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA=" | base64 -d > dummy_test.jpg

# ------------------------------------------------------------------------------
# 3. RECURSIVE SELF-HEALING LOOP
# ------------------------------------------------------------------------------
boot_and_test() {
    local attempt=$1
    log_trace "INFO" "deploy.sh/boot" "Attempting backend boot (Attempt $attempt/$MAX_RETRIES) on port $PORT..."

    # Pre-heal logic (Linux-only, safe skip for Windows Git Bash)
    if command -v lsof &> /dev/null; then
        if lsof -i:$PORT -t >/dev/null 2>&1; then
            log_trace "WARNING" "deploy.sh/heal" "Port $PORT blocked. Killing rogue processes..."
            lsof -i:$PORT -t | xargs kill -9
            sleep 2
        fi
    fi

    # Background the Python server
    export PYTHONPATH="$PWD/backend:$PYTHONPATH"
    $PYTHON_CMD -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT >> "$LOG_FILE" 2>&1 &
    local API_PID=$!
    log_trace "DEBUG" "deploy.sh/boot" "Process $API_PID spawned. Waiting for socket binding..."
    
    # Timeout-managed curl loop: Poll /health up to 10 times, 1 check every 2 seconds
    local health_ok=false
    for i in {1..10}; do
        sleep 2
        if ! kill -0 $API_PID 2>/dev/null; then
            log_trace "ERROR" "deploy.sh/boot" "Process $API_PID crashed during boot sequence."
            break
        fi
        
        local status=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:$PORT/health || echo "000")
        if [ "$status" -eq "200" ]; then
            health_ok=true
            log_trace "SUCCESS" "deploy.sh/boot" "Health probe returned 200 OK."
            break
        fi
        log_trace "DEBUG" "deploy.sh/boot" "Health probe returned $status. Retrying..."
    done

    if [ "$health_ok" != "true" ]; then
        log_trace "ERROR" "deploy.sh/boot" "Health probe failed to return 200 within timeout."
        kill -9 $API_PID 2>/dev/null || true
        return 1
    fi

    # --------------------------------------------------------------------------
    # Execute Base64 Dummy Image Injection & Inference Test
    # --------------------------------------------------------------------------
    log_trace "INFO" "deploy.sh/test" "Executing verbose curl injection to trigger Analyser Lazy Loading..."
    
    curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST \
      -F "file=@dummy_test.jpg" \
      -F "manual_text_override=Deployment Pipeline Validation Test" \
      http://127.0.0.1:$PORT/api/v1/predict -o response.json > curl_out.txt 2>&1
      
    local http_code=$(grep "HTTP_STATUS:" curl_out.txt | cut -d':' -f2)
    local payload=$(cat response.json 2>/dev/null || echo "")

    log_trace "INFO" "deploy.sh/test" "Inference HTTP Status: $http_code"
    log_trace "INFO" "deploy.sh/test" "Inference Payload: $payload"

    # Verify Telemetry Signals
    local telemetry_passed=false
    if grep -q "\[TELEMETRY:LAZY_LOAD:COMPLETE\].*SUCCESS" "$LOG_FILE"; then
        telemetry_passed=true
        log_trace "SUCCESS" "deploy.sh/test" "Telemetry signature [TELEMETRY:LAZY_LOAD:COMPLETE] SUCCESS found."
    elif echo "$payload" | grep -q "confidence"; then
        telemetry_passed=true
        log_trace "SUCCESS" "deploy.sh/test" "Valid JSON classification output detected."
    fi

    if [ "$http_code" -eq "200" ] && [ "$telemetry_passed" = true ]; then
        log_trace "SUCCESS" "deploy.sh/test" "Analyser successfully processed test payload."
        kill -SIGTERM $API_PID 2>/dev/null || true # Clean termination invokes close_db()
        sleep 2
        kill -9 $API_PID 2>/dev/null || true
        return 0
    else
        log_trace "ERROR" "deploy.sh/test" "Analyser failed to process dummy payload or crashed (OOM)."
        
        # Self-Healing Fallback
        log_trace "WARNING" "deploy.sh/heal" "Dumping last 20 lines of deploy.log for real-time visibility:"
        tail -n 20 "$LOG_FILE" | while read -r line; do log_trace "DEBUG" "deploy.sh/diag-dump" "$line"; done
        
        log_trace "WARNING" "deploy.sh/heal" "Invoking clean termination to trigger close_db() and purging cache paths..."
        kill -SIGTERM $API_PID 2>/dev/null || true
        sleep 2
        kill -9 $API_PID 2>/dev/null || true
        
        rm -rf ~/.cache/huggingface/hub/* 2>/dev/null || true
        return 1
    fi
}

# ------------------------------------------------------------------------------
# 4. EXECUTE LOOP
# ------------------------------------------------------------------------------
current_attempt=1
deploy_success=false

while [ $current_attempt -le $MAX_RETRIES ]; do
    if boot_and_test $current_attempt; then
        deploy_success=true
        break
    else
        if [ $current_attempt -eq $MAX_RETRIES ]; then
            log_trace "CRITICAL" "deploy.sh/fatal" "Max retries reached. Analyser remains uninitialized or failing."
            break
        fi
        current_attempt=$((current_attempt + 1))
        log_trace "INFO" "deploy.sh/retry" "Incrementing loop pointer. Retrying deployment..."
        sleep 3
    fi
done

# Gracefully sweep away temporary assets
rm -f dummy_test.jpg response.json curl_out.txt

if [ "$deploy_success" = true ]; then
    log_trace "SUCCESS" "deploy.sh/success" "✅ VERIFICATION FRAMEWORK PASSED — Analyser Model is active and fully responsive."
    exit 0
else
    log_trace "CRITICAL" "deploy.sh/fatal" "❌ VERIFICATION FRAMEWORK FAILED — Hard exit."
    exit 1
fi
