# #3电炉 - 逐步实施计划

## 📋 项目概览

**目标**: 将 Flutter App 复刻到 PyQt6，使用单进程多线程架构  
**预计时间**: 14天（2周）  
**完成进度**: 51/121 步骤 (42%) ✅

---

C:\Users\20216\Documents\GitHub\Clutch\
│
├── ceramic-electric-furnace-backend\          # 后端代码（现有项目）
│   │
│   ├── app\                                    # 业务逻辑层（保持不变）✅
│   │   ├── __pycache__\
│   │   ├── __init__.py
│   │   │
│   │   ├── core\                               # 核心模块
│   │   │   ├── __init__.py
│   │   │   ├── alarm_store.py                  # 报警存储（SQLite）
│   │   │   └── influxdb.py                     # InfluxDB 客户端
│   │   │
│   │   ├── models\                             # 数据模型
│   │   │   └── __init__.py
│   │   │
│   │   ├── plc\                                # PLC 通信层
│   │   │   ├── __init__.py
│   │   │   ├── plc_manager.py                  # PLC 连接管理器 ⭐
│   │   │   ├── parser_config_db1.py            # DB1 解析器（弧流弧压）⭐
│   │   │   ├── parser_config_db32.py           # DB32 解析器（传感器）⭐
│   │   │   ├── parser_modbus.py                # Modbus 解析器
│   │   │   ├── parser_status_db30.py           # DB30 状态解析器
│   │   │   ├── parser_status_db41.py           # DB41 状态解析器
│   │   │   ├── parser_status.py                # 通用状态解析器
│   │   │   └── plc_io_reader.py                # PLC IO 读取器
│   │   │
│   │   ├── services\                           # 业务服务层
│   │   │   ├── __init__.py
│   │   │   ├── batch_service.py                # 批次管理服务
│   │   │   ├── cooling_water_calculator.py     # 冷却水计算器
│   │   │   ├── feeding_accumulator.py          # 投料累计器
│   │   │   ├── feeding_calculator.py           # 投料计算器
│   │   │   ├── feeding_service.py              # 投料服务
│   │   │   ├── furnace_service.py              # 电炉服务
│   │   │   ├── polling_data_generator.py       # 轮询数据生成器（Mock）
│   │   │   ├── polling_data_processor.py       # 轮询数据处理器 ⭐
│   │   │   ├── polling_loops_v2.py             # 轮询循环（FastAPI 版本）
│   │   │   ├── polling_service.py              # 轮询服务
│   │   │   ├── power_energy_calculator.py      # 功率能耗计算器
│   │   │   ├── valve_calculator_service.py     # 阀门计算服务
│   │   │   └── valve_config_service.py         # 阀门配置服务
│   │   │
│   │   ├── tools\                              # 工具层（数据转换）
│   │   │   ├── __init__.py
│   │   │   ├── converter_elec_db1.py           # 弧流弧压转换器 ⭐
│   │   │   ├── converter_elec_db1_simple.py    # 简化版转换器
│   │   │   ├── converter_flow.py               # 流量转换器 ⭐
│   │   │   ├── converter_furnace.py            # 电炉综合转换器
│   │   │   ├── converter_length.py             # 长度转换器 ⭐
│   │   │   ├── converter_pressure.py           # 压力转换器 ⭐
│   │   │   ├── kalman_filter.py                # 卡尔曼滤波器
│   │   │   ├── operation_button.py             # 操作按钮工具
│   │   │   └── operation_modbus_weight_reader.py # Modbus 重量读取器 ⭐
│   │   │
│   │   └── routers\                            # FastAPI 路由（可选保留）
│   │       ├── __init__.py
│   │       ├── alarm.py                        # 报警路由
│   │       ├── api.py                          # API 路由
│   │       ├── batch.py                        # 批次路由
│   │       ├── control.py                      # 控制路由
│   │       ├── furnace.py                      # 电炉路由
│   │       ├── health.py                       # 健康检查路由
│   │       ├── history.py                      # 历史数据路由
│   │       ├── status.py                       # 状态路由
│   │       └── valve.py                        # 阀门路由
│   │
│   ├── configs\                                # 配置文件（保持不变）✅
│   │   ├── config_L3_P2_F2_C4_db32.yaml        # DB32 配置
│   │   ├── config_vw_data_db1.yaml             # DB1 配置
│   │   ├── db_mappings.yaml                    # DB 映射配置
│   │   ├── plc_modules.yaml                    # PLC 模块配置
│   │   ├── status_db41.yaml                    # DB41 状态配置
│   │   └── status_L3_P2_F2_C4_db30.yaml        # DB30 状态配置
│   │
│   ├── data\                                   # 数据文件
│   │   ├── batch_state.json                    # 批次状态
│   │   └── valve_config.json                   # 阀门配置
│   │
│   ├── frontend\                               # 新增：前后端桥接层 ⭐⭐⭐
│   │   ├── __init__.py
│   │   ├── data_bridge.py                      # 数据桥接器（Qt 信号）
│   │   └── data_cache.py                       # 缓存管理文件
│   │   └── data_models.py                      # 数据模型
│   │
│   ├── deploy\                                 # 部署文件
│   ├── docs\                                   # 文档
│   ├── scripts\                                # 脚本工具
│   ├── tests\                                  # 测试文件
│   ├── venv\                                   # 虚拟环境
│   │
│   ├── config.py                               # 配置文件（保持不变）✅
│   ├── main.py                                 # FastAPI 入口（可选保留）
│   ├── main_gui.py                             # 新增：PyQt6 GUI 入口 ⭐⭐⭐
│   ├── requirements.txt                        # Python 依赖
│   ├── ARCHITECTURE.md                         # 架构文档
│   ├── REFACTOR_PLAN.md                        # 重构计划
│   ├── SINGLE_PROCESS_IMPLEMENTATION_PLAN.md   # 单进程实施计划
│   └── PROJECT_STRUCTURE.md                    # 本文档 ⭐
│
│
└── ceramic-electric-furnace-pyqt\              # 新建：PyQt6 前端项目 ⭐⭐⭐
    │
    ├── main.py                                 # 应用入口（启动点）⭐⭐⭐
    ├── requirements.txt                        # PyQt6 依赖
    ├── config.py                               # 前端配置
    ├── README.md                               # 项目说明
    │
    ├── assets\                                 # 资源文件
    │   ├── images\                             # 图片资源
    │   │   ├── furnace.png                     # 电炉图片
    │   │   ├── dust_collector.png              # 除尘器图片
    │   │   └── waterpump.png                   # 水泵图片
    │   │
    │   ├── sounds\                             # 音频资源
    │   │   └── aviation-alarm.mp3              # 报警声音
    │   │
    │   └── fonts\                              # 字体资源
    │       └── RobotoMono-Regular.ttf          # 等宽字体
    │
    ├── ui\                                     # UI 层（复刻 Flutter）
    │   ├── __init__.py
    │   │
    │   ├── main_window.py                      # 主窗口（管理页面切换）⭐⭐⭐
    │   │
    │   ├── pages\                              # 页面层（复刻 Flutter pages/）
    │   │   ├── __init__.py
    │   │   ├── realtime_data_page.py           # 实时数据页面 ⭐⭐⭐
    │   │   ├── history_curve_page.py           # 历史曲线页面
    │   │   ├── alarm_record_page.py            # 报警记录页面
    │   │   ├── db30_status_page.py             # DB30 状态页面
    │   │   ├── db41_status_page.py             # DB41 状态页面
    │   │   ├── pump_room_status_page.py        # 泵房状态页面
    │   │   ├── status_page.py                  # 状态页面
    │   │   └── settings_page.py                # 设置页面
    │   │
    │   ├── widgets\                            # 组件层（复刻 Flutter widgets/）
    │   │   ├── __init__.py
    │   │   │
    │   │   ├── common\                         # 通用组件
    │   │   │   ├── __init__.py
    │   │   │   ├── tech_panel.py               # 科技风面板 ⭐⭐⭐
    │   │   │   ├── tech_button.py              # 科技风按钮
    │   │   │   ├── health_indicator.py         # 健康状态指示器
    │   │   │   ├── refresh_button.py           # 刷新按钮
    │   │   │   ├── export_button.py            # 导出按钮
    │   │   │   └── blinking_text.py            # 闪烁文本
    │   │   │
    │   │   ├── realtime_data\                  # 实时数据组件
    │   │   │   ├── __init__.py
    │   │   │   ├── data_card.py                # 数据卡片 ⭐⭐⭐
    │   │   │   ├── info_card.py                # 信息卡片
    │   │   │   ├── electrode_widget.py         # 电极组件 ⭐⭐⭐
    │   │   │   ├── electrode_chart.py          # 电极电流图表 ⭐⭐⭐
    │   │   │   ├── valve_indicator.py          # 阀门状态指示器 ⭐⭐⭐
    │   │   │   ├── valve_control.py            # 阀门控制组件
    │   │   │   └── smelting_button.py          # 冶炼控制按钮 ⭐⭐⭐
    │   │   │
    │   │   ├── history_curve\                  # 历史曲线组件
    │   │   │   ├── __init__.py
    │   │   │   ├── batch_selector.py           # 批次选择器
    │   │   │   ├── time_range_selector.py      # 时间范围选择器
    │   │   │   ├── quick_time_selector.py      # 快速时间选择器
    │   │   │   ├── tech_chart.py               # 科技风图表
    │   │   │   └── tech_bar_chart.py           # 科技风柱状图
    │   │   │
    │   │   └── shared\                         # 共享组件
    │   │       ├── __init__.py
    │   │       ├── custom_card.py              # 自定义卡片
    │   │       ├── data_table.py               # 数据表格
    │   │       └── tech_dropdown.py            # 科技风下拉框
    │   │
    │   └── styles\                             # 样式层（复刻 Flutter theme/）
    │       ├── __init__.py
    │       ├── colors.py                       # 颜色常量（TechColors）⭐⭐⭐
    │       ├── fonts.py                        # 字体配置
    │       └── qss_styles.py                   # QSS 样式表（类似 CSS）
    │
    ├── threads\                                # 后台线程层（复用后端逻辑）
    │   ├── __init__.py
    │   ├── plc_arc_thread.py                   # PLC 弧流轮询线程（0.2s）⭐⭐⭐
    │   ├── plc_sensor_thread.py                # PLC 传感器轮询线程（2s）⭐⭐⭐
    │   ├── influxdb_writer_thread.py           # InfluxDB 写入线程
    │   └── alarm_monitor_thread.py             # 报警监控线程
    │
    ├── models\                                 # 数据模型层
    │   ├── __init__.py
    │   ├── realtime_data.py                    # 实时数据模型
    │   ├── history_data.py                     # 历史数据模型
    │   ├── batch_data.py                       # 批次数据模型
    │   └── valve_status.py                     # 阀门状态模型
    │
    ├── utils\                                  # 工具函数层
    │   ├── __init__.py
    │   ├── logger.py                           # 日志工具
    │   ├── formatters.py                       # 数据格式化工具
    │   └── validators.py                       # 数据验证工具
    │
    └── logs\                                   # 日志文件目录
        └── app.log                             # 应用日志
