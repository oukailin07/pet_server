#!/bin/bash

echo "========================================"
echo "网络连接自动修复工具"
echo "========================================"

# 1. 检查并开放防火墙端口
echo "1. 配置防火墙..."
if command -v ufw &> /dev/null; then
    echo "   开放80端口..."
    sudo ufw allow 80/tcp
    echo "   开放8765端口..."
    sudo ufw allow 8765/tcp
    echo "   防火墙规则已更新"
else
    echo "   UFW未安装，跳过防火墙配置"
fi

# 2. 检查iptables
echo ""
echo "2. 配置iptables..."
if command -v iptables &> /dev/null; then
    echo "   添加iptables规则..."
    sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null
    sudo iptables -A INPUT -p tcp --dport 8765 -j ACCEPT 2>/dev/null
    echo "   iptables规则已添加"
fi

# 3. 检查SELinux
echo ""
echo "3. 配置SELinux..."
if command -v sestatus &> /dev/null; then
    SELINUX_STATUS=$(sestatus | grep "SELinux status" | awk '{print $3}')
    if [ "$SELINUX_STATUS" = "enabled" ]; then
        echo "   SELinux已启用，配置端口..."
        sudo semanage port -a -t http_port_t -p tcp 80 2>/dev/null || echo "   80端口规则已存在"
        sudo semanage port -a -t http_port_t -p tcp 8765 2>/dev/null || echo "   8765端口规则已存在"
        echo "   SELinux端口规则已配置"
    else
        echo "   SELinux未启用"
    fi
else
    echo "   SELinux未安装"
fi

# 4. 检查网络接口
echo ""
echo "4. 网络接口信息："
ip addr show | grep -E "inet.*global" | while read line; do
    echo "   $line"
done

# 5. 测试本地连接
echo ""
echo "5. 测试本地连接..."
if curl -I http://127.0.0.1:80 2>/dev/null | grep -q "HTTP"; then
    echo "   ✓ 本地连接正常"
else
    echo "   ✗ 本地连接失败，请检查服务器是否正常启动"
fi

# 6. 检查端口监听
echo ""
echo "6. 端口监听状态："
if netstat -tlnp | grep -q ":80 "; then
    echo "   ✓ 80端口正在监听"
else
    echo "   ✗ 80端口未监听"
fi

if netstat -tlnp | grep -q ":8765 "; then
    echo "   ✓ 8765端口正在监听"
else
    echo "   ✗ 8765端口未监听"
fi

echo ""
echo "========================================"
echo "修复完成！"
echo "========================================"
echo "如果仍然无法访问，请检查："
echo "1. 云服务器安全组设置"
echo "2. 虚拟机网络模式"
echo "3. 路由器端口转发"
echo "4. 服务器是否在公网IP上"
echo ""
echo "测试命令："
echo "curl -I http://$(hostname -I | awk '{print $1}'):80"
echo "========================================" 