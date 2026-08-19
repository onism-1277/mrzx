import json
import os
import time
import requests

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def translate_title(title):
    if not DEEPSEEK_API_KEY or not title:
        return ""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是专业生命科学翻译。请将论文标题准确翻译为中文，只返回译文，不要解释。"},
            {"role": "user", "content": title}
        ],
        "max_tokens": 100,
        "temperature": 0.3
    }
    for attempt in range(3):
        try:
            time.sleep(1)
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            result = resp.json()
            choices = result.get("choices") or []
            if choices:
                return (choices[0].get("message") or {}).get("content", "").strip()
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return ""


# 读取
with open("src/data/papers.json", "r", encoding="utf-8") as f:
    papers = json.load(f)

# 找未翻译的
untranslated = [p for p in papers if not p.get("title_cn")]
print(f"Total: {len(papers)}, untranslated: {len(untranslated)}")

# 翻译
for i, p in enumerate(untranslated, 1):
    p["title_cn"] = translate_title(p["title"])
    print(f"[{i}/{len(untranslated)}] {p['title'][:40]}... -> {p['title_cn'][:30]}")

# 保存
with open("src/data/papers.json", "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)

print("Done!")