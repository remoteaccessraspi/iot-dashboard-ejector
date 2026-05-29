#!/bin/bash

echo "=============================="
echo " IOT DASHBOARD GIT UPDATE"
echo "=============================="

cd ~/apps/iot_dashboard || exit

echo ""
echo "Adding files..."
git add .

if git diff --cached --quiet; then
    echo "No changes to commit."
    exit 0
fi

TS=$(date "+%Y-%m-%d %H:%M:%S")

echo "Commit: $TS"
git commit -m "update $TS"

echo "Pushing to GitHub..."
git push origin main

echo "DONE"
