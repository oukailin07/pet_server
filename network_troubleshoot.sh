#!/bin/bash

echo "========================================"
echo "网络连接故障排查工具"
echo "========================================"

# 获取服务器IP地址
echo "1. 服务器IP地址信息："
ip addr show | grep -E "inet.*global" | awk '{print "   " $2}'

# 检查端口监听状态
echo ""
echo "2. 端口监听状态："
echo "   80端口："
netstat -tlnp | grep :80 || echo "   80端口未监听"
echo "   8765端口："
netstat -tlnp | grep :8765 || echo "   8765端口未监听"

# 检查防火墙状态
echo ""
echo "3. 防火墙状态："
if command -v ufw &> /dev/null; then
    echo "   UFW状态："
    sudo ufw status
else
    echo "   UFW未安装"
fi

if command -v iptables &> /dev/null; then
    echo "   iptables规则："
    sudo iptables -L -n | head -20
fi

# 检查SELinux状态
echo ""
echo "4. SELinux状态："
if command -v sestatus &> /dev/null; then
    sestatus
else
    echo "   SELinux未安装"
fi

# 测试本地连接
echo ""
echo "5. 本地连接测试："
echo "   测试127.0.0.1:80："
curl -I http://127.0.0.1:80 2>/dev/null | head -1 || echo "   本地连接失败"

# 检查进程
echo ""
echo "6. Python进程状态："
ps aux | grep python | grep pet_feeder || echo "   未找到pet_feeder进程"

# 检查日志
echo ""
echo "7. 最近的系统日志："
journalctl -n 20 --no-pager | grep -E "(pet|python|flask)" || echo "   未找到相关日志"

echo ""
echo "========================================"
echo "排查建议："
echo "1. 如果80端口未监听，检查服务器是否正常启动"
echo "2. 如果防火墙阻止，运行: sudo ufw allow 80"
echo "3. 如果在云服务器上，检查安全组设置"
echo "4. 如果在虚拟机中，检查网络模式"
echo "========================================" 