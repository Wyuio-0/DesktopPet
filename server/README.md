# 🌐 阿米娅免 Key 公共 AI 中转网关 (Amiya Free AI Relay)

本项目提供基于 **Cloudflare Workers** 的轻量反向代理，用于实现：
> **用户在手机端（Android）或电脑桌面端（PC）无需配置任何 API Key，也能直接与阿米娅进行智能 AI 对话！**

---

## 🌟 核心优势

1. **完全免费，0 成本运行**：
   - 依赖 **智谱 GLM-4-Flash** 大模型：官方承诺**永久 0 元免费**。
   - 依赖 **Cloudflare Workers**：每日提供 **100,000 次免费请求**。
2. **密钥安全不泄露**：
   - API Key 保存在 Cloudflare 云端环境变量中，不写入客户端代码，开源仓库零泄密风险。
3. **内置防刷与限流**：
   - 内置单 IP 访问频率限制与单次输入字数保护，避免被脚本恶意刷量。
4. **无缝双向兼容**：
   - 普通用户：免 Key 直接开箱畅聊；
   - 高级用户：在客户端填写自己的 DeepSeek / Kimi / GPT Key，代理网关会自动穿透，使用用户自定义模型。

---

## 🚀 2 分钟极速部署教程

### 第一步：获取智谱 GLM-4-Flash 免费 API Key
1. 访问 [智谱开放平台 (bigmodel.cn)](https://bigmodel.cn/) 并注册登录；
2. 进入控制台左侧「API Keys」，点击「创建 API Key」；
3. 复制生成的 Key（例如 `xxxxxxxxxxxx.yyyyyyyyyyyy`，此模型调用永久免费）。

---

### 第二步：一键部署到 Cloudflare Worker
1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com/)（没有可免费注册）；
2. 点击左侧导航栏的 **「Compute (Workers & Pages)」** -> **「Create application」** -> **「Create Worker」**；
3. 给 Worker 起一个名称（例如 `amiya-ai-relay`），点击 **「Deploy」**；
4. 部署成功后，点击 **「Edit code」** 进入在线编辑器：
   - 将 `server/cloudflare_worker.js` 的完整代码全部复制并粘贴替换掉编辑器里的默认内容；
   - 点击右上角 **「Save and deploy」**；
5. 设置云端密钥（环境变量）：
   - 返回该 Worker 管理页面，进入 **「Settings」** -> **「Variables and Secrets」**；
   - 点击 **「Add」**：
     - **Variable name**: `DEFAULT_API_KEY`
     - **Value**: 粘贴您在第一步获取的智谱 API Key；
     - （可选）勾选 *Encrypt* 进行加密存储；
   - 点击 **「Save and deploy」**。

---

### 第三步：测试与上线
1. 在 Worker 概览页复制您的公开访问域名（形如：`https://amiya-ai-relay.<你的用户名>.workers.dev`）；
2. 在浏览器打开 `https://amiya-ai-relay.<你的用户名>.workers.dev/health`，若显示：
   ```json
   {
     "status": "ok",
     "service": "Amiya-Free-AI-Relay",
     "default_model": "glm-4-flash",
     "has_default_key": true
   }
   ```
   即说明网关已成功就绪！
3. 将此 Worker 域名填入 Android 端或 PC 桌面端公共线路配置中，即可让所有用户开箱即聊。
