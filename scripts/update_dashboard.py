#!/usr/bin/env python3
import json
import os
import re
import ssl
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from html import escape, unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
DATA = ROOT / "data" / "latest.json"
CHINA_TZ = timezone(timedelta(hours=8))
DEFAULT_REPOSITORY = "hothotpotjames-cloud/Power"

CITY_GROUPS = {
    "southJiangsu": [
        ("南京", "101190101"),
        ("苏州", "101190401"),
    ],
    "northJiangsu": [
        ("徐州", "101190801"),
        ("连云港", "101191001"),
    ],
}

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


@dataclass
class DayForecast:
    city: str
    forecast_date: date
    weather: str
    high: int
    low: int
    wind: str
    wind_level: str
    source: str


def china_now():
    return datetime.now(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")


def china_today():
    return datetime.now(CHINA_TZ).date()


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


def fetch_text(url):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 JiangsuPowerWeatherDashboard/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    context = ssl.create_default_context()
    last_error = None
    candidates = [url]
    if url.startswith("https://www.weather.com.cn/"):
        candidates.append("http://" + url.removeprefix("https://"))
    for candidate in candidates:
        try:
            with urlopen(Request(candidate, headers=req.headers), timeout=20, context=context) as resp:
                raw = resp.read(180000)
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="ignore"), resp.status, candidate
        except Exception as exc:
            last_error = exc
    try:
        completed = subprocess.run(
            ["curl", "-Ls", "--max-time", "25", url],
            check=True,
            capture_output=True,
        )
        text = completed.stdout.decode("utf-8", errors="ignore")
        if text.strip():
            return text, 200, url
    except Exception as exc:
        last_error = exc
    raise last_error


def fetch_source(name, url):
    try:
        text, status, final_url = fetch_text(url)
        title_match = re.search(r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S)
        title = re.sub(r"\s+", " ", unescape(title_match.group(1))).strip() if title_match else ""
        return {
            "name": name,
            "url": url,
            "status": "ok",
            "httpStatus": status,
            "title": title[:120],
            "checkedAt": china_now(),
            "finalUrl": final_url,
        }
    except HTTPError as exc:
        return {"name": name, "url": url, "status": "http_error", "httpStatus": exc.code, "checkedAt": china_now()}
    except URLError as exc:
        return {"name": name, "url": url, "status": "url_error", "error": str(exc.reason), "checkedAt": china_now()}
    except Exception as exc:
        return {"name": name, "url": url, "status": "error", "error": str(exc), "checkedAt": china_now()}


def clean_text(text):
    text = re.sub(r"<.*?>", "", text, flags=re.S)
    text = unescape(text)
    return re.sub(r"\s+", "", text)


def parse_ints(text):
    return [int(x) for x in re.findall(r"-?\d+", text)]


def resolve_date(base_year, base_month, day, previous=None):
    year = base_year
    month = base_month
    if previous and day < previous.day:
        month += 1
        if month > 12:
            month = 1
            year += 1
    return date(year, month, day)


def parse_weather7(city, code, html):
    hidden = re.search(r'id="hidden_title" value="(\d{2})月(\d{2})日', html)
    if hidden:
        base_year = china_today().year
        base_month = int(hidden.group(1))
    else:
        base_year = china_today().year
        base_month = china_today().month
    block = re.search(r'<div id="7d" class="c7d".*?<ul class="t clearfix">(.*?)</ul>', html, re.S)
    if not block:
        return []
    items = re.findall(r"<li.*?</li>", block.group(1), re.S)
    forecasts = []
    previous = None
    for item in items:
        day_match = re.search(r"<h1>(\d+)日", item)
        weather_match = re.search(r'<p title="([^"]+)" class="wea">', item)
        high_match = re.search(r'<p class="tem">\s*<span>(-?\d+)</span>/<i>(-?\d+)℃</i>', item, re.S)
        wind_titles = re.findall(r'<span title="([^"]+)"', item)
        wind_level = clean_text(re.search(r'<p class="win">.*?<i>(.*?)</i>', item, re.S).group(1)) if re.search(r'<p class="win">.*?<i>(.*?)</i>', item, re.S) else ""
        if not (day_match and weather_match and high_match):
            continue
        forecast_date = resolve_date(base_year, base_month, int(day_match.group(1)), previous)
        previous = forecast_date
        forecasts.append(DayForecast(
            city=city,
            forecast_date=forecast_date,
            weather=clean_text(weather_match.group(1)),
            high=int(high_match.group(1)),
            low=int(high_match.group(2)),
            wind="转".join(wind_titles[:2]) if wind_titles else "",
            wind_level=wind_level,
            source="7天天气预报",
        ))
    return forecasts


