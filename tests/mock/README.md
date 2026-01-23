# Mock 测试框架说明

## 目录结构

```
tests/
└── mock/
    ├── __init__.py
    ├── mock_data_generator.py      # 核心数据生成器
    ├── mock_polling_service.py     # 独立模拟轮询服务
    ├── mock_plc_server.py          # 模拟S7-1200 PLC服务器
    ├── mock_modbus_server.py       # 模拟Modbus RTU料仓重量服务器
    ├── test_data_variation.py      # 数据变化测试
    └── README.md                   # 本文档
```

## 使用场景对比

### 1. 独立Mock轮询服务 (`mock_polling_service.py`)

**适用场景**: 后端开发测试，不依赖PLC硬件

**特点**:
- ✅ 完全独立运行，不需要修改后端代码
- ✅ 直接写入InfluxDB，前端可直接调用API
- ✅ 使用真实的解析器和转换器，确保数据格式正确
- ❌ 无法测试PLC连接逻辑

**使用方法**:
```bash
# 1. 启动 InfluxDB
docker compose up -d influxdb

# 2. 运行独立Mock服务
python tests/mock/mock_polling_service.py

# 3. 启动前端测试（后端API无需启动）
flutter run -d windows
```

**输出示例**:
```
🚀 电炉模拟轮询服务启动
📊 轮询间隔: 5秒
📦 DB块: DB30(状态), DB32(传感器), DB33(电表)
✅ DB32 (传感器): 已写入 - 电极深度, 压力, 流量, 蝶阀
✅ DB33 (电表): Pt=6.52kW, I_0=302.0A (CT=20)
✅ 料仓重量: 448 kg
```

---

### 2. Mock PLC服务器 (`mock_plc_server.py`)

**适用场景**: 测试真实PLC连接代码，验证通信逻辑

**特点**:
- ✅ 模拟真实的S7-1200 PLC，后端代码无需修改
- ✅ 测试PLC连接、断线重连、错误处理等逻辑
- ✅ 动态生成数据，每5秒更新一次
- ⚠️ 需要安装 `python-snap7` 库

**使用方法**:
```bash
# 1. 安装依赖
pip install python-snap7

# 2. 启动Mock PLC服务器
python tests/mock/mock_plc_server.py

# 3. 修改 config.py
plc_ip = "127.0.0.1"  # 连接到本地Mock PLC

# 4. 启动后端（关闭Mock模式）
# config.py: use_mock_data = False
python -m uvicorn main:app --host 0.0.0.0 --port 8083
```

**输出示例**:
```
🚀 电炉 Mock PLC 服务器启动
📡 监听地址: 0.0.0.0:102
📦 提供服务: DB30 (40B), DB32 (28B), DB33 (56B)
✅ DB30 已注册 (40 bytes)
✅ DB32 已注册 (28 bytes)
✅ DB33 已注册 (56 bytes)
🎯 服务器监听中: 0.0.0.0:102
[16:30:15] 数据已更新 - DB30/DB32/DB33
```

---

### 3. Mock Modbus服务器 (`mock_modbus_server.py`)

**适用场景**: 测试Modbus RTU料仓重量读取，无需真实称重仪表

**特点**:
- ✅ 模拟真实的Modbus RTU设备（料仓称重仪表）
- ✅ 支持虚拟串口通信
- ✅ 动态生成重量数据，模拟下料过程
- ⚠️ 需要安装 `pymodbus` 和虚拟串口工具

**使用方法**:

#### Windows:
```bash
# 1. 安装 com0com 创建虚拟串口对 (COM10 <-> COM11)
# 下载: https://sourceforge.net/projects/com0com/

# 2. 安装依赖
pip install pymodbus

# 3. 启动Mock Modbus服务器（监听COM10）
python tests/mock/mock_modbus_server.py --port COM10

# 4. 修改 config.py
modbus_port = "COM11"  # 后端连接到COM11

# 5. 启动后端
python -m uvicorn main:app --host 0.0.0.0 --port 8083
```

#### Linux:
```bash
# 1. 创建虚拟串口对
socat -d -d pty,raw,echo=0 pty,raw,echo=0
# 输出: /dev/pts/2 <-> /dev/pts/3

# 2. 安装依赖
pip install pymodbus

# 3. 启动Mock Modbus服务器
python tests/mock/mock_modbus_server.py --port /dev/pts/2

# 4. 修改 config.py
modbus_port = "/dev/pts/3"

# 5. 启动后端
python -m uvicorn main:app --host 0.0.0.0 --port 8083
```

**输出示例**:
```
🚀 电炉 Mock Modbus RTU 服务器启动
📡 串口: COM10
📊 波特率: 19200
🆔 从站ID: 1
📦 寄存器: 40001-40002 (料仓重量, kg)
✅ 初始重量: 450 kg
[16:30:20] 重量已更新: 448 kg (寄存器: 0x0000 0x01C0)
```

---

## 数据生成特性

### 动态变化逻辑

1. **正弦波动** (`_add_sine_wave`)
   - 模拟周期性变化（如温度、功率波动）
   - 参数: `amplitude` (振幅), `period` (周期)

2. **随机噪声** (`_add_noise`)
   - 模拟传感器测量误差
   - 参数: `noise_range` (噪声范围，默认3%)

