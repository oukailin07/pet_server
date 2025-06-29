#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速创建管理员账户脚本
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pet_feeder_server import app, db, AdminUser
from werkzeug.security import generate_password_hash

def create_admin_user(username, password, email=None, role='admin'):
    """创建管理员用户"""
    with app.app_context():
        try:
            # 确保表存在
            db.create_all()
            
            # 检查用户名是否已存在
            existing_admin = AdminUser.query.filter_by(username=username).first()
            if existing_admin:
                print(f'❌ 用户名 {username} 已存在')
                return False
            
            # 创建管理员账户
            admin_user = AdminUser(
                username=username,
                password=generate_password_hash(password),
                email=email,
                role=role
            )
            
            db.session.add(admin_user)
            db.session.commit()
            
            print(f'✅ 管理员账户创建成功！')
            print(f'   用户名: {username}')
            print(f'   角色: {role}')
            print(f'   邮箱: {email or "未设置"}')
            print(f'   请使用此账户登录管理员界面')
            return True
            
        except Exception as e:
            print(f'❌ 创建管理员账户时出错: {e}')
            db.session.rollback()
            return False

def main():
    """主函数"""
    print("=" * 50)
    print("🐾 宠物喂食器 - 管理员账户创建工具")
    print("=" * 50)
    
    # 默认管理员账户
    default_admin = {
        'username': 'admin',
        'password': 'admin123',
        'email': 'admin@example.com',
        'role': 'admin'
    }
    
    print("创建默认管理员账户:")
    print(f"   用户名: {default_admin['username']}")
    print(f"   密码: {default_admin['password']}")
    print(f"   角色: {default_admin['role']}")
    print(f"   邮箱: {default_admin['email']}")
    
    # 创建默认管理员
    success = create_admin_user(
        default_admin['username'],
        default_admin['password'],
        default_admin['email'],
        default_admin['role']
    )
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 管理员账户创建完成！")
        print("=" * 50)
        print("登录信息:")
        print(f"   访问地址: http://你的服务器IP:80")
        print(f"   用户名: {default_admin['username']}")
        print(f"   密码: {default_admin['password']}")
        print("\n安全建议:")
        print("   1. 首次登录后立即修改密码")
        print("   2. 定期更换管理员密码")
        print("   3. 不要在公共网络使用默认密码")
        print("=" * 50)
    else:
        print("\n❌ 管理员账户创建失败！")

if __name__ == "__main__":
    main() 