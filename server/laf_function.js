/**
 * Laf 云函数: Amiya AI Free Relay (阿米娅免 Key 国内直连 AI 中转网关)
 * 平台: Laf (https://laf.run)
 * 
 * 优势:
 * 1. 国内直连: 服务器与域名均在国内/合规节点，免翻墙、无需 VPN、秒级响应。
 * 2. 0 成本运行: 结合 Laf 免费额度与智谱 GLM-4-Flash 永久免费模型，长期 0 成本。
 * 3. 完整支持 SSE 流式传输: 完美兼容安卓手机端打字机效果与深度思考过程 (CoT)。
 * 4. 密钥安全: 智谱 API Key 保存在云端环境变量 DEFAULT_API_KEY 中，不暴露给客户端。
 */

import cloud from '@lafjs/cloud'

// 内存简易限流器 (单 IP 访问频率限制)
const ipRequestCounts = new Map()

export default async function (ctx: FunctionContext) {
  const { req, response: res } = ctx

  // 1. 设置跨域头 (CORS)
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With, Accept')

  // 2. 处理 OPTIONS 预检请求
  if (ctx.method === 'OPTIONS') {
    res.status(204).end()
    return
  }

  // 3. 处理 GET 健康检查与就绪状态探测
  if (ctx.method === 'GET') {
    const defaultKey = cloud.env.DEFAULT_API_KEY || process.env.DEFAULT_API_KEY || ''
    return {
      status: 'ok',
      service: 'Amiya-Free-AI-Relay-Laf',
      region: 'China-Direct (免VPN国内直连)',
      upstream: 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
      default_model: 'glm-4-flash',
      has_default_key: Boolean(defaultKey),
      timestamp: Date.now()
    }
  }

  // 4. 仅处理 POST 请求
  if (ctx.method !== 'POST') {
    res.status(405).json({
      error: { message: 'Method Not Allowed. Please POST to /v1/chat/completions' }
    })
    return
  }

  // 5. 简易防刷频控 (单 IP 每分钟最多 30 次)
  const clientIp = ctx.headers['x-forwarded-for'] || ctx.headers['x-real-ip'] || 'unknown'
  const now = Date.now()
  const ipRecord = ipRequestCounts.get(clientIp) || { count: 0, resetAt: now + 60000 }
  if (now > ipRecord.resetAt) {
    ipRecord.count = 0
    ipRecord.resetAt = now + 60000
  }
  ipRecord.count++
  ipRequestCounts.set(clientIp, ipRecord)
  if (ipRecord.count > 30) {
    res.status(429).json({
      error: { message: '请求过于频繁，请稍后再试 (Rate limit exceeded)' }
    })
    return
  }

  // 6. 提取 API Key
  const defaultApiKey = cloud.env.DEFAULT_API_KEY || process.env.DEFAULT_API_KEY || ''
  const clientAuth = ctx.headers['authorization'] || ''
  const finalApiKey = clientAuth ? clientAuth : (defaultApiKey ? `Bearer ${defaultApiKey.replace(/^Bearer\s+/i, '')}` : '')

  if (!finalApiKey) {
    res.status(500).json({
      error: {
        message: '中转网关未配置 DEFAULT_API_KEY 环境变量，请在 Laf 控制台「环境变量」中设置智谱 API Key。'
      }
    })
    return
  }

  // 7. 准备请求载荷
  const payload = ctx.body || {}
  if (!payload.model) {
    payload.model = 'glm-4-flash'
  }

  // 截断超长输入保护
  if (Array.isArray(payload.messages)) {
    for (const msg of payload.messages) {
      if (typeof msg.content === 'string' && msg.content.length > 4000) {
        msg.content = msg.content.slice(-4000)
      }
    }
  }

  const UPSTREAM_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'

  try {
    const upstreamRes = await fetch(UPSTREAM_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': finalApiKey,
        'Accept': payload.stream ? 'text/event-stream' : 'application/json'
      },
      body: JSON.stringify(payload)
    })

    if (!upstreamRes.ok) {
      const errText = await upstreamRes.text()
      res.status(upstreamRes.status).send(errText)
      return
    }

    // 8. 处理流式输出 (SSE / text/event-stream)
    if (payload.stream) {
      res.setHeader('Content-Type', 'text/event-stream; charset=utf-8')
      res.setHeader('Cache-Control', 'no-cache')
      res.setHeader('Connection', 'keep-alive')

      if (upstreamRes.body) {
        const reader = upstreamRes.body.getReader()
        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            res.end()
            break
          }
          res.write(value)
        }
      } else {
        res.end()
      }
    } else {
      // 9. 处理普通 JSON 响应
      const data = await upstreamRes.json()
      res.status(200).json(data)
    }
  } catch (err) {
    console.error('Laf relay proxy error:', err)
    res.status(502).json({
      error: {
        message: `中转请求上游异常: ${err.message || String(err)}`
      }
    })
  }
}
