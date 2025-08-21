#!/bin/bash

# 构建发布包脚本
# 该脚本会创建一个 release 目录，并将后端可执行文件、下载脚本和前端构建文件复制到其中

set -e  # 遇到错误时退出

echo "开始构建发布包..."

# 创建 release 目录
echo "1. 创建 release 目录..."
rm -rf release
mkdir -p release
echo "release 目录创建成功"

# 从 src/server/dist/main 提取 main 文件到 release 目录
echo "2. 复制后端可执行文件..."
if [ -f "src/server/dist/main" ]; then
    cp src/server/dist/main release/
    echo "后端可执行文件复制成功"
else
    echo "警告: src/server/dist/main 文件不存在，跳过复制"
fi

# 复制 src/server/download_console.sh 到 release 目录
echo "3. 复制下载脚本..."
if [ -f "src/server/download_console.sh" ]; then
    cp src/server/download_console.sh release/
    echo "下载脚本复制成功"
else
    echo "错误: src/server/download_console.sh 文件不存在"
    exit 1
fi

# 复制 dist 目录(前端生成的)到 release 目录
echo "4. 复制前端构建文件..."
if [ -d "dist" ]; then
    cp -r dist release/
    echo "前端构建文件复制成功"
else
    echo "警告: dist 目录不存在，跳过复制"
fi

echo "发布包构建完成!"
echo "发布文件位于: release/"