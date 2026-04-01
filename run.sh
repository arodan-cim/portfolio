#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "🦋 Golden Butterfly Portfolio — Full Pipeline"
echo "=============================================="
echo ""

# Activate venv
if [ -f venv/bin/activate ]; then
    . venv/bin/activate
else
    echo "❌ venv not found. Run: python3 -m venv venv && pip install -r requirements.txt"
    exit 1
fi

# Step 1: Download data + run analysis
echo "📡 Step 1/3: Downloading data & running analysis..."
python golden_butterfly.py
echo ""

# Step 2: Validate proxies
echo "📊 Step 2/3: Validating proxies..."
python validate_proxies.py
echo ""

# Step 3: Generate report
echo "📄 Step 3/3: Generating report..."
python report/sections/build_proxy_validation.py

echo ""
echo "✅ Done. Open report/index.html in your browser."
