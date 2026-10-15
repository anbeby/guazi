# -*- coding: utf-8 -*-
# =============================================================================
# 第十师瓜子油料数字化交易平台 —— 企业侧 Odoo 17 镜像
# -----------------------------------------------------------------------------
# 构建（在 I:\瓜子\odoo 目录下执行）：
#   docker build -t gz-odoo:17.0 .
#
# 运行（示例，数据库与挂载按部署环境调整）：
#   docker run -d --name gz-odoo -p 8069:8069 -p 8072:8072 \
#     -e HOST=<pg-host> -e PORT=5432 -e USER=odoo -e PASSWORD=<pg-pwd> \
#     -v gz_odoo_data:/var/lib/odoo \
#     -v /srv/gz/odoo-conf:/etc/odoo \
#     gz-odoo:17.0
#
# 说明：
#   * 基础镜像 odoo:17.0 的 ENTRYPOINT 为 /entrypoint.sh、CMD 为 odoo，本文件不做覆盖；
#     entrypoint 会读取 /etc/odoo/odoo.conf（$ODOO_RC）并把 db_host/db_port/db_user/db_password
#     以命令行参数形式传给 odoo。
#   * 自研模块全部落在 /mnt/extra-addons（"自研模块目录"），不修改官方 addons。
# =============================================================================
FROM odoo:17.0

# 镜像内构建阶段需要写 /mnt/extra-addons、/etc/odoo，显式声明 root
USER root

# -----------------------------------------------------------------------------
# 1. Python 依赖
#    odoo:17.0 基于 Debian，系统 Python 可能启用 PEP 668（externally-managed-environment），
#    因此先按常规安装，失败时再追加 --break-system-packages 重试，保证两种基础镜像都能构建。
# -----------------------------------------------------------------------------
COPY requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip \
 && (python3 -m pip install --no-cache-dir -r /tmp/requirements.txt \
     || python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt) \
 && rm -f /tmp/requirements.txt

# -----------------------------------------------------------------------------
# 2. 自研模块（gz_*）复制到 extra-addons
# -----------------------------------------------------------------------------
COPY addons/ /mnt/extra-addons/

# -----------------------------------------------------------------------------
# 3. 配置目录与挂载点
#    /etc/odoo        配置（可挂载）
#    /mnt/extra-addons 自研模块（可挂载覆盖）
#    /var/lib/odoo    数据（filestore / sessions，可挂载）
#    仅在配置文件不存在时生成，避免覆盖运维通过挂载提供的配置。
# -----------------------------------------------------------------------------
RUN mkdir -p /etc/odoo /mnt/extra-addons /var/lib/odoo \
 && if [ ! -f /etc/odoo/odoo.conf ]; then \
        printf '%s\n' \
            '[options]' \
            'addons_path = /mnt/extra-addons' \
            'data_dir = /var/lib/odoo' \
            '; --- 平台集成参数（也可由 ir.config_parameter 覆盖） ---' \
            '; gz_platform_api_base_url = https://gz-platform.example.com' \
            '; gz_platform_api_token = <INTEGRATION_TOKEN>' \
            > /etc/odoo/odoo.conf; \
    fi \
 && chown -R odoo:odoo /etc/odoo /mnt/extra-addons /var/lib/odoo \
 && chmod 640 /etc/odoo/odoo.conf \
 && find /mnt/extra-addons -type d -exec chmod 755 {} + \
 && find /mnt/extra-addons -type f -exec chmod 644 {} +

VOLUME ["/var/lib/odoo", "/mnt/extra-addons", "/etc/odoo"]

# Odoo 主服务端口与长轮询（websocket）端口
EXPOSE 8069 8072

# 与官方镜像保持一致：以 odoo 非特权用户运行
USER odoo

# 官方 entrypoint / CMD（保持官方行为：entrypoint.sh 负责等待数据库并注入 db_* 参数）
ENTRYPOINT ["/entrypoint.sh"]
CMD ["odoo"]
