# Wi-Fi 现网诊断与修复记录

2026-11-14，vivo V2199A，Android 14 / SDK 34。用户确认暂时无法提供另一可互访网络，先完成可独立复现的代码修复。

## 现网结论

PC 和手机本机回环 HTTP 探测均成功，但跨设备 TCP 在两个方向均超时，UDP 自动发现也未成功。测试未修改防火墙或网络配置；同一 Wi-Fi、同一网段本身不保证允许设备互访。当前证据无法确定限制来自接入网络、代理还是其他网络边界。

直连前置条件未满足，因此没有执行这轮 Wi-Fi 配对、同步、后台收发、Wi-Fi 断开恢复和热点切换。传输正文检查标为跳过，不能把没有流量计为加密验证通过。

原始问题的脱敏结果见 [修复前现网诊断](acceptance/android-lan-before-fix-2026-11-14.json)。不包含网络地址、Wi-Fi 名称、手机序列号、令牌或密钥。

## 已修复

- **Android UDP 端口未释放**：真机停止同步后，独占绑定发现端口返回 `EADDRINUSE`。取消协程不能中断阻塞的 `DatagramSocket.receive()`；现将 UDP socket 纳入服务生命周期，在停止时显式关闭。启动、停止串行执行，协程持有各自 socket，避免重启时旧任务影响新监听。
- **断网提示误导重新配对**：PC 探测不到设备不再直接判断为不支持加密协议；PC 和 Android 的连接错误提示检查网络、恢复后重试，并保留已有配对。认证失败仍然拒绝，未增加明文回退。
- **验收工具**：新增直接 LAN 模式、双向 HTTP 探测、UDP 发现和本机监听诊断；只有直连成功才执行后续同步。新增服务中断后保持数据和凭证、恢复后使用原凭证同步的检查。已安装 APK 的 SHA-256 一致时复用，减少手机重复安装确认。
- **CI**：新增独立验收应用及 instrumentation 的编译检查，不在无真机的 CI 环境声称执行物理网络测试。

PC 回归：441 passed、1 skipped。Android 独立应用与测试包构建成功。修复后通过 USB 转发运行原生 PC / Android 回归，**20 / 20 通过**，包含 UDP 端口释放、PC 服务中断时数据和凭证不变、恢复后使用原配对同步；见 [修复后 USB 真机回归](acceptance/android-connectivity-usb-fixed-2026-11-14.json)。该回归不代替 Wi-Fi 互访验收。

## 复现 LAN 模式

先按 [独立验收构建步骤](android-sync-acceptance.md) 生成应用及测试包，连接并授权 USB 调试，再在仓库根目录执行：

```powershell
python tools/run_android_sync_acceptance.py --adb <adb.exe路径> --aapt <aapt.exe路径> --serial <手机序列号> --transport lan --pc-address <电脑的局域网IPv4> --phone-address <手机的局域网IPv4> --report scratch/android-lan-acceptance.json
```

LAN 模式中，同步和探测均使用所给局域网 IP，测试工具不为同步服务建立 ADB TCP forward/reverse；仅临时测试控制接口通过 USB 回环转发，配对密钥也通过 USB 测试参数交付。正式协议不会发送该控制令牌。

有可互访的 Wi-Fi 后可附加 `--cycle-wifi`，短暂关闭并恢复测试手机的 Wi-Fi。测试和异常清理均尝试重新开启 Wi-Fi。该选项会影响测试期间手机的网络连接；它只测试同一网络的断开恢复，不等同于切换两个热点。后台用例只覆盖 instrumentation 存活时退到桌面 15 秒，不代表锁屏、省电模式、杀进程或长期保活。
