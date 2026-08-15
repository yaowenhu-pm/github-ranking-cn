#!/usr/bin/env python3
"""拉取 GitHub Star 排行数据，翻译简介，生成 data/rankings.json。

每日由 GitHub Actions 调用；本地调试直接运行。
环境变量：
  GITHUB_TOKEN      可选，提高 API 配额
  DEEPSEEK_API_KEY  可选，缺失时简介保留英文原文
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
RANKINGS_PATH = os.path.join(DATA_DIR, "rankings.json")
TRANSLATIONS_PATH = os.path.join(DATA_DIR, "translations.json")

# (榜单 key, 中文名, GitHub search 查询)
LISTS = [
    ("overall", "总榜", "stars:>10000"),
    ("python", "Python", "language:Python stars:>1000"),
    ("javascript", "JavaScript", "language:JavaScript stars:>1000"),
    ("typescript", "TypeScript", "language:TypeScript stars:>1000"),
    ("go", "Go", "language:Go stars:>1000"),
    ("java", "Java", "language:Java stars:>1000"),
    ("rust", "Rust", "language:Rust stars:>1000"),
]

TRANSLATE_BATCH = 25
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U0001F900-\U0001F9FF☀-➿⬀-⯿️‍]+"
)


def strip_emoji(text):
    return re.sub(r"\s{2,}", " ", EMOJI_RE.sub("", text)).strip(" :：-—·|")


def http_json(url, headers=None, payload=None, retries=3):
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == retries - 1:
                raise
            print(f"  请求失败({e})，{2 ** attempt}s 后重试", file=sys.stderr)
            time.sleep(2 ** attempt)


def gh_search(query):
    headers = {
        "User-Agent": "github-ranking-cn",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = (
        "https://api.github.com/search/repositories"
        f"?q={urllib.request.quote(query)}&sort=stars&order=desc&per_page=100"
    )
    result = http_json(url, headers=headers)
    return result["items"]


def load_json(path, default):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def translate_batch(items, api_key):
    """items: [(full_name, description)] -> {full_name: 中文简介}"""
    numbered = "\n".join(f"{i + 1}. {desc}" for i, (_, desc) in enumerate(items))
    prompt = (
        "下面是若干条 GitHub 开源项目的英文简介，逐条翻译成简洁自然的中文，"
        "保留产品名、技术名词原文不译。只输出 JSON 数组，第 i 个元素是第 i 条的译文，"
        "不要输出其他内容。\n\n" + numbered
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    resp = http_json(DEEPSEEK_URL, headers=headers, payload=payload)
    text = resp["choices"][0]["message"]["content"].strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("["):]
    translations = json.loads(text[text.find("["): text.rfind("]") + 1])
    if len(translations) != len(items):
        raise ValueError(f"译文条数 {len(translations)} 与原文 {len(items)} 不符")
    return {items[i][0]: t for i, t in enumerate(translations)}


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    old = load_json(RANKINGS_PATH, {})
    prev_ranks = {
        key: {r["full_name"]: r["rank"] for r in lst}
        for key, lst in old.get("lists", {}).items()
    }
    cache = load_json(TRANSLATIONS_PATH, {})
    # 历史缓存里可能带 emoji，统一清洗，避免误判为"简介已变"而重复翻译
    for entry in cache.values():
        entry["en"] = strip_emoji(entry["en"])
        entry["zh"] = strip_emoji(entry["zh"])

    lists = {}
    seen = {}  # full_name -> repo dict（跨榜去重，翻译只做一次）
    for key, cn_name, query in LISTS:
        print(f"拉取 {cn_name} ...")
        items = gh_search(query)
        rows = []
        for rank, it in enumerate(items, 1):
            full_name = it["full_name"]
            row = {
                "rank": rank,
                "full_name": full_name,
                "url": it["html_url"],
                "desc_en": strip_emoji(it["description"] or ""),
                "stars": it["stargazers_count"],
                "forks": it["forks_count"],
                "language": it["language"] or "",
                "prev_rank": prev_ranks.get(key, {}).get(full_name),
            }
            rows.append(row)
            seen.setdefault(full_name, row)
        lists[key] = rows
        time.sleep(3)  # search API 限流 10 次/分钟（未认证）

    # 增量翻译：只翻缓存里没有、或英文简介变了的
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    pending = [
        (fn, row["desc_en"])
        for fn, row in seen.items()
        if row["desc_en"] and cache.get(fn, {}).get("en") != row["desc_en"]
    ]
    if pending and not api_key:
        print(f"未配置 DEEPSEEK_API_KEY，{len(pending)} 条简介保留英文", file=sys.stderr)
    elif pending:
        print(f"翻译 {len(pending)} 条新简介 ...")
        for i in range(0, len(pending), TRANSLATE_BATCH):
            batch = pending[i: i + TRANSLATE_BATCH]
            try:
                result = translate_batch(batch, api_key)
            except Exception as e:
                print(f"  批次翻译失败，保留英文：{e}", file=sys.stderr)
                continue
            for fn, zh in result.items():
                cache[fn] = {"en": seen[fn]["desc_en"], "zh": strip_emoji(zh)}
            print(f"  {min(i + TRANSLATE_BATCH, len(pending))}/{len(pending)}")

    for rows in lists.values():
        for row in rows:
            row["desc_zh"] = cache.get(row["full_name"], {}).get("zh", "")

    out = {
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "lists": lists,
    }
    with open(TRANSLATIONS_PATH, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1)
    with open(RANKINGS_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False)
    total = sum(len(v) for v in lists.values())
    print(f"完成：{len(lists)} 个榜单，{total} 行，独立项目 {len(seen)} 个")


if __name__ == "__main__":
    main()
