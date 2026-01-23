# 电炉后端 v1.1.4 发布说明

## 更新日志

1.  **修复 DB41 轮询问题**:
    *   暂时屏蔽 DB41 状态读取，防止 "Address out of range" 错误导致整个轮询服务异常。
    *   前端查询 DB41 状态时将返回空数据，而不是报错。

2.  **手动轮询控制优化**:
    *   前端 Flutter App "开始实时数据" 按钮现在会正确调用 `/api/control/start` 接口。
    *   后端接收请求后才会建立 PLC 连接，避免服务启动即连接，提高系统稳定性。

## 部署步骤

1.  构建镜像:
    ```powershell
    docker build -t furnace-backend:1.1.4 .
    ```

2.  运行服务:
    ```powershell
    cd deploy/1.1.4
    docker compose up -d
    ```
