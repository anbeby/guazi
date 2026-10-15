# MinIO 对象存储 —— Bucket 规划与使用约定

本目录只存放说明文档与（可选的）桶策略 JSON，**不存放任何对象实体**。
对象实体持久化在 Docker 具名卷 `gz_minio_data` 中，宿主机路径为
`/var/lib/docker/volumes/gz_minio_data/_data`。

- S3 API：容器内 `http://minio:9000`；宿主 `http://<host>:9000`
- 控制台：`http://<host>:9001`（账号见 `deploy/.env` 的 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`）
- 初始化：由一次性容器 `minio-init`（镜像 `minio/mc`）自动创建桶与策略，
  见 `deploy/docker-compose.yml`。失败可单独重跑：
  `docker compose run --rm minio-init`

---

## 1. Bucket 规划

| Bucket | 用途 | 典型对象路径 | 单文件上限 | 访问策略 |
| --- | --- | --- | --- | --- |
| `gz-product` | **商品图片**：商品主图、详情图、SKU 图 | `product/{enterprise_id}/{product_id}/{uuid}.jpg` | 10 MB | private（预签名 URL 下发） |
| `gz-report` | **检测报告**：质检报告、化验单、合格证（PDF/图片） | `report/{enterprise_id}/{product_id}/{yyyyMM}/{uuid}.pdf` | 50 MB | private |
| `gz-contract` | **合同附件**：园区入驻合同、交易合同、补充协议（PDF/扫描件） | `contract/{yyyy}/{contract_no}/{uuid}.pdf` | 100 MB | private |
| `gz-trace` | **溯源证据**：产地照片、加工过程影像、仓储/物流凭证 | `trace/{batch_no}/{stage}/{uuid}.jpg` | 20 MB | private（如需扫码公开可单独放开读） |

> `gz-product` 是平台默认桶（由 `.env` 的 `MINIO_BUCKET` 指定）；
> 其余三个桶由 `minio-init` 显式创建，`gz-trace`→`gz-report`→`gz-contract` 顺序无依赖。

## 2. 策略与安全

- **默认全部 private**：`minio-init` 执行 `mc anonymous set none`，禁止匿名访问。
- 前端展示图片/报告时，由 API 调 `get_presigned_url()` 生成**限时 URL**
  （建议 5~15 分钟），不要在数据库里存永久公网地址。
- 数据库表 `sys_file`（见 `docs/03-数据模型设计.md`）保存 `file_key / bucket /
  object_name / content_type / size / storage(minio|local)`，对象存储只存实体。
- 溯源公开页（`GET /api/v1/trace/public/{batch_no}`）如需直接展示图片，
  再单独执行：`mc anonymous set download local/gz-trace`；**不要**把
  `gz-contract` 设为匿名可读（含企业敏感信息）。

## 3. 命名与上传约定

- 对象名统一 `{biz_type}/{scope}/{yyyy}/{uuid}.{ext}`，禁止使用原始文件名
  （防中文乱码、防路径穿越、防同名覆盖）。
- 原始文件名记录在 `sys_file.original_name`，下载时通过
  `Content-Disposition: attachment; filename*=UTF-8''<encoded>` 还原。
- `biz_type ∈ product_image / test_report / contract_file / trace_evidence`，
  与桶一一对应，便于按前缀做生命周期与配额管理。
- 图片上传前在 API 侧做压缩与尺寸校验（主图 ≤ 1600px 长边），
  避免小程序端流量浪费。

## 4. 生命周期与容量

| Bucket | 版本控制 | 生命周期 | 容量估算（阶段一） |
| --- | --- | --- | --- |
| `gz-product` | 建议开启（防误删覆盖） | 无自动过期 | ≤ 50 GB |
| `gz-report` | 关闭 | 保留 5 年（合规要求） | ≤ 100 GB |
| `gz-contract` | 开启 | 保留 10 年 | ≤ 100 GB |
| `gz-trace` | 关闭 | 热数据 1 年后转冷/归档 | ≤ 200 GB |

阶段一单机 500 GB SSD 足够；超过 300 GB 时应规划独立对象存储节点
（MinIO 分布式模式：4 节点起步，纠删码保证 2 块盘容错）。

## 5. 常用运维命令

```bash
# 列出所有桶
docker compose exec minio-init mc ls local

# 查看桶内对象（递归）
docker compose exec minio-init mc ls --recursive local/gz-report

# 统计桶容量
docker compose exec minio-init mc du local/gz-product

# 备份某个桶到宿主目录（biz_type 级增量备份示例）
docker compose exec minio-init mc mirror local/gz-contract /backup/gz-contract

# 修改为匿名可读（谨慎，仅 gz-trace 场景）
docker compose exec minio-init mc anonymous set download local/gz-trace

# 回收匿名策略
docker compose exec minio-init mc anonymous set none local/gz-trace
```

## 6. 故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 上传报 `NoSuchBucket` | `minio-init` 未成功执行 | `docker compose run --rm minio-init`，再看 `mc ls local` |
| 上传报 `SignatureDoesNotMatch` | 预签名 URL 使用的 endpoint 与访问地址不一致 | 检查 `.env` 的 `MINIO_ENDPOINT`（容器内应为 `minio:9000`）与浏览器可达地址 |
| 预签名 URL 打开 404 | 对象名含中文/空格未编码 | 统一使用 UUID 对象名 |
| 控制台打不开 | 9001 未映射或防火墙拦截 | 检查 compose 的 `MINIO_CONSOLE_PORT` 与安全组 |
| 磁盘写满 | 检测报告/溯源影像累积 | 按上文生命周期归档，或扩容 `gz_minio_data` 所在分区 |
