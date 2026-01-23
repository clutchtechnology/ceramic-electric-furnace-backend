# 1.1.0 版本部署指南

## 文件清单
- docker-compose.yml: 容器编排配置
- ceramic-backend-1.1.0.tar.gz: 后端镜像
- influxdb-2.7.tar.gz: InfluxDB 镜像
- README.md: 部署说明

## 工控机部署步骤
1. 将所有文件复制到工控机
2. 加载镜像: docker load < ceramic-backend-1.1.0.tar.gz
3. 加载镜像: docker load < influxdb-2.7.tar.gz
4. 启动服务: docker compose up -d
5. 检查健康: curl http://localhost:8082/api/health

## 版本信息
版本: 1.1.0
构建时间: 2026-01-21 18:44:32
