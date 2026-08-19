import json
import os
import time
import requests
import sys

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()

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
            {
                "role": "system",
                "content": "You are a professional life science translator. Translate the paper title to Chinese. Return only the translation."
            },
            {"role": "user", "content": title}
        ],
        "max_tokens": 100,
        "temperature": 0.3
    }

    payload = json.dumps(data, ensure_ascii=True).encode("ascii")

    for attempt in range(3):
        try:
            time.sleep(1)
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, data=payload, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            choices = result.get("choices") or []
            if choices:
                translation = (choices[0].get("message") or {}).get("content", "").strip()
                if translation:
                    return translation
        except Exception:
            pass
        time.sleep(2)

    return ""


with open(PAPERS_PATH, "r", encoding="utf-8") as f:
    papers = json.load(f)

untranslated = [p for p in papers if not p.get("title_cn")]
print(f"Total: {len(papers)}, Untranslated: {len(untranslated)}")

for i, p in enumerate(untranslated, 1):
    p["title_cn"] = translate_title(p["title"])
    ok = "OK" if p["title_cn"] else "FAIL"
    print(f"[{i}/{len(untranslated)}] {ok}")

with open(PAPERS_PATH, "w", encoding="utf-8") as f:
    json.dump(papers, f, ensure_ascii=False, indent=2)

print("Done!")