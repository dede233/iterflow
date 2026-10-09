#!/usr/bin/env bash
set -euo pipefail
root_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# Start Web only after API is ready so its startup DNS lookup sees the service.
"$root_dir/dc.sh" stop web api
"$root_dir/dc.sh" restart redis
"$root_dir/dc.sh" up -d --wait --wait-timeout 300 redis api web
