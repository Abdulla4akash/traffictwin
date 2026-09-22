#!/bin/sh
set -eu
cd "$(dirname "$0")"
engine="${TECTONIC:-tectonic}"
exec "$engine" -X compile TrafficTwin_Dissertation.tex --keep-logs --keep-intermediates
