#!/bin/bash
# Fly.ioでのマイグレーション実行スクリプト
# 使用方法: ./scripts/run_migration_fly.sh

set -e

echo "=== SmartIR Database Migration for Fly.io ==="

# 1. 現在のマイグレーション状態を確認
echo ""
echo "[Step 1] Checking current migration status..."
fly ssh console -C "cd /app && PYTHONPATH=. alembic current" || {
    echo "Failed to connect to Fly.io. Make sure 'fly' CLI is installed and you're logged in."
    exit 1
}

# 2. マイグレーション履歴を確認
echo ""
echo "[Step 2] Migration history:"
fly ssh console -C "cd /app && PYTHONPATH=. alembic history --verbose"

# 3. マイグレーションをアップグレード
echo ""
echo "[Step 3] Running migration upgrade..."
read -p "Proceed with migration? (y/n): " confirm
if [[ $confirm == "y" || $confirm == "Y" ]]; then
    fly ssh console -C "cd /app && PYTHONPATH=. alembic upgrade head"
    echo ""
    echo "Migration completed successfully!"
else
    echo "Migration cancelled."
    exit 0
fi

# 4. 最終状態を確認
echo ""
echo "[Step 4] Final migration status:"
fly ssh console -C "cd /app && PYTHONPATH=. alembic current"

echo ""
echo "=== Migration process complete ==="
