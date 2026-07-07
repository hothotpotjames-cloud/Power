# 江苏电力现货天气看板 - GitHub Pages 版

这个仓库用于托管江苏天气与现货电价预测看板。

## 自动更新

`.github/workflows/update-dashboard.yml` 已配置：

- 北京时间 08:30 自动运行
- 北京时间 15:30 自动运行
- 支持在 GitHub Actions 页面手动点击 `Run workflow`

GitHub Actions 的 cron 使用 UTC，所以配置为：

- `30 0 * * *`
- `30 7 * * *`

## GitHub Pages

部署后访问地址通常为：

```text
https://<你的GitHub用户名>.github.io/<仓库名>/
```

## 启用步骤

1. 把本目录所有文件提交到 GitHub 仓库。
2. 进入仓库 `Settings -> Pages`。
3. Source 选择 `Deploy from a branch`。
4. Branch 选择 `main`，目录选择 `/root`。
5. 保存后等待 Pages 发布。
6. 进入 `Actions`，确认 `Update Jiangsu Power Weather Dashboard` workflow 可运行。

## 当前脚本做了什么

`scripts/update_dashboard.py` 会：

1. 检查中国气象局、中国天气网、中央气象台台风网等权威来源是否可访问。
2. 抓取南京、苏州、徐州、连云港的 7 天和 8-15 天天气预报。
3. 按苏南/苏北聚合温度、降雨、光照时长/强度和风速。
4. 用规则模型重算未来 15 天现货电价倾向、波动等级和持仓提示。
5. 更新 `data/latest.json` 和 `index.html` 中的每日天气-电价预测日历。
6. 由 GitHub Actions 自动提交回仓库。

远期 15 天以后的 7-12 月内容仍保留为气候情景参考，不作为逐日确定性天气预报。
