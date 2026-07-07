#!/usr/bin/env python3
import json
import os
import re
import ssl
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
DATA = ROOT / "data" / "latest.json"
CHINA_TZ = timezone(timedelta(hours=8))
DEFAULT_REPOSITORY = "hothotpotjames-cloud/Power"

SOURCES = [
    ("中国气象局：7月气候趋势及台风预测", "https://www.cma.gov.cn/2011xwzx/2011xmtjj/202607/t20260702_7898375.html"),
    ("中国气象局2026年7月新闻发布会", "https://www.cma.gov.cn/2011zwxx/2011ztzgg/202606/t20260630_7891248.html"),
    ("中央气象台台风网", "https://typhoon.nmc.cn/web.html"),
    ("南京7天天气预报", "https://www.weather.com.cn/weather/101190101.shtml"),
    ("南京8-15天天气预报", "https://www.weather.com.cn/weather15d/101190101.shtml"),
    ("苏州8-15天天气预报", "https://www.weather.com.cn/weather15d/101190401.shtml"),
    ("徐州8-15天天气预报", "https://www.weather.com.cn/weather15d/101190801.shtml"),
    ("连云港8-15天天气预报", "https://www.weather.com.cn/weather15d/101191001.shtml"),
]


def china_now():
    return datetime.now(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")


def github_pages_url():
    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY)
    if "/" not in repo:
        return ""
    owner, name = repo.split("/", 1)
    return f"https://{owner}.github.io/{name}/"


def manual_run_url():
    repo = os.environ.get("GITHUB_REPOSITORY", DEFAULT_REPOSITORY)
    if not repo:
        return ""
    return f"https://github.com/{repo}/actions/workflows/update-dashboard.yml"


def fetch_source(name, url):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 JiangsuPowerWeatherDashboard/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    context = ssl.create_default_context()
    try:
        with urlopen(req, timeout=20, context=context) as resp:
            raw = resp.read(60000)
            charset = resp.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="ignore")
            title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
            return {
                "name": name,
                "url": url,
                "status": "ok",
                "httpStatus": resp.status,
                "title": title[:120],
                "checkedAt": china_now(),
            }
    except HTTPError as exc:
        return {"name": name, "url": url, "status": "http_error", "httpStatus": exc.code, "checkedAt": china_now()}
    except URLError as exc:
        return {"name": name, "url": url, "status": "url_error", "error": str(exc.reason), "checkedAt": china_now()}
    except Exception as exc:
        return {"name": name, "url": url, "status": "error", "error": str(exc), "checkedAt": china_now()}


def update_index_timestamp(updated_at, page_url):
    html = INDEX.read_text(encoding="utf-8")
    html = re.sub(r"更新时间：[^。]+。", f"更新时间：{updated_at}。", html, count=1)
    if page_url:
        html = html.replace("部署到 GitHub Pages 后自动显示正式网址", page_url)
    INDEX.write_text(html, encoding="utf-8")


def main():
    updated_at = china_now()
    source_results = [fetch_source(name, url) for name, url in SOURCES]
    ok_count = sum(1 for item in source_results if item["status"] == "ok")
    page_url = github_pages_url()
    payload = {
        "updatedAt": updated_at,
        "message": f"GitHub Actions 已于北京时间 {updated_at} 完成更新；权威气象源检查 {ok_count}/{len(source_results)} 个可访问。页面已纳入苏南/苏北降雨量、光照时长和光照强度展示；后续可在脚本中继续接入结构化天气解析和电价预测重算。",
        "pageUrl": page_url,
        "manualRunUrl": manual_run_url(),
        "sources": source_results,
        "forecastPolicy": {
            "southJiangsu": "优先跟踪高温高湿、降雨量、云量、光照时长/强度和沿江沿海风速，对峰段价格与光伏出力偏差做滚动修正。",
            "northJiangsu": "优先跟踪强降雨、台风残余环流、光照衰减、沿海风电波动和局部阻塞风险。",
            "spotPrice": "当前版本保留原有天气驱动预测框架，并用降雨量、光照时长/强度辅助判断空调负荷、光伏出力和午间价格弹性；真实出清价数值化需要接入负荷、风光、机组可用率、外来电和市场报价数据。"
        }
    }
    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_index_timestamp(updated_at, page_url)
    print(json.dumps({"updatedAt": updated_at, "okSources": ok_count, "pageUrl": page_url}, ensure_ascii=False))


if __name__ == "__main__":
    main()
