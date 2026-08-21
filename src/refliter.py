import json
import os
import re
import time
import requests

# 获取 API Key 并清理可能的非 ASCII 字符
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()

# 如果环境变量为空，请务必在这里填入你真正的 sk-xxx Key（不要保留中文字符）
if not DEEPSEEK_API_KEY or "你的Key" in DEEPSEEK_API_KEY:
    DEEPSEEK_API_KEY = "sk-1"  # 请替换为你的真实 API Key

# 过滤掉所有非 ASCII 字符，防止 latin-1 编码报错
DEEPSEEK_API_KEY = re.sub(r"[^\x00-\x7F]+", "", DEEPSEEK_API_KEY).strip()

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
PAPERS_PATH = "D:/11433/VScode/mrzx/src/data/papers.json"


def ai_filter(paper):
    prompt = f"""You are a wildlife biologist reviewing papers for a database focused exclusively on WILD VERTEBRATES.

INCLUDE only if the paper DIRECTLY studies one or more of:
- Wild mammals, birds, reptiles, amphibians, or fish
- Their ecology, behavior, conservation, management, or trade
- Their diseases, genetics, or evolution
- Human-wildlife conflict involving these animals
- Methods specifically designed for studying these animals

EXCLUDE if the paper is primarily about:
- Plants, fungi, or agriculture
- Invertebrates (insects, snails, copepods, corals, etc.)
- Humans only (social science, policy without direct wildlife focus)
- Domestic animals, livestock, or pets
- General environmental science without a specific wild vertebrate focus
- Laboratory studies without wild animal application

Examples of EXCLUDE:
- Climate change impacts on reptile embryos (too narrow, lab-based)
- Threatened plants (plants)
- Marine snail movement (invertebrate)
- Corporate biodiversity losses (no specific animal)

Examples of INCLUDE:
- Avian body condition in logged tropical forest (birds)
- Bat roost conservation (mammals)
- IUCN Red List threat attribution (wildlife conservation)
- Wildlife trafficking detection dogs (wildlife trade)

Paper Title: {paper.get('title', '')}
Paper Abstract: {paper.get('abstract', '')[:500]}

Answer with ONLY ONE WORD: YES or NO"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a wildlife biology expert. Return only YES or NO."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 10,
        "temperature": 0.1
    }

    for attempt in range(3):
        try:
            time.sleep(1)
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            content = (result.get("choices", [{}])[0].get("message") or {}).get("content", "").strip().upper()
            return content == "YES"
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            time.sleep(2)
    return False


# 检查并读取文件
if not os.path.exists(PAPERS_PATH):
    print(f"错误: 找不到文件 {PAPERS_PATH}")
    exit(1)

with open(PAPERS_PATH, "r", encoding="utf-8") as f:
    papers = json.load(f)

print(f"Total papers: {len(papers)}")

kept = []
for i, paper in enumerate(papers, 1):
    result = ai_filter(paper)
    status = "KEEP" if result else "SKIP"
    print(f"[{i}/{len(papers)}] {status}: {paper.get('title', '')[:60]}...")
    if result:
        kept.append(paper)

print(f"\nKept: {len(kept)} / {len(papers)} ({len(kept)/len(papers)*100:.1f}%)")

output_path = "D:/11433/VScode/mrzx/src/data/papers_filtered.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(kept, f, ensure_ascii=False, indent=2)

print(f"Saved to {output_path}")