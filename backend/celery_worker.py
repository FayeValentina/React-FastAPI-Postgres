#!/usr/bin/env python3
"""
Celery Worker Entry Point
用于启动Celery Worker的独立脚本
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(__file__))

from app.celery_app import celery_app

if __name__ == '__main__':
    # 启动Celery Worker
    celery_app.start()