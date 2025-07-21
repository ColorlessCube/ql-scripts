#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能网络连接诊断和修复脚本
功能：
1. 检查Google连通性
2. 如果连接失败，智能诊断OpenClash状态
3. 根据OpenClash状态采取相应措施：
   - 如果OpenClash未运行 → 启动服务
   - 如果OpenClash运行但Google不通 → 重启服务
4. 提供详细的诊断信息和修复建议
"""

import requests
import time
import sys
from datetime import datetime

# 配置参数
GOOGLE_URL = "https://www.google.com"
OPENCLASH_STATUS_URL = "http://192.168.100.2:3789/api/v1.0/clash/status"
OPENCLASH_DOWN_URL = "http://192.168.100.2:3789/api/v1.0/clash/down"  # 替换为实际的重启URL
OPENCLASH_UP_URL = "http://192.168.100.2:3789/api/v1.0/clash/up"  # 替换为实际的重启URL

TIMEOUT = 10  # 连接超时时间（秒）
MAX_RETRIES = 3  # 最大重试次数
RETRY_INTERVAL = 30  # 重试间隔（秒）


def log_message(message):
    """打印带时间戳的日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


def check_google_connectivity():
    """检查Google连通性"""
    try:
        response = requests.get(GOOGLE_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            log_message("✅ Google连接正常")
            return True
        else:
            log_message(f"❌ Google返回状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log_message(f"❌ 无法连接Google: {e}")
        return False


def check_openclash_status():
    """检查OpenClash服务状态"""
    try:
        response = requests.get(OPENCLASH_STATUS_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            # 尝试解析响应内容
            try:
                data = response.json()
                # 根据API响应判断状态，常见的状态字段可能是 'running', 'status', 'state' 等
                if isinstance(data, dict):
                    # 检查可能的状态字段
                    status_fields = ['running', 'status', 'state', 'enabled', 'active', 'success']
                    for field in status_fields:
                        if field in data:
                            status_value = data[field]
                            if status_value in [True, 'running', 'active', 'enabled', 'up', 1]:
                                log_message("✅ OpenClash服务正在运行")
                                return True
                            else:
                                log_message(f"❌ OpenClash服务未运行，状态: {status_value}")
                                return False

                    # 如果没有找到明确的状态字段，但返回了数据，假设服务正在运行
                    log_message("✅ OpenClash服务响应正常（推测正在运行）")
                    return True
                else:
                    log_message("✅ OpenClash服务响应正常")
                    return True
            except ValueError:
                # 如果不是JSON响应，但状态码是200，假设服务正在运行
                log_message("✅ OpenClash服务响应正常")
                return True
        else:
            log_message(f"❌ OpenClash状态检查失败，状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log_message("❌ 无法连接到OpenClash服务（服务可能未启动）")
        return False
    except requests.exceptions.Timeout:
        log_message("❌ OpenClash状态检查超时")
        return False
    except requests.exceptions.RequestException as e:
        log_message(f"❌ OpenClash状态检查异常: {e}")
        return False


def start_openclash():
    """启动OpenClash服务"""
    try:
        log_message("🚀 正在启动OpenClash服务...")
        response = requests.get(OPENCLASH_UP_URL, timeout=TIMEOUT)
        if response.status_code == 200:
            log_message("✅ OpenClash启动请求发送成功")
            # 等待服务启动
            log_message("⏳ 等待服务启动...")
            time.sleep(15)
            return True
        else:
            log_message(f"❌ OpenClash启动失败，状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log_message(f"❌ OpenClash启动请求异常: {e}")
        return False


def restart_openclash():
    """重启OpenClash代理 - 通过down + up实现，增强鲁棒性"""

    def execute_request(url, operation_name, max_retries=3):
        """执行HTTP请求，带重试机制"""
        for attempt in range(1, max_retries + 1):
            try:
                log_message(f"🔄 执行{operation_name}操作 (尝试 {attempt}/{max_retries})")
                response = requests.get(url, timeout=TIMEOUT)

                if response.status_code == 200:
                    log_message(f"✅ {operation_name}操作成功")
                    return True
                else:
                    log_message(f"❌ {operation_name}操作失败，状态码: {response.status_code}")
                    if attempt < max_retries:
                        log_message(f"⏳ 等待3秒后重试...")
                        time.sleep(3)

            except requests.exceptions.Timeout:
                log_message(f"⏰ {operation_name}操作超时")
                if attempt < max_retries:
                    log_message(f"⏳ 等待3秒后重试...")
                    time.sleep(3)

            except requests.exceptions.ConnectionError:
                log_message(f"🔌 {operation_name}操作连接错误")
                if attempt < max_retries:
                    log_message(f"⏳ 等待5秒后重试...")
                    time.sleep(5)

            except requests.exceptions.RequestException as e:
                log_message(f"❌ {operation_name}操作异常: {e}")
                if attempt < max_retries:
                    log_message(f"⏳ 等待3秒后重试...")
                    time.sleep(3)

        log_message(f"❌ {operation_name}操作最终失败，已重试{max_retries}次")
        return False

    try:
        log_message("🔄 开始重启OpenClash代理...")

        # 步骤1: 执行down操作
        log_message("📉 第一步：停止OpenClash服务")
        if not execute_request(OPENCLASH_DOWN_URL, "停止服务"):
            log_message("❌ 停止服务失败，重启操作中止")
            return False

        # 步骤2: 等待服务完全停止
        log_message("⏳ 等待服务完全停止...")
        time.sleep(5)

        # 步骤3: 执行up操作
        log_message("📈 第二步：启动OpenClash服务")
        if not execute_request(OPENCLASH_UP_URL, "启动服务"):
            log_message("❌ 启动服务失败")
            # 即使启动失败，也尝试再次启动
            log_message("🔄 尝试再次启动服务...")
            time.sleep(3)
            if not execute_request(OPENCLASH_UP_URL, "重新启动服务", max_retries=2):
                log_message("❌ 重新启动服务也失败，请手动检查")
                return False

        # 步骤4: 等待服务完全启动
        log_message("⏳ 等待服务完全启动...")
        time.sleep(10)

        log_message("✅ OpenClash重启操作完成")
        return True

    except Exception as e:
        log_message(f"❌ 重启过程中发生未预期的错误: {e}")
        return False


def main():
    """主函数 - 智能检查和修复网络连接"""
    log_message("🚀 开始智能网络连接检查...")

    # 第一步：检查Google连通性
    for attempt in range(1, MAX_RETRIES + 1):
        log_message(f"📡 第 {attempt}/{MAX_RETRIES} 次Google连通性检查")

        if check_google_connectivity():
            log_message("🎉 Google连接正常，网络状态良好")
            sys.exit(0)

        if attempt < MAX_RETRIES:
            log_message(f"⏳ {RETRY_INTERVAL}秒后重试...")
            time.sleep(RETRY_INTERVAL)

    # 第二步：Google连接失败，检查OpenClash状态
    log_message("⚠️ Google连接失败，开始诊断OpenClash状态...")

    openclash_running = check_openclash_status()

    if not openclash_running:
        # OpenClash未运行，尝试启动
        log_message("🔧 检测到OpenClash未运行，尝试启动服务...")

        if start_openclash():
            log_message("✅ OpenClash启动完成，验证连接...")

            # 启动后验证连接
            if check_google_connectivity():
                log_message("🎉 启动OpenClash后连接恢复正常")
                sys.exit(0)
            else:
                log_message("❌ 启动OpenClash后仍无法连接Google，可能需要检查配置")
        else:
            log_message("❌ OpenClash启动失败，请手动检查")

    else:
        # OpenClash正在运行但Google不通，尝试重启
        log_message("🔄 OpenClash正在运行但Google不通，尝试重启服务...")

        if restart_openclash():
            log_message("✅ OpenClash重启完成，等待服务恢复...")
            time.sleep(60)  # 等待代理重启

            # 重启后再次检查
            if check_google_connectivity():
                log_message("🎉 重启OpenClash后连接恢复正常")
                sys.exit(0)
            else:
                log_message("❌ 重启OpenClash后仍无法连接Google")

                # 最后尝试：再次检查OpenClash状态
                log_message("🔍 进行最终状态检查...")
                final_status = check_openclash_status()
                if final_status:
                    log_message("⚠️ OpenClash服务正常，但Google仍不可达，可能是:")
                    log_message("   1. 代理配置问题")
                    log_message("   2. 上游网络问题")
                    log_message("   3. Google服务被阻断")
                    log_message("   建议手动检查OpenClash配置和日志")
                else:
                    log_message("❌ OpenClash服务异常，请手动检查服务状态")
        else:
            log_message("❌ OpenClash重启失败，请手动处理")

    log_message("🏁 网络诊断完成，请根据上述信息进行相应处理")


if __name__ == "__main__":
    main()
