# ============================================================
# Modbus RTU 料仓重量 - PowerShell 测试命令集合
# ============================================================
# 用法: 在 PowerShell 中复制粘贴以下命令执行
# ============================================================

# 切换到项目目录
cd D:\furnace-backend

# ============================================================
# 1. 完整测试 (推荐)
# ============================================================
venv\Scripts\python scripts\test_modbus_weight.py


# ============================================================
# 2. 快速读取净重
# ============================================================
venv\Scripts\python -c "import sys; sys.path.insert(0, '.'); from app.tools.operation_modbus_weight_reader import read_hopper_weight; result = read_hopper_weight('COM1', 19200); print('成功:', result['success']); print('净重:', result['weight'], 'kg'); print('错误:', result['error'])"


# ============================================================
# 3. 测试请求报文生成
# ============================================================
venv\Scripts\python -c "import sys; sys.path.insert(0, '.'); from app.tools.operation_modbus_weight_reader import build_read_request; req = build_read_request(1, 2, 2); print('生成报文:', req.hex(' ').upper()); print('期望值:   01 03 00 02 00 02 65 CB')"


# ============================================================
# 4. 测试响应解析
# ============================================================
venv\Scripts\python -c "import sys; sys.path.insert(0, '.'); from app.tools.operation_modbus_weight_reader import parse_response_hex; success, weight, error = parse_response_hex('01 03 04 00 00 01 22 7B BA'); print('解析结果:', weight, 'kg')"


# ============================================================
# 5. 使用 read_hopper_weight.py 脚本
# ============================================================
venv\Scripts\python scripts\read_hopper_weight.py COM1


# ============================================================
# 6. 调试模式 (显示详细日志)
# ============================================================
venv\Scripts\python -c "import sys; import logging; logging.basicConfig(level=logging.DEBUG); sys.path.insert(0, '.'); from app.tools.operation_modbus_weight_reader import read_hopper_weight; result = read_hopper_weight('COM1', 19200); print('结果:', result)"