def parse_weather15(city, code, html, base_date):
    block = re.search(r'<div id="15d" class="c15d".*?<ul class="t clearfix">(.*?)</ul>', html, re.S)
    if not block:
        return []
    items = re.findall(r"<li.*?</li>", block.group(1), re.S)
    forecasts = []
    previous = None
    for item in items:
        day_match = re.search(r"（(\d+)日）", item)
        weather_match = re.search(r'<span class="wea">(.*?)</span>', item, re.S)
        temp_match = re.search(r'<span class="tem"><em>(-?\d+)℃</em>/(-?\d+)℃</span>', item, re.S)
        wind_match = re.search(r'<span class="wind">(.*?)</span>', item, re.S)
        level_match = re.search(r'<span class="wind1">(.*?)</span>', item, re.S)
        if not (day_match and weather_match and temp_match):
            continue
        forecast_date = resolve_date(base_date.year, base_date.month, int(day_match.group(1)), previous or base_date)
        previous = forecast_date
        forecasts.append(DayForecast(
            city=city,
            forecast_date=forecast_date,
            weather=clean_text(weather_match.group(1)),
            high=int(temp_match.group(1)),
            low=int(temp_match.group(2)),
            wind=clean_text(wind_match.group(1)) if wind_match else "",
            wind_level=clean_text(level_match.group(1)) if level_match else "",
            source="8-15天天气预报",
        ))
    return forecasts


def fetch_city_forecast(city, code):
    forecasts = []
    errors = []
    for path, parser in (
        ("weather", parse_weather7),
        ("weather15d", parse_weather15),
    ):
        url = f"https://www.weather.com.cn/{path}/{code}.shtml"
        try:
            html, _, final_url = fetch_text(url)
            if path == "weather":
                forecasts.extend(parser(city, code, html))
            else:
                base = min((item.forecast_date for item in forecasts), default=china_today())
                forecasts.extend(parser(city, code, html, base))
        except Exception as exc:
            errors.append({"city": city, "url": url, "error": str(exc)})
    merged = {}
    for item in forecasts:
        merged[item.forecast_date.isoformat()] = item
    return list(merged.values()), errors


def rain_mm(weather):
    if "大暴雨" in weather or "特大暴雨" in weather:
        return 85
    if "暴雨" in weather:
        return 55
    if "大雨" in weather:
        return 28
    if "中雨" in weather:
        return 12
    if "小雨" in weather or "阵雨" in weather or "雷阵雨" in weather or weather == "雨":
        return 5
    if "雨" in weather:
        return 8
    return 0


def sunlight_hours(weather):
    if "晴" in weather and "雨" not in weather:
        return 8.0, "强"
    if "晴" in weather:
        return 6.5, "较强"
    if "多云" in weather and "雨" not in weather:
        return 6.0, "中等-较强"
    if "多云" in weather:
        return 4.5, "中等"
    if "阴" in weather and "雨" not in weather:
        return 3.0, "弱-中等"
    if "暴雨" in weather or "大雨" in weather:
        return 1.0, "很弱"
    if "雨" in weather:
        return 2.0, "弱"
    return 4.0, "中等"


def max_wind_level(text):
    numbers = parse_ints(text)
    return max(numbers) if numbers else 3


def region_summary(items):
    if not items:
        return None
    highs = [item.high for item in items]
    lows = [item.low for item in items]
    rain = [rain_mm(item.weather) for item in items]
    sun = [sunlight_hours(item.weather)[0] for item in items]
    wind = [max_wind_level(item.wind_level) for item in items]
    weather_bits = "、".join(f"{item.city}{item.weather}" for item in items)
    wind_bits = "、".join(f"{item.city}{item.wind}{item.wind_level}" for item in items if item.wind or item.wind_level)
    sunlight_strength = sunlight_hours(max(items, key=lambda item: sunlight_hours(item.weather)[0]).weather)[1]
    return {
        "weatherBits": weather_bits,
        "temp": f"{min(lows)}-{max(highs)}C",
        "rainRange": (min(rain), max(rain)),
        "sunRange": (min(sun), max(sun)),
        "sunStrength": sunlight_strength,
        "windMax": max(wind),
        "windBits": wind_bits,
        "highMax": max(highs),
        "lowMin": min(lows),
        "rainMax": max(rain),
        "rainAvg": sum(rain) / len(rain),
        "sunAvg": sum(sun) / len(sun),
    }