## 🎯 实施进度总览

| 阶段 | 进度 | 预计时间 | 优先级 |
|------|------|----------|--------|
| [阶段 1: 环境准备](#阶段-1-环境准备1天) | 10/10 ✅ | 1天 | ✅ 已完成 |
| [阶段 2: 后端桥接层](#阶段-2-后端桥接层1天) | 13/13 ✅ | 1天 | ✅ 已完成 |
| [阶段 3: 样式系统](#阶段-3-样式系统1天) | 12/12 ✅ | 1天 | ✅ 已完成 |
| [阶段 4: 基础窗口功能](#阶段-4-基础窗口功能05天) | 8/8 ✅ | 0.5天 | ✅ 已完成 |
| [阶段 4.5: 顶部导航栏](#阶段-45-顶部导航栏05天) | 8/8 ✅ | 0.5天 | ✅ 已完成 |
| [阶段 5: 核心UI组件](#阶段-5-核心ui组件2天) | 0/20 | 2天 | 🔥 **下一步** |
| [阶段 6: 实时数据页面UI](#阶段-6-实时数据页面ui2天) | 0/15 | 2天 | 🔥 **优先** |
| [阶段 7: 其他页面UI](#阶段-7-其他页面ui15天) | 0/12 | 1.5天 | 🔥 **优先** |
| [阶段 8: 后台线程集成](#阶段-8-后台线程集成2天) | 0/15 | 2天 | ⏳ 后续 |
| [阶段 9: 功能完善](#阶段-9-功能完善2天) | 0/10 | 2天 | ⏳ 后续 |
| [阶段 10: 测试优化](#阶段-10-测试优化2天) | 0/8 | 2天 | ⏳ 后续 |
| **总计** | **51/121** | **14.5天** | - |

---

## 阶段 1: 环境准备（1天）✅ 已完成

### 1.1 创建项目目录结构

- [x] 1.1.1 创建前端项目根目录 `ceramic-electric-furnace-pyqt` ✅
- [x] 1.1.2 创建 `ui` 目录及子目录（pages, widgets, styles） ✅
- [x] 1.1.3 创建 `threads` 目录 ✅
- [x] 1.1.4 创建 `models` 目录 ✅
- [x] 1.1.5 创建 `utils` 目录 ✅
- [x] 1.1.6 创建 `assets` 目录（images, sounds, fonts） ✅
- [x] 1.1.7 创建后端 `frontend` 目录（桥接层） ✅

### 1.2 创建配置文件

- [x] 1.2.1 创建 `requirements.txt`（PyQt6 依赖） ✅
- [x] 1.2.2 创建 `config.py`（前端配置） ✅
- [x] 1.2.3 创建 `README.md`（项目说明） ✅

**验收标准**: 目录结构完整，配置文件已创建 ✅

**完成时间**: 2026-01-27

---

## 阶段 2: 后端桥接层（1天）✅ 已完成

### 2.1 数据桥接器

- [x] 2.1.1 创建 `backend/frontend/__init__.py` ✅
- [x] 2.1.2 创建 `backend/frontend/data_bridge.py` ✅
- [x] 2.1.3 实现 `DataBridge` 类（单例模式） ✅
- [x] 2.1.4 定义 Qt 信号（arc_data_updated, sensor_data_updated） ✅
- [x] 2.1.5 实现数据发送方法（emit_arc_data, emit_sensor_data） ✅

### 2.2 数据缓存管理器 ⭐ 新增

- [x] 2.2.1 创建 `backend/frontend/data_cache.py` ✅
- [x] 2.2.2 实现 `DataCache` 类（单例模式） ✅
- [x] 2.2.3 实现线程安全的读写方法（使用 Lock） ✅
- [x] 2.2.4 实现历史数据存储（使用 deque，保留最近 1000 条） ✅
- [x] 2.2.5 创建 `backend/frontend/data_models.py`（数据模型定义） ✅

### 2.3 GUI 入口

- [x] 2.3.1 创建 `backend/main_gui.py` ✅
- [x] 2.3.2 实现应用启动逻辑 ✅
- [x] 2.3.3 测试后端模块导入 ✅

**验收标准**: 可以从 PyQt6 导入后端模块，信号正常工作，缓存管理器线程安全 ✅

**完成时间**: 2026-01-27

**说明**: 
- `app/models/` 目录保留，用于 FastAPI 数据模型
- `frontend/data_models.py` 用于前端数据结构，两者用途不同
- 缓存管理器测试通过，所有功能正常

---

## 阶段 3: 样式系统（1天）✅ 已完成

### 3.1 颜色常量

- [x] 3.1.1 创建 `ui/styles/__init__.py` ✅
- [x] 3.1.2 创建 `ui/styles/colors.py` ✅
- [x] 3.1.3 定义 `DarkColors` 类（深色主题）✅
- [x] 3.1.4 定义 `LightColors` 类（浅色主题）✅

### 3.2 主题管理器

- [x] 3.2.1 创建 `ui/styles/themes.py` ✅
- [x] 3.2.2 实现 `ThemeManager` 类（单例模式）✅
- [x] 3.2.3 实现主题切换功能 ✅
- [x] 3.2.4 实现颜色访问接口 ✅

### 3.3 QSS 样式表

- [x] 3.3.1 创建 `ui/styles/qss_styles.py` ✅
- [x] 3.3.2 实现全局样式、按钮、面板、输入框等样式 ✅

### 3.4 字体配置

- [x] 3.4.1 创建 `ui/styles/fonts.py` ✅
- [x] 3.4.2 实现 `FontManager` 类 ✅

### 3.5 主题切换组件

- [x] 3.5.1 创建 `ui/widgets/common/theme_switch.py` ✅
- [x] 3.5.2 创建主题预览 HTML ✅

**验收标准**: 支持深色/浅色主题切换，颜色系统完整，QSS 样式正常加载 ✅

**完成时间**: 2026-01-27

**说明**: 
- 深色主题：科技风格（青色发光边框 #00d4ff）
- 浅色主题：绿色系（基于 #E9EEA8，深绿强调色 #007663）
- 支持主题实时切换
- 提供完整的 QSS 样式库

---

## 阶段 4: 基础窗口功能（0.5天）✅ 已完成

### 4.1 主窗口基础功能

- [x] 4.1.1 创建 `ui/__init__.py` ✅
- [x] 4.1.2 创建 `ui/main_window.py` ✅
- [x] 4.1.3 实现 `MainWindow` 类（继承 QMainWindow）✅
- [x] 4.1.4 实现全屏模式（showFullScreen）✅
- [x] 4.1.5 实现最小化功能（showMinimized）✅
- [x] 4.1.6 实现退出快捷键（Esc 或 Alt+F4）✅
- [x] 4.1.7 创建简单的测试页面（显示"Hello PyQt6"）✅
- [x] 4.1.8 在 `main.py` 中启动主窗口 ✅

**验收标准**: 
- ✅ 窗口能全屏显示
- ✅ 窗口能最小化
- ✅ 能正常退出应用
- ✅ 应用主题样式正常加载

**完成时间**: 2026-01-28

**说明**:
- 主窗口默认全屏启动
- 支持 F11 切换全屏/窗口模式
- 集成主题切换功能
- 使用 QStackedWidget 实现页面管理
- 修复了 PyQt6 6.10.2 兼容性问题
- 修复了模块导入优先级问题

---

## 阶段 4.5: 顶部导航栏（0.5天）✅ 已完成

### 4.5.1 创建导航栏目录结构

- [x] 4.5.1.1 创建 `ui/bar/` 目录 ✅
- [x] 4.5.1.2 创建 `ui/bar/__init__.py` ✅
- [x] 4.5.1.3 创建 `ui/icons/` 目录（存放图标资源）✅
- [x] 4.5.1.4 创建 `ui/icons/__init__.py` ✅

### 4.5.2 实现顶部导航栏组件

- [x] 4.5.2.1 创建 `ui/bar/top_nav_bar.py` ✅
- [x] 4.5.2.2 实现 `TopNavBar` 类（继承 QFrame）✅
- [x] 4.5.2.3 实现 Logo 和标题（带发光效果）✅
- [x] 4.5.2.4 实现导航按钮（3# 电炉、历史数据、状态监控）✅
- [x] 4.5.2.5 实现时钟显示（实时更新）✅
- [x] 4.5.2.6 实现设置按钮（SVG 图标，点击变亮）✅
- [x] 4.5.2.7 实现主题切换按钮集成 ✅
- [x] 4.5.2.8 实现窗口控制按钮（最小化、全屏、退出）✅

### 4.5.3 集成到主窗口

- [x] 4.5.3.1 修改 `ui/main_window.py`，集成导航栏 ✅
- [x] 4.5.3.2 实现页面切换逻辑（4个页面：3# 电炉、历史数据、状态监控、系统设置）✅
- [x] 4.5.3.3 创建占位页面（显示页面标题和说明）✅
- [x] 4.5.3.4 实现导航信号连接 ✅

### 4.5.4 科技风格样式

- [x] 4.5.4.1 实现细亮边框效果（1px 边框）✅
- [x] 4.5.4.2 实现选中状态（青色发光边框 + 半透明背景）✅
- [x] 4.5.4.3 实现悬停效果（边框高亮）✅
- [x] 4.5.4.4 实现 SVG 图标颜色动态切换（激活时变亮）✅

**验收标准**: 
- ✅ 导航栏显示正常，科技风格完整
- ✅ 导航按钮点击切换页面正常
- ✅ 设置按钮使用 SVG 图标，无边框，点击后图标变亮
- ✅ 时钟实时更新
- ✅ 主题切换功能正常
- ✅ 窗口控制功能正常

**完成时间**: 2026-01-28

**说明**:
- 导航栏采用科技风格设计，所有按钮都有细亮边框（1px）
- 设置按钮使用 SVG 图标（齿轮），无边框设计，只有图标本身
- 点击设置按钮进入设置页面时，图标颜色从次要文字色变为青色发光色
- 时钟使用 QTimer 每秒更新一次
- 支持 4 个页面切换：3# 电炉（index 0）、历史数据（index 1）、状态监控（index 2）、系统设置（index 3）
- 导航栏高度 60px，使用渐变背景和发光边框
- 修复了 `ui/styles/__init__.py` 中删除 fonts.py 后的导入错误

---

## 阶段 5: 核心UI组件（2天）🔥 下一步

### 5.1 科技风面板

- [ ] 5.1.1 创建 `ui/widgets/common/__init__.py`
- [ ] 5.1.2 创建 `ui/widgets/common/tech_panel.py`
- [ ] 5.1.3 实现 `TechPanel` 类（继承 QFrame）
- [ ] 5.1.4 实现边框发光效果
- [ ] 5.1.5 实现标题栏
- [ ] 5.1.6 实现内容区域

### 5.2 数据卡片

- [ ] 5.2.1 创建 `ui/widgets/realtime_data/__init__.py`
- [ ] 5.2.2 创建 `ui/widgets/realtime_data/data_card.py`
- [ ] 5.2.3 实现 `DataCard` 类
- [ ] 5.2.4 实现数据项布局（图标 + 标签 + 数值 + 单位）
- [ ] 5.2.5 实现报警状态显示（使用模拟数据）

### 5.3 电极组件

- [ ] 5.3.1 创建 `ui/widgets/realtime_data/electrode_widget.py`
- [ ] 5.3.2 实现 `ElectrodeWidget` 类
- [ ] 5.3.3 实现深度显示（使用模拟数据）
- [ ] 5.3.4 实现弧流显示（使用模拟数据）
- [ ] 5.3.5 实现弧压显示（使用模拟数据）
- [ ] 5.3.6 实现报警状态（深度报警 + 电流报警）

### 5.4 电极电流图表

- [ ] 5.4.1 创建 `ui/widgets/realtime_data/electrode_chart.py`
- [ ] 5.4.2 实现 `ElectrodeChart` 类（使用 PyQtGraph）
- [ ] 5.4.3 实现梯形图布局
- [ ] 5.4.4 实现设定值显示（使用模拟数据）
- [ ] 5.4.5 实现实际值显示（使用模拟数据）
- [ ] 5.4.6 实现死区显示

### 5.5 阀门指示器

- [ ] 5.5.1 创建 `ui/widgets/realtime_data/valve_indicator.py`
- [ ] 5.5.2 实现 `ValveIndicator` 类
- [ ] 5.5.3 实现阀门状态显示（开/关/停，使用模拟数据）
- [ ] 5.5.4 实现开度百分比显示（使用模拟数据）

**验收标准**: 
- ✅ 所有组件样式与 Flutter 主题预览一致
- ✅ 组件能显示模拟数据
- ✅ 组件布局美观，响应式设计

**完成时间**: 预计 2 天

---

## 阶段 6: 实时数据页面UI（2天）🔥 优先

### 6.1 实时数据页面布局

- [ ] 6.1.1 创建 `ui/pages/__init__.py`
- [ ] 6.1.2 创建 `ui/pages/realtime_data_page.py`
- [ ] 6.1.3 实现 `RealtimeDataPage` 类
- [ ] 6.1.4 实现整体布局（使用 QGridLayout）
- [ ] 6.1.5 添加电炉图片（居中）
- [ ] 6.1.6 添加电极组件（3个，覆盖在图片上）

### 6.2 集成组件（使用模拟数据）

- [ ] 6.2.1 添加蝶阀状态面板（左上角）
- [ ] 6.2.2 添加除尘器面板（右上角）
- [ ] 6.2.3 添加电极电流图表（左下角）
- [ ] 6.2.4 添加冷却水面板（底部）
- [ ] 6.2.5 添加料仓重量面板（左下角）
- [ ] 6.2.6 添加冶炼控制按钮（顶部）

### 6.3 页面切换功能

- [ ] 6.3.1 在主窗口实现页面切换（QStackedWidget）
- [ ] 6.3.2 添加导航栏或侧边栏
- [ ] 6.3.3 实现页面切换动画（可选）

**验收标准**: 
- ✅ 页面布局与 Flutter 版本一致
- ✅ 所有组件正常显示模拟数据
- ✅ 页面切换流畅

**完成时间**: 预计 2 天

---

## 阶段 7: 其他页面UI（1.5天）🔥 优先

### 7.1 历史曲线页面

- [ ] 7.1.1 创建 `ui/pages/history_curve_page.py`
- [ ] 7.1.2 实现页面布局
- [ ] 7.1.3 实现时间选择器（UI组件）
- [ ] 7.1.4 实现批次选择器（UI组件）
- [ ] 7.1.5 实现图表显示（PyQtGraph，使用模拟数据）

### 7.2 报警记录页面

- [ ] 7.2.1 创建 `ui/pages/alarm_record_page.py`
- [ ] 7.2.2 实现页面布局
- [ ] 7.2.3 实现报警列表（QTableWidget，使用模拟数据）

### 7.3 状态页面

- [ ] 7.3.1 创建 `ui/pages/status_page.py`
- [ ] 7.3.2 实现 DB30 状态显示（使用模拟数据）
- [ ] 7.3.3 实现 DB41 状态显示（使用模拟数据）

### 7.4 设置页面

- [ ] 7.4.1 创建 `ui/pages/settings_page.py`
- [ ] 7.4.2 实现设置项布局
- [ ] 7.4.3 实现主题切换功能集成

**验收标准**: 
- ✅ 所有页面UI完整
- ✅ 页面能正常切换
- ✅ 使用模拟数据展示功能

**完成时间**: 预计 1.5 天

---

## 阶段 8: 后台线程集成（2天）⏳ 后续

### 8.1 PLC 弧流轮询线程

- [ ] 8.1.1 创建 `threads/__init__.py`
- [ ] 8.1.2 创建 `threads/plc_arc_thread.py`
- [ ] 8.1.3 实现 `PLCArcThread` 类（继承 QThread）
- [ ] 8.1.4 导入后端模块（plc_manager, parser_db1, converter）
- [ ] 8.1.5 实现 `run()` 方法（0.2s 轮询）
- [ ] 8.1.6 实现数据读取逻辑
- [ ] 8.1.7 实现数据解析逻辑
- [ ] 8.1.8 实现信号发送逻辑

### 8.2 PLC 传感器轮询线程

- [ ] 8.2.1 创建 `threads/plc_sensor_thread.py`
- [ ] 8.2.2 实现 `PLCSensorThread` 类
- [ ] 8.2.3 导入后端模块（parser_db32, converter）
- [ ] 8.2.4 实现 `run()` 方法（2s 轮询）
- [ ] 8.2.5 实现传感器数据读取
- [ ] 8.2.6 实现料仓重量读取（Modbus）
- [ ] 8.2.7 实现信号发送逻辑

**验收标准**: 
- ✅ 弧流数据 0.2s 更新
- ✅ 传感器数据 2s 更新
- ✅ 无数据丢失

**完成时间**: 预计 2 天

---

## 阶段 9: 功能完善（2天）⏳ 后续

### 9.1 连接信号槽

- [ ] 9.1.1 在主窗口启动后台线程
- [ ] 9.1.2 连接弧流数据信号到UI组件
- [ ] 9.1.3 连接传感器数据信号到UI组件
- [ ] 9.1.4 实现数据更新方法

### 9.2 InfluxDB 集成

- [ ] 9.2.1 创建 `threads/influxdb_writer_thread.py`
- [ ] 9.2.2 实现数据写入逻辑
- [ ] 9.2.3 实现历史数据查询

### 9.3 报警功能

- [ ] 9.3.1 创建 `threads/alarm_monitor_thread.py`
- [ ] 9.3.2 实现报警检测逻辑
- [ ] 9.3.3 实现报警声音播放

### 9.4 控制功能

- [ ] 9.4.1 实现冶炼控制功能
- [ ] 9.4.2 实现阀门控制功能
- [ ] 9.4.3 实现PLC写入功能

**验收标准**: 
- ✅ 所有功能正常工作
- ✅ 数据实时更新
- ✅ 报警功能正常

**完成时间**: 预计 2 天

---

## 阶段 10: 测试优化（2天）⏳ 后续

### 10.1 功能测试

- [ ] 10.1.1 测试弧流数据刷新（0.2s）
- [ ] 10.1.2 测试传感器数据刷新（2s）
- [ ] 10.1.3 测试报警声音播放
- [ ] 10.1.4 测试冶炼控制功能
- [ ] 10.1.5 测试历史数据查询

### 10.2 性能测试

- [ ] 10.2.1 测试内存占用（< 150MB）
- [ ] 10.2.2 测试 CPU 占用（< 5%）
- [ ] 10.2.3 测试数据延迟（< 1ms）

### 10.3 打包部署

- [ ] 10.3.1 安装 PyInstaller
- [ ] 10.3.2 配置打包脚本
- [ ] 10.3.3 打包为 exe
- [ ] 10.3.4 测试 exe 运行
- [ ] 10.3.5 编写部署文档

**验收标准**: 
- ✅ 所有测试通过
- ✅ exe 正常运行

**完成时间**: 预计 2 天

---

## 📝 使用说明

### 如何标记完成

每完成一个步骤，将 `- [ ]` 改为 `- [x]`：

```markdown
- [x] 1.1.1 创建前端项目根目录 `ceramic-electric-furnace-pyqt`  ✅ 已完成
```

### 进度计算

```
总进度 = 已完成步骤数 / 100
```

### 每日更新

建议每天结束时更新进度，并记录遇到的问题。

---

## 🎯 里程碑

| 里程碑 | 完成条件 | 预计日期 | 状态 |
|--------|----------|----------|------|
| M1: 环境就绪 | 阶段 1-3 完成 | 第3天 | ✅ 已完成 |
| M2: 基础窗口功能 | 阶段 4 完成 | 第3.5天 | ✅ 已完成 |
| M2.5: 顶部导航栏完成 | 阶段 4.5 完成 | 第4天 | ✅ 已完成 |
| M3: 核心UI组件完成 | 阶段 5 完成 | 第6天 | 🔥 **下一步** |
| M4: 实时页面UI完成 | 阶段 6 完成 | 第8天 | ⏳ 待开始 |
| M5: 所有页面UI完成 | 阶段 7 完成 | 第9.5天 | ⏳ 待开始 |
| M6: 后台线程集成 | 阶段 8 完成 | 第11.5天 | ⏳ 待开始 |
| M7: 功能完善 | 阶段 9 完成 | 第13.5天 | ⏳ 待开始 |
| M8: 项目交付 | 阶段 10 完成 | 第15.5天 | ⏳ 待开始 |

---

## 📌 开发策略说明

### 🎨 UI优先策略

本项目采用 **UI优先** 的开发策略：

1. **阶段 4-7（UI开发）**: 
   - 先实现所有UI界面和组件
   - 使用模拟数据展示功能
   - 确保PyQt6能够支持全屏、最小化等基础窗口功能 ✅
   - 验证样式主题在实际组件中的效果

2. **阶段 8-9（功能集成）**:
   - UI完成后再集成后台线程
   - 连接真实的PLC数据
   - 实现数据库和报警功能

3. **优势**:
   - ✅ 快速验证PyQt6的可行性 ✅ 已验证
   - ✅ 提前发现UI布局问题
   - ✅ 前后端分离，降低复杂度
   - ✅ 可以先展示UI效果给用户确认

---

**维护者**: Clutch Team  
**创建日期**: 2026-01-27  
**最后更新**: 2026-01-28  
**当前进度**: 51/121 (42%) ✅  
**下一步**: 🔥 实现核心UI组件（科技风面板、数据卡片等）

---

## 📝 更新日志

### 2026-01-28
- ✅ 完成阶段 4.5：顶部导航栏
  - 创建 `ui/bar/` 目录和导航栏组件
  - 实现科技风格导航栏（Logo、导航按钮、时钟、设置按钮、主题切换、窗口控制）
  - 实现 SVG 图标支持（设置按钮使用齿轮图标，点击后变亮）
  - 实现 4 个页面切换（3# 电炉、历史数据、状态监控、系统设置）
  - 修复 `ui/styles/__init__.py` 导入错误
  - 进度：51/121 (42%)

### 2026-01-27
- ✅ 完成阶段 1-4：环境准备、后端桥接层、样式系统、基础窗口功能
  - 进度：43/113 (38%)
