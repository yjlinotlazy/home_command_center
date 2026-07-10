# 家用命令台

English version: [README_EN.md](README_EN.md)

家用命令台是一个家庭内部的仪表盘，用来管理同一可信局域网里的本地 Web 应用和仓库内的命令行工具。

它不会启动、停止或托管外部服务。Web 应用由你自己运行，通过局域网 HTTPS 暴露出来，并写进 `~/.config/home_command_center/apps/*.yaml`。

命令行工具不一样：它们是本仓库里的小型 CLI 脚本，通过受控的 Web 表单暴露出来。家用命令台不会从用户配置里执行任意命令。

Web 界面提供中英文切换，下拉框在页面顶部。

## 运行

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

启动仪表盘：

```bash
python3 server.py --host 127.0.0.1 --port 7000
```

打开：

```text
http://127.0.0.1:7000
```

家庭设备上建议通过 Caddy 用 HTTPS 访问这个仪表盘。

默认情况下，应用配置从下面读取：

```text
~/.config/home_command_center/apps/*.yaml
```

工作簿工具的单独配置在：

```text
~/.config/home_command_center/apps/workbook_go.yaml
```

当前工作簿配置示例：

```yaml
type: command_tool
chinese_chars:
  output_dir: <home_command_center_output_dir>
```

开发时可以指向另一个配置目录：

```bash
python3 server.py --apps-dir ./apps
```

## 应用配置

在 `~/.config/home_command_center/apps/` 里为每个应用创建一个 YAML 文件。

```yaml
id: inspire
name: Inspire
url: "https://192.168.0.0:8001"
thumbnail: ./thumb.png
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

* `thumbnail`
* `description`
* `tags`
* `health_url`
* `health_verify_tls`

`thumbnail` 路径会相对 YAML 文件解析。

`health_url` 只用于提取要探测的 host 和 port。家用命令台只检查这个端口是否在监听，不会发 HTTP 请求。这里要填本地后端端口，不是公开的 Caddy 端口。

`health_verify_tls` 只是为了兼容旧配置，但当前基于端口的健康检查不会用到它。

## 命令行工具

仓库内的命令行工具放在 `cli_tools/`，并在 `command_tools.py` 里注册。

仪表盘会把已注册的命令行工具和配置好的 Web 应用一起列出来。点击命令行工具会打开一个表单页，例如：

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
