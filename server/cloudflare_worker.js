/**
 * Cloudflare Worker: Amiya AI Free Relay (阿米娅免 Key 公共 AI 中转网关)
 * 
 * 功能特性：
 * 1. 客户端免 Key 访问：客户端请求时若未附带 Authorization，服务端自动注入免费模型 API Key（如智谱 GLM-4-Flash 或 硅基流动）。
 * 2. 兼容 OpenAI 格式：支持 /v1/chat/completions 转发。
 * 3. 完整跨域支持 (CORS)：支持任意移动端、网页或桌面客户端直接调用。
 * 4. 频率限制 (Rate Limiting) 与安全保护：单 IP 访问频率限制、输入字数截断，防止公共通道被恶意刷量。
 * 5. 0 成本长期运行：Cloudflare Workers 每日免费提供 100,000 次请求额度，搭配 0 元免费模型（GLM-4-Flash）永久免费。
 */

// 默认配置（可在 Cloudflare Worker 的 Settings -> Variables 环境变量中覆盖）
const CONFIG = {
  // 上游大模型 API 地址（默认使用智谱开放平台 GLM-4-Flash，完全免费）
  UPSTREAM_URL: "https://open.bigmodel.cn/api/paas/v4/chat/completions",
  // 默认免费模型名称
  DEFAULT_MODEL: "glm-4-flash",
  // 每分钟单个 IP 最大允许请求次数（防刷保护）
  RATE_LIMIT_PER_MINUTE: 30,
  // 单次最大请求字符长度限制
  MAX_INPUT_LENGTH: 3000,
};

// 内存简易限流记录器 (基于 Worker 实例周期)
const ipRequestCounts = new Map();

export default {
  async fetch(request, env, ctx) {
    // 1. 处理 CORS 跨域预检请求
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: getCorsHeaders(),
      });
    }

    const url = new URL(request.url);

    // 2. 健康检查与状态路由
    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response(JSON.stringify({
        status: "ok",
        service: "Amiya-Free-AI-Relay",
        upstream: env.UPSTREAM_URL || CONFIG.UPSTREAM_URL,
        default_model: env.DEFAULT_MODEL || CONFIG.DEFAULT_MODEL,
        has_default_key: Boolean(env.DEFAULT_API_KEY),
        timestamp: Date.now()
      }, null, 2), {
        status: 200,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          ...getCorsHeaders()
        }
      });
    }

    // 3. 仅处理 chat completions 路径
    if (!url.pathname.endsWith("/chat/completions")) {
      return new Response(JSON.stringify({
        error: { message: "Endpoint not found. Please POST to /v1/chat/completions" }
      }), {
        status: 404,
        headers: { "Content-Type": "application/json", ...getCorsHeaders() }
      });
    }

    if (request.method !== "POST") {
      return new Response(JSON.stringify({
        error: { message: "Method not allowed. Only POST is accepted." }
      }), {
        status: 405,
        headers: { "Content-Type": "application/json", ...getCorsHeaders() }
      });
    }

    // 4. IP 简易速率限制
    const clientIP = request.headers.get("CF-Connecting-IP") || "unknown";
    const now = Date.now();
    const limit = parseInt(env.RATE_LIMIT_PER_MINUTE || CONFIG.RATE_LIMIT_PER_MINUTE, 10);
    const ipRecord = ipRequestCounts.get(clientIP) || { count: 0, resetAt: now + 60000 };
    
    if (now > ipRecord.resetAt) {
      ipRecord.count = 0;
      ipRecord.resetAt = now + 60000;
    }
    ipRecord.count += 1;
    ipRequestCounts.set(clientIP, ipRecord);

    if (ipRecord.count > limit) {
      return new Response(JSON.stringify({
        error: {
          message: "请求过于频繁，请稍后再试（博士，请给阿米娅一点思考时间哦）。",
          type: "rate_limit_exceeded"
        }
      }), {
        status: 429,
        headers: { "Content-Type": "application/json; charset=utf-8", ...getCorsHeaders() }
      });
    }

    // 5. 解析并装配请求体
    try {
      const bodyText = await request.text();
      if (bodyText.length > CONFIG.MAX_INPUT_LENGTH) {
        return new Response(JSON.stringify({
          error: { message: "输入内容过长，请精简后重试。" }
        }), {
          status: 400,
          headers: { "Content-Type": "application/json; charset=utf-8", ...getCorsHeaders() }
        });
      }

      let payload = {};
      try {
        payload = JSON.parse(bodyText);
      } catch (err) {
        return new Response(JSON.stringify({ error: { message: "Invalid JSON body" } }), {
          status: 400,
          headers: { "Content-Type": "application/json", ...getCorsHeaders() }
        });
      }

      // 如果客户端请求附带了有效自定义 Authorization，则优先使用客户端的
      const clientAuth = request.headers.get("Authorization");
      const serverKey = env.DEFAULT_API_KEY || "";
      const finalAuth = clientAuth && clientAuth.trim().length > 10 ? clientAuth : (serverKey ? `Bearer ${serverKey}` : "");

      // 默认模型：当走公共免费线路时强制指定为免费模型
      if (!clientAuth || !payload.model || payload.model === "deepseek-chat") {
        payload.model = env.DEFAULT_MODEL || CONFIG.DEFAULT_MODEL;
      }

      const upstreamUrl = env.UPSTREAM_URL || CONFIG.UPSTREAM_URL;
      const upstreamHeaders = {
        "Content-Type": "application/json",
        "User-Agent": "Amiya-Free-AI-Relay/1.0"
      };
      if (finalAuth) {
        upstreamHeaders["Authorization"] = finalAuth;
      }

      // 向大模型服务商发起请求
      const upstreamResponse = await fetch(upstreamUrl, {
        method: "POST",
        headers: upstreamHeaders,
        body: JSON.stringify(payload)
      });

      // 转发响应并注入 CORS 标头
      const respHeaders = new Headers(upstreamResponse.headers);
      const cors = getCorsHeaders();
      for (const [k, v] of Object.entries(cors)) {
        respHeaders.set(k, v);
      }

      return new Response(upstreamResponse.body, {
        status: upstreamResponse.status,
        headers: respHeaders
      });

    } catch (e) {
      return new Response(JSON.stringify({
        error: { message: "中转网关处理异常: " + (e.message || String(e)) }
      }), {
        status: 502,
        headers: { "Content-Type": "application/json; charset=utf-8", ...getCorsHeaders() }
      });
    }
  }
};

function getCorsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
    "Access-Control-Max-Age": "86400",
  };
}
