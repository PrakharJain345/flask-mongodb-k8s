#!/bin/sh
# Load generator script for HPA autoscaling verification

TARGET_URL="${1:-http://flask-svc:5000/cpu}"
CONCURRENCY="${2:-1}"

echo "Generating load against ${TARGET_URL}..."

while true; do
  wget -q -O- "${TARGET_URL}" > /dev/null
done

