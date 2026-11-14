# Android 真机同步验收

2026-11-14 使用 vivo V2199A（Android 14 / SDK 34）重新验收，18 项全部通过。
结果见 [脱敏 JSON 记录](acceptance/android-usb-vivo-2026-11-14.json)。PC 回归测试为 439 passed、1 skipped；独立 Android 应用与 instrumentation APK 均构建成功。

## 本次发现及修复

首次完整运行有 16 项通过、2 项失败：PC 接收、保存和重新打包课表与考试时没有保留原始 ID。
进一步检查发现自定义课程时间、Android 节次时间，以及考试时长、座位、类型、备注和关联课程也会在往返过程中丢失。

此次保留这些字段和毫秒时间；合并优先按稳定 ID 更新，旧数据按完整上课安排或考试名称与时间识别，避免单纯按课程名和开始节次、考试名称去重造成数据丢失。针对磁盘往返、同名不同安排、同 ID 编辑和旧任务格式补充了回归测试。

## 已验证范围

- Android 发起加密配对；接收端拒绝新配对时保留原信任关系。
- 旧配对和格式有效的错误密钥被拒绝；过期邀请被拒绝；撤销后拒绝旧凭证；重新配对后恢复。
- 双向加密快传支持中文和 emoji。
- 双向课表、考试和便签同步；课程 ID、自定义时间、节次时间及考试字段完整保留。
- 重复合并不增加课程和考试数量。
- PC 与 Android 同步**服务**分别停止再启动后可继续同步。
- 在记录的请求、响应字节中未发现本轮测试的配对密钥、令牌或测试正文原文。

过期邀请用 PC 测试控制端将邀请有效期置为过去触发；未实际等待五分钟。服务重启测试不等同于杀进程、设备重启或后台保活测试。

本次流量通过 USB ADB 的 TCP forward/reverse 转发，运行的是手机原生同步实现和 PC 服务。**尚未覆盖 Wi-Fi UDP 自动发现、路由器隔离、断网重连或 iOS 真机互联**；这些仍需单独验收。传输字节检查只针对本轮已知测试数据，不代表对所有运行场景的网络审计。

## 复现

1. 使用已授权 USB 调试的手机，保持屏幕解锁，依次允许应用包和测试包的安装提示。
2. 在 `android` 目录构建独立包：

   ```powershell
   .\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest -PsyncAcceptance=true --no-daemon
   ```

3. 在仓库根目录运行（Python 环境需安装项目依赖）：

   ```powershell
   python tools/run_android_sync_acceptance.py --adb <adb.exe路径> --aapt <aapt.exe路径> --serial <手机序列号> --report scratch/android-sync-acceptance.json
   ```

脚本校验 APK 与 instrumentation 均指向固定包名 `com.amiya.pet.syncacceptance` 后才安装，并只清空该独立包的数据。PC 数据使用临时目录，清除继承的 `PET_*_FILE` 路径覆盖。测试结束会关闭独立应用、PC 服务，并移除本轮创建的 USB 转发；独立包保留在手机上供复测。

配对密钥和控制令牌在运行时生成，不写入验收报告。报告只包含机型、系统版本、项目结果，不含 USB 序列号、个人数据或凭证。测试控制接口仅监听 PC 回环地址并要求临时令牌；它不属于正式同步协议。
