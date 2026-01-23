# ============================================================
# 文件说明: test_batch_api.py - 批次管理API测试
# ============================================================
# 用法:
#   cd D:\furnace-backend
#   venv\Scripts\python scripts\test_batch_api.py
# ============================================================

import sys
sys.path.insert(0, '.')

import requests
import time

BASE_URL = "http://localhost:8082"


def test_get_status():
    """测试1: 获取当前状态"""
    print("\n" + "=" * 60)
    print("测试1: 获取当前冶炼状态")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/batch/status")
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  state: {data['state']}")
        print(f"  is_smelting: {data['is_smelting']}")
        print(f"  is_running: {data['is_running']}")
        print(f"  batch_code: {data['batch_code']}")
        print(f"  elapsed_seconds: {data['elapsed_seconds']:.1f}s")
        return data
    else:
        print(f"❌ 错误: {response.text}")
        return None


def test_start_smelting(batch_code: str):
    """测试2: 开始冶炼"""
    print("\n" + "=" * 60)
    print(f"测试2: 开始冶炼 (批次号: {batch_code})")
    print("=" * 60)
    
    response = requests.post(
        f"{BASE_URL}/api/batch/start",
        json={"batch_code": batch_code}
    )
    print(f"状态码: {response.status_code}")
    
    data = response.json()
    if response.status_code == 200:
        print(f"✅ 成功: {data['message']}")
        print(f"   批次号: {data['batch_code']}")
    else:
        print(f"❌ 失败: {data.get('detail', data)}")
    
    return response.status_code == 200


def test_pause_smelting():
    """测试3: 暂停冶炼"""
    print("\n" + "=" * 60)
    print("测试3: 暂停冶炼")
    print("=" * 60)
    
    response = requests.post(f"{BASE_URL}/api/batch/pause")
    print(f"状态码: {response.status_code}")
    
    data = response.json()
    if response.status_code == 200:
        print(f"✅ 成功: {data['message']}")
    else:
        print(f"❌ 失败: {data.get('detail', data)}")
    
    return response.status_code == 200


def test_resume_smelting():
    """测试4: 恢复冶炼"""
    print("\n" + "=" * 60)
    print("测试4: 恢复冶炼")
    print("=" * 60)
    
    response = requests.post(f"{BASE_URL}/api/batch/resume")
    print(f"状态码: {response.status_code}")
    
    data = response.json()
    if response.status_code == 200:
        print(f"✅ 成功: {data['message']}")
    else:
        print(f"❌ 失败: {data.get('detail', data)}")
    
    return response.status_code == 200


def test_stop_smelting():
    """测试5: 停止冶炼"""
    print("\n" + "=" * 60)
    print("测试5: 停止冶炼")
    print("=" * 60)
    
    response = requests.post(f"{BASE_URL}/api/batch/stop")
    print(f"状态码: {response.status_code}")
    
    data = response.json()
    if response.status_code == 200:
        print(f"✅ 成功: {data['message']}")
    else:
        print(f"❌ 失败: {data.get('detail', data)}")
    
    return response.status_code == 200


def test_full_workflow():
    """完整工作流测试"""
    print("\n" + "=" * 60)
    print("完整工作流测试")
    print("=" * 60)
    
    batch_code = "03-2026-01-15"
    
    # 1. 检查初始状态
    print("\n步骤1: 检查初始状态")
    status = test_get_status()
    
    # 2. 开始冶炼
    print("\n步骤2: 开始冶炼")
    if not test_start_smelting(batch_code):
        print("⚠️ 可能已有进行中的批次，尝试先停止...")
        test_stop_smelting()
        test_start_smelting(batch_code)
    
    # 3. 等待5秒，检查状态
    print("\n步骤3: 等待5秒后检查状态...")
    time.sleep(5)
    test_get_status()
    
    # 4. 暂停冶炼
    print("\n步骤4: 暂停冶炼")
    test_pause_smelting()
    test_get_status()
    
    # 5. 等待3秒
    print("\n步骤5: 等待3秒（模拟暂停期间）...")
    time.sleep(3)
    
    # 6. 恢复冶炼
    print("\n步骤6: 恢复冶炼")
    test_resume_smelting()
    test_get_status()
    
    # 7. 等待3秒
    print("\n步骤7: 等待3秒...")
    time.sleep(3)
    
    # 8. 停止冶炼
    print("\n步骤8: 停止冶炼")
    test_stop_smelting()
    test_get_status()
    
    print("\n" + "=" * 60)
    print("✅ 完整工作流测试完成!")
    print("=" * 60)


def test_power_recovery():
    """测试断电恢复场景"""
    print("\n" + "=" * 60)
    print("断电恢复场景测试")
    print("=" * 60)
    
    batch_code = "03-2026-01-16"
    
    # 1. 开始冶炼
    print("\n步骤1: 开始新批次")
    test_stop_smelting()  # 先清理
    test_start_smelting(batch_code)
    
    # 2. 运行5秒
    print("\n步骤2: 运行5秒...")
    time.sleep(5)
    
    # 3. 模拟断电（直接检查状态文件）
    print("\n步骤3: 检查状态持久化文件...")
    try:
        with open("data/batch_state.json", "r") as f:
            print(f"状态文件内容:\n{f.read()}")
    except FileNotFoundError:
        print("⚠️ 状态文件不存在")
    
    # 4. 模拟重启后检查状态
    print("\n步骤4: 模拟重启后，检查状态")
    status = test_get_status()
    
    if status and status.get('state') in ('running', 'paused'):
        print(f"\n✅ 断电恢复检测成功!")
        print(f"   需要恢复: {status.get('batch_code')}")
        print(f"   已运行: {status.get('elapsed_seconds'):.1f}秒")
    
    # 5. 清理
    print("\n步骤5: 清理测试数据")
    test_stop_smelting()


# ============================================================
# 主函数
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("批次管理 API 测试")
    print("=" * 60)
    print(f"后端地址: {BASE_URL}")
    
    # 检查后端是否运行
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code != 200:
            print("❌ 后端服务未正常运行")
            sys.exit(1)
        print("✅ 后端服务正常")
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务")
        print("   请先启动后端: venv\\Scripts\\python main.py")
        sys.exit(1)
    
    # 运行测试
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="运行完整工作流测试")
    parser.add_argument("--recovery", action="store_true", help="运行断电恢复测试")
    parser.add_argument("--status", action="store_true", help="只查看当前状态")
    args = parser.parse_args()
    
    if args.full:
        test_full_workflow()
    elif args.recovery:
        test_power_recovery()
    elif args.status:
        test_get_status()
    else:
        # 默认运行所有测试
        test_full_workflow()
