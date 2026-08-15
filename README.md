# GitHub 星榜

每日更新的 GitHub 开源项目 Star 排行榜，界面与项目简介均为中文。

在线访问：https://yaowenhu-pm.github.io/github-ranking-cn/

## 榜单

- 总榜 Top 100（按 star 数）
- 语言分榜：Python / JavaScript / TypeScript / Go / Java / Rust 各 Top 100
- 每行显示较前一日的排名升降（升 / 降 / 持平 / 新上榜）

## 工作原理

1. GitHub Actions 每日 08:30（北京时间）运行 [scripts/update.py](scripts/update.py)
2. 通过 GitHub Search API 拉取各榜单 Top 100
3. 新入榜项目的英文简介由 DeepSeek 翻译成中文，结果缓存在 [data/translations.json](data/translations.json)，已翻过的不再重复调用
4. 生成 [data/rankings.json](data/rankings.json) 并提交，GitHub Pages 自动发布

前端为纯静态页面（无框架、无构建），样式为纸质榜单风格。

## 本地运行

```bash
export GITHUB_TOKEN=xxx        # 可选，提高 API 配额
export DEEPSEEK_API_KEY=xxx    # 可选，缺失时简介保留英文
python3 scripts/update.py
python3 -m http.server 8646    # 打开 http://localhost:8646
```

## 致谢

数据思路来自 [EvanLi/Github-Ranking](https://github.com/EvanLi/Github-Ranking)。
