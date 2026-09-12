#!/bin/bash
set -e

cd "$(dirname "$0")/hackerrank_submission"

echo "============================================================"
echo "WISE MOM — HACKERRANK RUN"
echo "============================================================"

python3 code/main.py

echo ""
echo "✅ Run complete"
echo ""
echo "Generated:"
echo "  output.csv"
echo "  mom_mood.csv"
echo ""
head -n 6 output.csv