def risk_class(south, north):
    rain_max = max(south["rainMax"], north["rainMax"])
    wind_max = max(south["windMax"], north["windMax"])
    high_max = max(south["highMax"], north["highMax"])
    if rain_max >= 50 or wind_max >= 7 or high_max >= 37:
        return "high", "高"
    if rain_max >= 12 or wind_max >= 5 or high_max >= 34:
        return "medium", "中"
    return "low", "低"


def tag_for(south, north):
    rain_max = max(south["rainMax"], north["rainMax"])
    high_max = max(south["highMax"], north["highMax"])
    sun_avg = (south["sunAvg"] + north["sunAvg"]) / 2
    if rain_max >= 12:
        return "rain"
    if high_max >= 34:
        return "heat"
    if sun_avg >= 6:
        return "sun"
    return "mixed"


def price_forecast(south, north, forecast_date):
    rain_max = max(south["rainMax"], north["rainMax"])
    high_max = max(south["highMax"], north["highMax"])
    sun_avg = (south["sunAvg"] + north["sunAvg"]) / 2
    wind_max = max(south["windMax"], north["windMax"])
    weekend = forecast_date.weekday() >= 5
    confidence = "自动"
    if rain_max >= 25:
        title = "日前均价偏低至中性"
        peak = "强降雨压制空调负荷，实时波动增强"
        logic = "降雨和低光照削弱午后负荷，但光伏低出力、风电爬坡和局部阻塞会放大实时价差"
        action = "降低单纯高温多头，保留实时波动和阻塞风险保护"
        vol = "高"
    elif high_max >= 35 and sun_avg >= 5:
        title = "日前均价中性偏高"
        peak = "晴热高湿支撑午后和晚峰"
        logic = "高温推升空调负荷，若午间光照强则光伏压低午间价，晚峰上行弹性更突出"
        action = "保留峰段上行敞口，午间注意光伏压价"
        vol = "中"
    elif sun_avg >= 6 and high_max < 33:
        title = "日前均价中性偏低"
        peak = "光伏出力较好，午间价格承压"
        logic = "晴到多云提升光伏供给，空调负荷弹性有限，低谷和午间价更容易走弱"
        action = "午间和谷段偏谨慎，晚峰按负荷修复程度处理"
        vol = "中"
    elif wind_max >= 6:
        title = "日前均价中性"
        peak = "大风增加风电预测偏差"
        logic = "风速偏高可能抬升沿海风电，但预测误差、备用需求和台风外围扰动会增加实时波动"
        action = "降低方向性仓位，重点盯风电偏差和通道约束"
        vol = "中"
    else:
        title = "日前均价中性"
        peak = "峰段随温度和云量小幅摆动"
        logic = "天气驱动不极端，价格更多取决于负荷修正、风光预测和机组可用率"
        action = "维持中性仓位，等待临近负荷和新能源预测确认"
        vol = "低"
    if weekend:
        peak += "，周末负荷弹性略弱"
        action = "周末降低仓位弹性；" + action
    return title, peak, vol, confidence, logic, action


def build_dynamic_rows(city_data):
    by_date = {}
    for group, cities in city_data.items():
        for item in cities:
            by_date.setdefault(item.forecast_date, {}).setdefault(group, []).append(item)
    rows = []
    for forecast_date in sorted(by_date)[:15]:
        south = region_summary(by_date[forecast_date].get("southJiangsu", []))
        north = region_summary(by_date[forecast_date].get("northJiangsu", []))
        if not (south and north):
            continue
        risk_code, risk_text = risk_class(south, north)
        tag = tag_for(south, north)
        title, peak, vol, confidence, logic, action = price_forecast(south, north, forecast_date)
        weather = (
            f"苏南：{south['weatherBits']}，{south['temp']}，最大风力约{south['windMax']}级；"
            f"苏北：{north['weatherBits']}，{north['temp']}，最大风力约{north['windMax']}级"
        )
        rain = (
            f"苏南 {south['rainRange'][0]}-{south['rainRange'][1]}mm，按天气现象估算；"
            f"苏北 {north['rainRange'][0]}-{north['rainRange'][1]}mm，按天气现象估算"
        )
        sunlight = (
            f"苏南 {south['sunRange'][0]:.1f}-{south['sunRange'][1]:.1f}h，{south['sunStrength']}；"
            f"苏北 {north['sunRange'][0]:.1f}-{north['sunRange'][1]:.1f}h，{north['sunStrength']}"
        )
        rows.append(
            f"<tr data-month='{forecast_date:%m}' data-risk='{risk_code}' data-tag='{tag}'>"
            f"<td>{forecast_date.isoformat()}</td><td>自动预报</td>"
            f"<td>{escape(weather)}</td><td>{escape(rain)}</td><td>{escape(sunlight)}</td>"
            f"<td><span class='risk {risk_code}'>{risk_text}</span></td>"
            f"<td><div class='forecast'><b>{escape(title)}</b><span>{escape(peak)}</span><small>波动：{escape(vol)}；置信：{escape(confidence)}</small></div></td>"
            f"<td>{escape(logic)}<br><strong>{escape(action)}</strong></td></tr>"
        )
    return rows


