# 家用控制台

English version: [README_EN.md](README_EN.md)

围绕局域网优化的个人网页应用管理平台，提供本地应用和轻量级命令行工具两种接口：

 - 本地的网页应用需要在一个专用端口跑，配置放到 `~/.config/home_command_center/apps/*.yaml`供识别。
 - 命令行工具则在这个repo每一个都专门写一个网页前端套壳。出于安全原因，家用命令台不会从用户配置里执行任意命令。

## 运行

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

启动控制台：

```bash
python3 server.py --host 127.0.0.1 --port 7000
```

打开：

```text
http://127.0.0.1:7000
```

本机就能测试使用了。

默认情况下，应用配置从下面读取，不同app可以有自己的配置参数：

```text
~/.config/home_command_center/apps/*.yaml
```

比如：

```yaml
type: command_tool
chinese_chars:
  output_dir: <home_command_center_output_dir>
```

开发测试时可以临时用另一个配置目录：

```bash
python3 server.py --apps-dir ./apps
```

## 网页应用配置

这部分是针对单独跑的完整网页应用。yaml文件放在 `~/.config/home_command_center/apps/` 里，每个应用都有自己的单独配置文件。由于端口在这里写定了，跑这个应用的时候要注意别用了错误端口。

```yaml
id: inspire
name: Inspire
url: "https://192.168.0.0:8001"
description: Inspiration browser
tags:
  - writing
  - local
health_url: "http://127.0.0.1:7001"
```

必填字段：

* `id`
* `name`
* `url`

可选字段：

* `description`
* `tags`
* `health_url`
* `health_verify_tls`

应用封面放在 YAML 文件旁边，并使用相同的文件名，例如 `inspire.yaml` 对应
`inspire.png`。旧的 `thumbnail` 配置字段仍然兼容，并在同名 PNG 不存在时使用。

`health_url` 只用于提取要探测的 host 和 port。家用命令台只检查这个端口是否在监听，不会发 HTTP 请求。这里要填本地后端端口，不是公开的 Caddy 端口。

`health_verify_tls` 只是为了兼容旧配置，但当前基于端口的健康检查不会用到它。

## 命令行工具

仓库内的命令行工具放在 `cli_tools/`，并在 `command_tools.py` 里注册。

控制台会把已注册的命令行工具和配置好的 Web 应用一起列出来。点击命令行工具会打开一个表单页，例如：

```text
/tools/slugify
```

前端会根据注册的 schema 限制字段。后端会再校验一遍同样的输入，组装 argv 列表，然后不通过 shell 直接运行注册脚本。

当前工具：

* `chinese-practice`：使用 `workbook_go` 生成可打印的中文练字 PDF
* `eat-what`：生成周菜单，或列出食谱
* `daka`：显示 `new_year_resolution_tracker` 里的所有新年愿望和任务，并支持按日期逐个打卡

`eat-what` 目前只暴露非交互式的 planner 和 recipe-list 模式。交互式的 `eat-what-recipe` 和 `eat-what-pick` 还没有封装。

`daka` 是 web-first：页面会加载完整的愿望树，带一个默认指向今天的日期选择器，每个任务都有自己的打卡按钮，页面还能生成任务或愿望汇总。重命名和新增仍留在原始 CLI 里。

添加命令行工具时：

* 在 `cli_tools/` 下面添加一个 CLI 脚本
* 在 `command_tools.py` 里注册它
* 用 `ToolArg` 定义每个接受的参数
* 保持 CLI 脚本非交互且有边界
* 如果工具会生成文件，就写到它自己的配置输出目录里

对于 `chinese-practice`，输出目录字段默认来自 `~/.config/home_command_center/apps/workbook_go.yaml` 里的 `chinese_chars.output_dir`。用户可以在表单里为单次运行覆盖这个目录。包装器不会给 `workbook_go` 传 PDF 文件名；它会切换到选定的输出目录，让 `workbook_go` 使用自己的默认文件名模式，例如 `practice_20260710.pdf`。

