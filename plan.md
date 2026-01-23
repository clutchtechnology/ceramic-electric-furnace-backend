1,我需要就是完善我的对于批次的逻辑的实现 ✅ 已完成
   - SM: 主动开始冶炼 (前端点击按钮)
   - SX: 被动创建 (轮询时无批次号自动创建)
   - 所有数据点添加 batch_code tag
   - API: POST /smelting/start, POST /smelting/stop, GET /smelting/batch
2,完善对于解析相关代码文件的修改(后续需要修改) ✅ 已完成: 新增 parser_config_db32.py 和 parser_status_db30.py 配置驱动解析器
3,完善对于我的计算相关逻辑代码的实现(后续还需要修改) 
4,激光测距的计算 1 
5,modbus_rtu读取料仓的重量的单独服务的实现 1 
6,四路蝶阀的开关问题TODO:
7,流量计和压力计的计算代码 1 
8,电表的 解析计算代码文件 
9, 轮询服务将数据点存数据库中 ✅ 已完成
   - DB30: 通信状态 (仅缓存)
   - DB32: 3电极深度 + 2压力 + 2流量 + 4蝶阀开关状态 = 11 Point
   - DB33: 1电表 三电流和电压
   - Modbus RTU: 1料仓净重 = 1 Point
   - 合计: 13 Point/轮询, 每10轮询批量写入

10,完善批次编号实现,每次都会带上编号
11,完善前端对于健康状态的显示的逻辑完善
12,对于我的实时数据大屏的实现(缺乏投料重量,累计用水,前置过滤器进出口压差)
13,完善我的 历史数据的某些联调 
14,然后我需要完善我的实际的db的修改和前端的联调


15,docker安装
16,前后端部署
17,联调测试





4,完善对于轮询和存缓存以及写入数据库的逻辑的实现 ✅ 已完成: polling_service 已集成 Mock/PLC 轮询 + InfluxDB 批量写入
5,完善前端对于除了料仓除尘器以外的其他部分的接入后端的api实现
6,完善对于我的报警记录的实现

---
## 已完成记录
- [x] 后端 /api/furnace/realtime 输出 3红外+2压力+2流量+4蝶阀实时数据
- [x] 新增配置驱动解析器 (parser_config_db32.py, parser_status_db30.py)
- [x] plc_manager 补充 health_check(), reset_plc_manager() 方法
- [x] furnace_service 改造为直接读取轮询缓存数据

### 2026-01-22 弧流弧压单位修改 (kA → A)
- [x] 新增 `app/tools/converter_elec_db1.py` - DB1 弧流弧压转换器
  - 弧流目标值: 5978 A (梯形图 2989 × 2)
  - 弧压目标值: 80 V (范围 70-90 V)
  - 校准逻辑: 若原始值在有效范围内直接使用，否则乘以校准系数
- [x] 更新 `app/services/polling_service.py`
  - 集成 converter_elec_db1 转换逻辑
  - Mock 数据生成目标: 5978 A ±10%, 80 V ±10 V
  - 添加 DB1 轮询读取逻辑
- [x] 更新 `app/routers/furnace.py`
  - API 返回字段: `current_kA` → `current_A`
- [x] 更新前端 `lib/models/realtime_data.dart`
  - 字段: `currentKA` → `currentA`
- [x] 更新前端 `lib/pages/realtime_data_page.dart`
  - 电极显示直接使用 `currentA`（无需 ×1000）
  - setValue 设为 5978
- [x] 更新前端 `lib/providers/realtime_config_provider.dart`
  - 电极阈值配置: setValueA=5978, lowAlarmA=5081.3 (85%), highAlarmA=6874.7 (115%)
  - 方法参数: `valueKA` → `valueA`
- [x] 更新前端 `lib/widgets/realtime_data/electrode_current_chart.dart`
  - Y轴标签: `电流 (kA)` → `电流 (A)`
  - 数值格式: `toStringAsFixed(2)` → `toStringAsFixed(0)` (整数显示)

## 部署提示
- 后端生产模式: enable_polling=true, enable_mock_polling=false
- 前端调用: /api/furnace/realtime 取 electrode_depths/cooling_pressures/cooling_flows/valve_controls

