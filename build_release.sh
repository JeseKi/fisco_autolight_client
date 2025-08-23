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

# 复制 src/server/build_chain.sh 到 release 目录
echo "4. 复制 build_chain.sh 脚本..."
if [ -f "src/server/build_chain.sh" ]; then
    cp src/server/build_chain.sh release/
    echo "build_chain.sh 脚本复制成功"
else
    echo "警告: src/server/build_chain.sh 文件不存在，跳过复制"
fi

# 复制 dist 目录(前端生成的)到 release 目录
echo "5. 复制前端构建文件..."
if [ -d "dist" ]; then
    cp -r dist release/
    echo "前端构建文件复制成功"
else
    echo "警告: dist 目录不存在，跳过复制"
fi

# 复制 ~/.fisco/ 目录到 release 目录
echo "6. 复制 .fisco 配置目录..."
if [ -d "$HOME/.fisco" ]; then
    cp -r "$HOME/.fisco" release/
    echo ".fisco 配置目录复制成功"
else
    echo "警告: $HOME/.fisco 目录不存在，跳过复制"
fi

# 创建 run.sh 脚本
echo "7. 创建运行脚本..."
cat > release/run.sh << 'EOF'
#!/bin/bash

# 运行脚本
# 该脚本会检查 ~/.fisco 是否存在，如果不存在则从当前目录复制，并运行 main 二进制文件

set -e  # 遇到错误时退出

echo "开始运行..."

# 检查并复制 .fisco 目录
echo "1. 检查 .fisco 配置目录..."
if [ ! -d "$HOME/.fisco" ]; then
    echo "~/.fisco 目录不存在，正在从当前目录复制..."
    if [ -d "./.fisco" ]; then
        cp -r "./.fisco" "$HOME/"
        echo ".fisco 配置目录复制成功"
    else
        echo "警告: 当前目录中不存在 .fisco 目录，将使用默认配置"
    fi
else
    echo "~/.fisco 配置目录已存在，跳过复制"
fi

# 运行 main 二进制文件
echo "2. 运行主程序..."
if [ -f "./main" ]; then
    ./main
else
    echo "错误: main 二进制文件不存在"
    exit 1
fi
EOF

# 给 run.sh 脚本添加执行权限
chmod +x release/run.sh
echo "运行脚本创建成功"

echo "发布包构建完成!"
echo "发布文件位于: release/"