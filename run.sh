#!/usr/bin/env bash
# GitHub 热门项目推送 — 一键运行脚本
cd "$(dirname "$0")"
exec .venv/bin/python github_hot.py "$@"
