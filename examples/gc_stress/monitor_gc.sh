#!/bin/bash
#
# Monitor RAM usage of the gc_stress example compiled with different GC options.
#
# Usage:
#   ./monitor_gc.sh
#
# This script:
#   1. Compiles examples/gc_stress.spy with --gc=none and --gc=bdwgc
#   2. Runs each binary while sampling RSS (resident set size) every 0.1s
#   3. Reports peak RSS for each run
#
# Expected result:
#   --gc=none:  peak RSS grows unbounded (proportional to total allocations)
#   --gc=bdwgc: peak RSS stays bounded (GC reclaims memory)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SPY_FILE="$SCRIPT_DIR/gc_stress.spy"
BUILD_DIR="$SCRIPT_DIR/build"

echo "=== Compiling with --gc=none ==="
spy build -t native --gc none -b "$BUILD_DIR" "$SPY_FILE"
cp "$BUILD_DIR/gc_stress" "$BUILD_DIR/gc_stress_none"

echo ""
echo "=== Compiling with --gc=bdwgc ==="
spy build -t native --gc bdwgc -b "$BUILD_DIR" "$SPY_FILE"
cp "$BUILD_DIR/gc_stress" "$BUILD_DIR/gc_stress_bdwgc"

# monitor_rss: run a command in background and sample its RSS
# Usage: monitor_rss <label> <executable>
monitor_rss() {
    local label="$1"
    local exe="$2"
    local peak_rss=0

    # Run the executable in background
    "$exe" &
    local pid=$!

    # Sample RSS every 0.1 seconds
    while kill -0 "$pid" 2>/dev/null; do
        # Read VmRSS from /proc (in kB)
        local rss
        rss=$(awk '/VmRSS/ {print $2}' /proc/$pid/status 2>/dev/null || echo 0)
        if [ "$rss" -gt "$peak_rss" ] 2>/dev/null; then
            peak_rss=$rss
        fi
        sleep 0.1
    done

    wait "$pid" 2>/dev/null || true
    local peak_mb=$(( peak_rss / 1024 ))
    echo "$label: peak RSS = ${peak_mb} MB (${peak_rss} kB)"
}

echo ""
echo "=== Running with --gc=none ==="
monitor_rss "--gc=none " "$BUILD_DIR/gc_stress_none"

echo ""
echo "=== Running with --gc=bdwgc ==="
monitor_rss "--gc=bdwgc" "$BUILD_DIR/gc_stress_bdwgc"

# Cleanup temporary binaries
rm -f "$BUILD_DIR/gc_stress_none" "$BUILD_DIR/gc_stress_bdwgc"

echo ""
echo "Done. With --gc=none, peak RSS should be much larger than with --gc=bdwgc."