## 局域网 HTTPS

推荐做法：

* 安装 Caddy
* 安装 mkcert
* 为服务器 IP 生成本地证书
* 在家庭客户端设备上信任 mkcert 根证书
* 每个应用自己运行在 localhost
* 让 Caddy 通过 HTTPS 暴露仪表盘和各个应用

示例：

```bash
mkcert -install
mkcert 192.168.0.0
```

示例 Caddyfile：

```caddy
{
    auto_https off
}

https://192.168.0.0:8000 {
    bind 0.0.0.0
    tls /path/to/192.168.0.0.pem /path/to/192.168.0.0-key.pem
    reverse_proxy 127.0.0.1:7000
}

https://192.168.0.0:8001 {
    bind 0.0.0.0
    tls /path/to/192.168.0.0.pem /path/to/192.168.0.0-key.pem
    reverse_proxy 127.0.0.1:7001
}
```

格式化并运行 Caddy：

```bash
caddy fmt --overwrite Caddyfile
sudo caddy run --config Caddyfile
```

要在客户端设备上信任本地 CA：

```bash
mkcert -CAROOT
```

把 `rootCA.pem` 拷到每台客户端设备上。不要拷贝根 CA 的私钥文件。

## 外网 HTTPS

！这部分涉及网络安全，风险自担！

# 家用服务器远程访问

## 准备工作

### 公网 IP

家庭网络需要具备可从互联网访问的公网 IPv4 地址。若 ISP 提供的是 CGNAT，则无法直接建立入站连接，需要申请公网 IP 或采用其它方案。

### 固定内网地址

为服务器配置固定局域网 IP（推荐使用路由器 DHCP Reservation），避免端口转发和防火墙配置因 IP 变化而失效。

---

## 技术方案

### VPN（WireGuard）

仅开放一个公网 UDP 端口用于 WireGuard。

Remote Device
↓
Internet
↓
WireGuard VPN
↓
Home LAN
↓
Server / Web Apps

远程设备连接 VPN 后加入家庭局域网，直接通过内网地址访问所有服务，无需为每个 Web App 单独开放公网端口。

### Firewall（nftables）

采用默认拒绝（default deny）策略。

允许：

- 已建立连接
- WireGuard 端口
- VPN 虚拟网卡流量
- 局域网

拒绝：

- 其它所有公网入站连接

防火墙作为最后一道防线，即使路由器误配置了端口转发，也不会直接暴露内部服务。

# 新增设备

## 1. 生成密钥

进入客户端配置目录：

```bash
cd <wc_dir>

wg genkey | tee <device>.private | wg pubkey > <device>.public
```

---

## 2. 分配 VPN IP

为设备分配一个未使用的 VPN 地址，例如：

```text
10.100.0.3/32
```

---

## 3. 注册到服务器

编辑：

```text
/etc/wireguard/wg0.conf
```

追加：

```ini
[Peer]
PublicKey = <device>.public 内容
AllowedIPs = <设备 VPN IP>/32
```

重启 WireGuard：

```bash
sudo systemctl restart wg-quick@wg0
```

确认设备已注册：

```bash
sudo wg
```

---

## 4. 生成客户端配置

创建 `<device>.conf`：

```ini
[Interface]
PrivateKey = <device>.private 内容
Address = <设备 VPN IP>/32
DNS = <局域网网关>

[Peer]
PublicKey = <服务器 Public Key>
Endpoint = <公网 IP>:<WireGuard Port>
AllowedIPs = <局域网网段>,<VPN 网段>
PersistentKeepalive = 25
```

---

## 5. 导入客户端

移动端：

```bash
qrencode -o <device>.png < <device>.conf
```

使用 WireGuard App 扫描二维码导入。

桌面端可直接导入 `.conf` 文件。

---

## 6. 验证

连接 VPN 后，访问任意局域网服务即可。
