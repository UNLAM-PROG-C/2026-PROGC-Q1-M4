#!/bin/sh
BACKEND="${BACKEND_URL:-http://localhost:3001}"
sed -i "s|http://localhost:3001|${BACKEND}|g" /usr/share/nginx/html/js/analyze.js
exec nginx -g "daemon off;"
