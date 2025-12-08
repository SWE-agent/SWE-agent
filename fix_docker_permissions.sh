#!/bin/bash
# 修复 Docker socket 权限的脚本
# 在 dev container 中，Docker 权限有时会被重置
# 运行此脚本以恢复访问权限

echo "🔧 修复 Docker socket 权限..."

# 检查 socket 是否存在
if [ ! -e /var/run/docker.sock ]; then
    echo "❌ Docker socket 不存在"
    exit 1
fi

# 修复权限
sudo chown root:docker /var/run/docker.sock 2>/dev/null || true
sudo chmod 666 /var/run/docker.sock 2>/dev/null || true

# 验证
if docker ps >/dev/null 2>&1; then
    echo "✅ Docker socket 权限已修复，Docker 可用"
    ls -la /var/run/docker.sock
    exit 0
else
    echo "❌ 权限修复失败，Docker 仍不可用"
    ls -la /var/run/docker.sock
    exit 1
fi