def existing_rows_after(html, cutoff):
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    if not tbody_match:
        return []
    rows = re.findall(r"<tr data-month='.*?</tr>", tbody_match.group(1), re.S)
    kept = []
    for row in rows:
        date_match = re.search(r"<td>(\d{4}-\d{2}-\d{2})</td>", row)
        if not date_match:
            continue
        try:
            row_date = date.fromisoformat(date_match.group(1))
        except ValueError:
            continue
        if row_date > cutoff:
            kept.append(row)
    return kept


def update_index(updated_at, page_url, dynamic_rows):
    html = INDEX.read_text(encoding="utf-8")
    html = re.sub(r"更新时间：[^。]+。", f"更新时间：{updated_at}。", html, count=1)
    html = re.sub(
        r"当前版本：[^。]+。",
        f"当前版本：{updated_at}。未来15天已由 GitHub Actions 自动刷新天气与电价预测。",
        html,
        count=1,
    )
    if page_url:
        html = html.replace("部署到 GitHub Pages 后自动显示正式网址", page_url)
    if dynamic_rows:
        cutoff = max(date.fromisoformat(re.search(r"<td>(\d{4}-\d{2}-\d{2})</td>", row).group(1)) for row in dynamic_rows)
        rows = dynamic_rows + existing_rows_after(html, cutoff)
        html = re.sub(r"<tbody>.*?</tbody>", "<tbody>" + "".join(rows) + "</tbody>", html, count=1, flags=re.S)
    INDEX.write_text(html, encoding="utf-8")


def main():
    updated_at = china_now()
    source_results = [fetch_source(name, url) for name, url in SOURCES]
    ok_count = sum(1 for item in source_results if item["status"] == "ok")
    city_data = {}
    forecast_errors = []
    for group, cities in CITY_GROUPS.items():
        city_data[group] = []
        for city, code in cities:
            forecasts, errors = fetch_city_forecast(city, code)
            city_data[group].extend(forecasts)
            forecast_errors.extend(errors)
    dynamic_rows = build_dynamic_rows(city_data)
    page_url = github_pages_url()
    payload = {
        "updatedAt": updated_at,
        "message": f"GitHub Actions 已于北京时间 {updated_at} 完成更新；权威气象源检查 {ok_count}/{len(source_results)} 个可访问；已自动重算未来 {len(dynamic_rows)} 天苏南/苏北天气、降雨、光照和现货电价倾向。",
        "pageUrl": page_url,
        "manualRunUrl": manual_run_url(),
        "sources": source_results,
        "autoForecast": {
            "days": len(dynamic_rows),
            "cities": CITY_GROUPS,
            "errors": forecast_errors,
            "model": "规则模型：基于中国天气网城市预报，按苏南/苏北聚合温度、降雨、光照和风速，再推导日前均价、峰段、波动和持仓动作。"
        },
        "forecastPolicy": {
            "southJiangsu": "优先跟踪高温高湿、降雨量、云量、光照时长/强度和沿江沿海风速，对峰段价格与光伏出力偏差做滚动修正。",
            "northJiangsu": "优先跟踪强降雨、台风残余环流、光照衰减、沿海风电波动和局部阻塞风险。",
            "spotPrice": "当前版本保留原有天气驱动预测框架，并用降雨量、光照时长/强度辅助判断空调负荷、光伏出力和午间价格弹性；真实出清价数值化需要接入负荷、风光、机组可用率、外来电和市场报价数据。"
        }
    }
    DATA.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_index(updated_at, page_url, dynamic_rows)
    print(json.dumps({"updatedAt": updated_at, "okSources": ok_count, "autoForecastRows": len(dynamic_rows), "pageUrl": page_url}, ensure_ascii=False))


if __name__ == "__main__":
    main()