3. **能耗累计**
   - 电表能耗持续递增
   - 根据功率计算增量: `ΔE = P * Δt / 3600`

4. **料仓消耗**
   - 10%概率切换下料状态
   - 下料时重量递减: `weight -= rate * interval`
   - 消耗速率: 0.8-2.0 kg/s

### 测试数据变化

运行测试脚本验证数据生成逻辑:
```bash
python tests/mock/test_data_variation.py
```

**测试内容**:
- ✅ 数据块大小验证 (DB30=40B, DB32=28B, DB33=56B)
- ✅ 电极深度波动测试
- ✅ 电表能耗累计测试
- ✅ 料仓重量消耗模拟测试

---

## 数据格式说明

### DB32 传感器数据 (28字节)

```
Offset | Module         | Type              | Size | 说明
-------|---------------|-------------------|------|------------------
0      | LENTH1        | InfraredDistance  | 4B   | 电极1深度 (mm)
4      | LENTH2        | InfraredDistance  | 4B   | 电极2深度 (mm)
8      | LENTH3        | InfraredDistance  | 4B   | 电极3深度 (mm)
12     | WATER_PRESS_1 | PRESSURE          | 2B   | 炉皮冷却水压 (MPa*100)
14     | WATER_PRESS_2 | PRESSURE          | 2B   | 炉盖冷却水压 (MPa*100)
16     | WATER_FLOW_1  | FLOW_METER        | 2B   | 炉皮冷却水流量 (m³/h*100)
18     | WATER_FLOW_2  | FLOW_METER        | 2B   | 炉盖冷却水流量 (m³/h*100)
20     | MF_1          | ButterFlyValve    | 2B   | 蝶阀1开度 (%)
22     | MF_2          | ButterFlyValve    | 2B   | 蝶阀2开度 (%)
24     | MF_3          | ButterFlyValve    | 2B   | 蝶阀3开度 (%)
26     | MF_4          | ButterFlyValve    | 2B   | 蝶阀4开度 (%)
```

### DB33 电表数据 (56字节 = 14 REAL)

```
Offset | Field  | Type | 说明
-------|--------|------|--------------------
0      | U_0    | REAL | A相电压 (V)
4      | U_1    | REAL | B相电压 (V)
8      | U_2    | REAL | C相电压 (V)
12     | I_0    | REAL | A相电流 (A, 原始读数)
16     | I_1    | REAL | B相电流 (A, 原始读数)
20     | I_2    | REAL | C相电流 (A, 原始读数)
24     | Pt     | REAL | 总功率 (kW)
28     | Qt     | REAL | 总无功功率 (kVar)
32     | PF     | REAL | 功率因数
36     | Fr     | REAL | 频率 (Hz)
40     | ImpEp  | REAL | 累计有功电能 (kWh)
44     | ImpEq  | REAL | 累计无功电能 (kVarh)
48     | ExpEp  | REAL | 反向有功电能 (kWh)
52     | ExpEq  | REAL | 反向无功电能 (kVarh)
```

**注意**: CT变比=20，实际电流 = 读数 * 20

### DB30 状态数据 (40字节)

```
10个设备，每个4字节:
  - Byte 0-1: Modbus地址 (Word)
  - Byte 2: 状态字节 (Bit0=TxOK, Bit1=RxOK, Bit2=CommOK)
  - Byte 3: 保留
```

### Modbus RTU 料仓重量

```
寄存器: 40001-40002 (保持寄存器)
格式: 32位整数 (Big Endian)
单位: kg
```

---

## 与磨料车间项目对比

| 特性 | 电炉项目 | 磨料车间项目 |
|-----|---------|------------|
| **DB块数量** | 3个 (DB30/32/33) | 3个 (DB8/9/10) |
| **设备类型** | 电炉 + 料仓 | 料仓 + 辊道窑 + SCR |
| **特殊通信** | Modbus RTU (料仓重量) | 无 |
| **CT变比** | 20 (100A/5A) | 无电表 |
| **Mock服务器** | ✅ PLC + Modbus | ❌ 仅轮询服务 |
| **虚拟串口** | ✅ 支持 | ❌ 不适用 |

---

## 常见问题

### Q1: Mock PLC服务器无法启动？
**A**: 检查 `python-snap7` 是否正确安装:
```bash
pip install python-snap7
# Windows 还需下载 snap7.dll
```

### Q2: Mock Modbus服务器找不到串口？
**A**: 确认虚拟串口已创建:
- Windows: 使用 com0com，检查设备管理器
- Linux: 使用 socat，检查 `/dev/pts/` 目录

### Q3: 料仓重量为什么一直是0？
**A**: 检查Modbus通信是否正常:
1. Mock服务器是否在运行
2. 串口号是否匹配
3. 波特率是否正确 (19200-8-E-1)

### Q4: 如何调试Mock数据？
**A**: 使用测试脚本:
```bash
python tests/mock/test_data_variation.py
```

---

## 下一步优化

- [ ] 添加 WebSocket 实时推送
- [ ] 支持多个电炉设备模拟
- [ ] 增加异常场景模拟（断线、超时、错误数据）
- [ ] 集成到 CI/CD 自动化测试

---

**最后更新**: 2026-01-21
