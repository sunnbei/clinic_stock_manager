#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# データベース初期化
python -c "from app import init_db; init_db()"

# PostgreSQLマイグレーション（本番環境の場合）
if [ -n "$DATABASE_URL" ]; then
    python migrate_postgres.py
fi 