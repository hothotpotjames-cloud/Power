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
2. 更新 `data/latest.json`。
3. 更新 `index.html` 中的更新时间。
4. 由 GitHub Actions 自动提交回仓库。

后续可继续增强脚本，把网页中的每日天气和电价预测表按最新天气预报重新生成。
