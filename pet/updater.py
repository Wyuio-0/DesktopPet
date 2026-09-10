"""自动更新检查：启动时静默查询 GitHub Releases，发现新版本提示下载。

版本号 APP_VERSION 需与发布 tag 保持一致（发版时一起改）。
查询失败（离线 / 限流 / 网络错误）一律静默忽略，绝不影响正常启动。
"""

import json
import re
import urllib.request

# 与仓库发布 tag 保持一致（如发 v1.6.7 时这里就是 "1.6.7"）。
APP_VERSION = "1.8.14"

REPO = "Wyuio-0/DesktopPet"
_LATEST_API = "https://api.github.com/repos/%s/releases/latest" % REPO


def latest_release(timeout=5):
    """查询最新 Release。返回 (tag_name, html_url, installer_url) 或 None。

    installer_url 取第一个 .exe 资产（安装包），没有则为空串。
    """
    try:
        req = urllib.request.Request(
            _LATEST_API,
            headers={"User-Agent": "AmiyaDesktopPet",
                     "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        tag = str(data.get("tag_name", "")).strip()
        html = str(data.get("html_url", "")).strip()
        installer = ""
        for a in data.get("assets", []) or []:
            name = str(a.get("name", ""))
            if name.lower().endswith(".exe"):
                installer = str(a.get("browser_download_url", "")).strip()
                break
        if tag:
            return (tag, html, installer)
    except Exception:
        pass

    # 备用机制：通过 GitHub Release 页面 302 重定向解析最新 tag
    try:
        req2 = urllib.request.Request(
            "https://github.com/%s/releases/latest" % REPO,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req2, timeout=timeout) as r:
            final_url = r.geturl()
        m = re.search(r"/releases/tag/([^/?#]+)", final_url)
        if m:
            tag = m.group(1).strip()
            html = final_url
            installer = "https://github.com/%s/releases/download/%s/DesktopPet-Setup-%s.exe" % (REPO, tag, tag)
            return (tag, html, installer)
    except Exception:
        pass

    return None


def is_newer(tag, current=APP_VERSION):
    """'v1.4.0' / '1.4.0' 语义比较：tag 是否比 current 新。"""
    def norm(v):
        main_part = str(v).split("-")[0].split("+")[0]
        nums = re.findall(r"\d+", main_part)
        return [int(x) for x in nums[:3]] + [0] * (3 - len(nums[:3]))
    return norm(tag) > norm(current)
