"""
蝶阀状态队列 API 测试脚本
测试3个API端点的功能
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8082"


def test_valve_status_queues():
    """测试获取蝶阀状态队列"""
    print("\n" + "=" * 60)
    print("测试 1: 获取蝶阀状态队列")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/valve/status/queues", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ 状态码: {response.status_code}")
        print(f"✅ 响应成功: {data.get('success')}")
        print(f"✅ 时间戳: {data.get('timestamp')}")
        print(f"✅ 队列长度: {data.get('queue_length')}")
        
        # 显示每个蝶阀的队列信息
        valve_data = data.get('data', {})
        for valve_id in ['1', '2', '3', '4']:
            queue = valve_data.get(valve_id, [])
            if queue:
                print(f"\n蝶阀{valve_id}:")
                print(f"  - 队列长度: {len(queue)}")
                print(f"  - 最旧记录: {queue[0]['timestamp']} -> {queue[0]['status']} ({queue[0]['state_name']})")
                print(f"  - 最新记录: {queue[-1]['timestamp']} -> {queue[-1]['status']} ({queue[-1]['state_name']})")
            else:
                print(f"\n蝶阀{valve_id}: 队列为空")
        
        return True
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_latest_valve_status():
    """测试获取蝶阀最新状态"""
    print("\n" + "=" * 60)
    print("测试 2: 获取蝶阀最新状态")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/valve/status/latest", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ 状态码: {response.status_code}")
        print(f"✅ 响应成功: {data.get('success')}")
        print(f"✅ 时间戳: {data.get('timestamp')}")
        
        # 显示每个蝶阀的最新状态
        valve_data = data.get('data', {})
        print("\n最新状态:")
        for valve_id in ['1', '2', '3', '4']:
            status_info = valve_data.get(valve_id, {})
            status = status_info.get('status', 'N/A')
            state_name = status_info.get('state_name', 'N/A')
            timestamp = status_info.get('timestamp', 'N/A')
            
            # 状态可视化
            status_icon = {
                'open': '🟢 打开',
                'closed': '🔴 关闭',
                'error': '⚠️  异常',
                'unknown': '⚪ 未知'
            }.get(state_name, '❓')
            
            print(f"  蝶阀{valve_id}: {status_icon} (状态码: {status})")
        
        return True
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_valve_statistics():
    """测试获取蝶阀状态统计"""
    print("\n" + "=" * 60)
    print("测试 3: 获取蝶阀状态统计")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/valve/status/statistics", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ 状态码: {response.status_code}")
        print(f"✅ 响应成功: {data.get('success')}")
        print(f"✅ 时间戳: {data.get('timestamp')}")
        
        # 显示统计信息
        stats_data = data.get('data', {})
        print("\n状态统计:")
        for valve_id in ['1', '2', '3', '4']:
            stats = stats_data.get(valve_id, {})
            total = stats.get('total_records', 0)
            closed = stats.get('closed_count', 0)
            opened = stats.get('open_count', 0)
            error = stats.get('error_count', 0)
            unknown = stats.get('unknown_count', 0)
            closed_pct = stats.get('closed_percentage', 0)
            open_pct = stats.get('open_percentage', 0)
            
            print(f"\n蝶阀{valve_id}:")
            print(f"  - 总记录数: {total}")
            print(f"  - 关闭: {closed} ({closed_pct:.1f}%)")
            print(f"  - 打开: {opened} ({open_pct:.1f}%)")
            print(f"  - 异常: {error}")
            print(f"  - 未知: {unknown}")
        
        return True
    
    except requests.exceptions.RequestException as e:
        print(f"❌ 请求失败: {e}")
        return False


def main():
    print("=" * 60)
    print("🔧 蝶阀状态队列 API 测试")
    print("=" * 60)
    print(f"后端地址: {BASE_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 依次执行测试
    results = []
    results.append(("获取蝶阀状态队列", test_valve_status_queues()))
    results.append(("获取蝶阀最新状态", test_latest_valve_status()))
    results.append(("获取蝶阀状态统计", test_valve_statistics()))
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过!")
    else:
        print("\n⚠️  部分测试失败，请检查后端服务状态")


if __name__ == "__main__":
    main()
