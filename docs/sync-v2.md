# Rhodes Sync v2

## 使用与升级

三端统一使用 HTTP 承载的 AES-256-GCM 认证加密消息。只有 `/api/info` 和 UDP 设备发现是公开信息；课表、考试、便签、剪贴板、状态消息和配对令牌均在加密消息内。此方案不提供 HTTPS 证书，也不隐藏 IP、设备公开名称或消息长度。

1. 两端都升级到支持 v2 的版本。旧 HTTP Bearer 配对和 iOS 未认证 TCP 快传均被拒绝，不会自动降级。
2. 在接收端开启同步并生成配对密钥。将完整密钥通过可信渠道粘贴到发送端，选择目标 IP／设备后发起配对。
3. 对照双方显示的六位核对码，在接收端确认。核对码只是密钥指纹提示，不能替代完整密钥。
4. 成功后使用已配对设备执行快传或合并同步。旧配对需重新建立，升级不会删除课表、考试或笔记。

密钥为操作系统安全随机数生成的 32 字节，base64url 编码后为 43 个字符。生成的邀请 5 分钟有效，同一邀请仅允许一个请求在途，确认成功后失效。该密钥随后作为此配对的长期凭证保存，请勿公开分享、提交密钥配置或上传包含凭证的备份。PC 使用用户配置目录，Android 使用应用私有存储，iOS 使用设备专属 Keychain；不能防御已取得应用数据或同用户进程权限的本地恶意软件。

## 消息格式

私有接口只允许 `POST`、`Content-Type: application/json`、`X-Rhodes-Protocol: 2`，禁止明文 `Authorization` 头、浏览器来源和重定向。路径沿用 `/api/pair/request`、`/api/sync/pull`、`/api/sync/push`、`/api/clipboard`、`/api/status`、`/api/pair/unpair`。

外层 JSON 字段：`v` 固定整数 2；`kid` 是密钥原始 32 字节的 SHA-256；`epoch` 是接收端本次服务启动生成的随机 32 字节；`id` 是随机 16 字节请求标识；`ts` 为 Unix 秒整数；`s` 为请求的 0 或响应 HTTP 状态码；`nonce` 为随机 12 字节 GCM nonce；`ct` 为密文后接 16 字节认证标签。所有二进制字段使用不带填充的规范 base64url 编码。

附加认证数据（UTF-8，无换行）：

```
RhodesSync/2|{request或response}|POST|{路径}|{kid}|{epoch}|{id}|{ts}|{s}
```

明文必须是 UTF-8 JSON 对象，已配对请求在对象内携带 `_auth_token`。接收端根据 `kid` 找到配对密钥，验证令牌属于同一配对后才执行操作。响应沿用请求的 `epoch`、`id`、`ts`，使用独立随机 nonce，并将 HTTP 状态码纳入认证；客户端拒绝不匹配、未认证或明文响应。

GCM 随机 nonce 不复用；请求 ID 防重放记录保留 241 秒，允许时钟偏差不超过 120 秒。服务每次重启更换 epoch，从而拒绝仍处于时间窗口内的旧抓包。防重放表达到 4096 条时拒绝新请求，不驱逐未过期记录。无效认证不会占用防重放记录。

邀请不在网络上发布；设备发现只声明协议版本和 epoch。伪造发现信息或 epoch 会导致认证失败，不能使客户端回退为明文传输。发现设备不等于信任设备。

## 边界与验证

解密后的普通消息上限 4 MiB、配对上限 4 KiB、剪贴板上限 256 KiB；外层允许 base64 开销并在解密后再次检查。每端最多处理 16 个入站连接，读取超时 5 秒，完整连接亦有超时保护。配对等待 30 秒，按来源限流。

`tests/fixtures/sync_v2_vectors.tsv` 是公开的人工测试密钥与固定 nonce 向量，仅用于测试，不能用于实际配对。Python、JCA 和 CryptoKit 分别解密相同向量，并检查篡改、反射、请求／响应绑定、重放及服务重启。Python 另有真实 HTTP 双向加密测试；Android、iOS 分别通过原生构建检查。物理设备互联仍需按上述使用步骤验收。

相关实现依据：[cryptography AEAD](https://cryptography.io/en/latest/hazmat/primitives/aead/)、[Apple AES.GCM](https://developer.apple.com/documentation/cryptokit/aes/gcm)。
