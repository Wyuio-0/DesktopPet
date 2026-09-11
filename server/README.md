# 🌐 阿米娅免 Key 公共 AI 中转网关 (Amiya Free AI Relay)

本项目提供轻量反向代理网关实现，用于实现：
> **用户在手机端（Android）或电脑桌面端（PC）无需配置任何 API Key，也能直接与阿米娅进行智能 AI 对话！**

---

## 🧭 部署方案选型对比

| 方案 | 部署平台 | 国内访问状态 | 是否需要域名 | 推荐场景 | 代码文件 |
|---|---|---|---|---|---|
| **方案一（强烈推荐）** | **Laf (laf.run)** | **免 VPN 秒级直连** | ❌ 不需要（平台赠送二级域名） | **国内用户首选**，免翻墙、开箱即用 | `server/laf_function.js` |
| **方案二** | **Cloudflare Workers** | ⚠️ 需绑定自定义域名 | ✅ 需绑定个人自有域名 | 拥有海外云/已有独立域名用户 | `server/cloudflare_worker.js` |

> 💡 **为什么 Cloudflare 默认域名国内无法使用？**  
> Cloudflare 默认分配的 `*.workers.dev` 二级域名在中国大陆已被长城防火墙（GFW）进行 DNS 污染和 SNI 阻断，因此在不开 VPN 的情况下会连接失败。  
> **Laf (laf.run)** 的服务器与二级域名均在国内/合规节点，完美支持 **免翻墙直连** 与 **SSE 流式传输（打字机效果与思维链展示）**！

---

## 🚀 方案一：Laf (laf.run) 3 分钟极速部署教程（国内免翻墙首选）

### 第一步：获取智谱 GLM-4-Flash 免费 API Key
1. 打开 [智谱开放平台 (bigmodel.cn)](https://bigmodel.cn/) 注册并登录；
2. 点击控制台左侧 **「API Keys」** -> **「创建 API Key」**；
3. 复制生成的 API Key（例如 `xxxxxxxxxxxx.yyyyyyyyyyyy`，此模型官方承诺**永久 0 元免费**）。

---

### 第二步：在 Laf 平台创建云函数
1. 访问并登录 [Laf 云开发平台 (laf.run)](https://laf.run/)（国内手机号一键注册登录）；
2. 在控制台点击 **「新建应用」**（选择免费规格，应用名称任意如 `amiya-ai`）；
3. 进入应用详情页，点击左侧导航栏的 **「云函数」** -> 点击 **「+ (新建函数)」**：
   - **函数名称 / 路径**：输入 `chat` 或 `v1/chat/completions`（建议填 `v1/chat/completions`）；
   - **请求方法**：勾选 `POST`、`GET`（用于健康检查探测）、`OPTIONS`；
4. 将本项目中 [`server/laf_function.js`](file:///d:/Dev/project/floating/server/laf_function.js) 的完整代码复制，粘贴覆盖到 Laf 在线代码编辑器中。

---

### 第三步：配置云端 API Key 环境变量
1. 在 Laf 左侧导航栏点击 **「环境变量」**（或应用设置中的环境变量）；
2. 点击 **「添加环境变量」**：
   - **变量名**：`DEFAULT_API_KEY`
   - **变量值**：粘贴在第一步中获取的智谱 API Key；
3. 保存环境变量（Laf 会自动热更新）。

---

### 第四步：发布云函数并验证
1. 回到云函数编辑器，点击右上角 **「发布」**；
2. 在函数界面顶部即可看到该函数的公开调用地址，形如：
   ```text
   https://<你的应用ID>.laf.run/v1/chat/completions
   ```
3. **验证连通性**：
   在手机或电脑浏览器中（**不开启任何代理/VPN**）访问该地址的健康检查：
   ```text
   https://<你的应用ID>.laf.run/v1/chat/completions
   ```
   页面正常返回以下 JSON 即表示部署成功：
   ```json
   {
     "status": "ok",
     "service": "Amiya-Free-AI-Relay-Laf",
     "region": "China-Direct (免VPN国内直连)",
     "default_model": "glm-4-flash",
     "has_default_key": true
   }
   ```
4. 将该完整 URL 填入客户端设置或项目的 `DEFAULT_PUBLIC_RELAY_URL` 中即可！

---

## 🌐 方案二：Cloudflare Workers 部署教程（需自定义域名）

若您拥有个人独立域名并将 DNS 托管在 Cloudflare：

1. 打开 [Cloudflare Dashboard](https://dash.cloudflare.com/) -> **Compute (Workers & Pages)** -> **Create Worker**；
2. 将 [`server/cloudflare_worker.js`](file:///d:/Dev/project/floating/server/cloudflare_worker.js) 代码粘贴并保存发布；
3. 在 Worker 的 **Settings -> Variables and Secrets** 添加 `DEFAULT_API_KEY` 为智谱 API Key；
4. **关键步骤（国内免翻墙）**：
   - 进入 Worker -> **Settings** -> **Domains & Routes** -> **Add Custom Domain**；
   - 绑定一个您自己的二级域名（如 `ai.yourdomain.com`）；
   - 绑定完成后，国内用户即可通过 `https://ai.yourdomain.com/v1/chat/completions` 免 VPN 直连。
