import json
import os
import time
import requests

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
if not DEEPSEEK_API_KEY:
    DEEPSEEK_API_KEY = "你的Key"

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
- "Differences in climate change impacts on reptile embryos" (too narrow, lab-based)
- "Threatened plants" (plants)
- "Marine snail movement" (invertebrate)
- "Corporate biodiversity losses" (no specific animal)

Examples of INCLUDE:
- "Avian body condition in logged tropical forest" (birds)
- "Bat roost conservation" (mammals)
- "IUCN Red List threat attribution" (wildlife conservation)
- "Wildlife trafficking detection dogs" (wildlife trade)

Paper Title: {paper['title']}
Paper Abstract: {paper['abstract'][:500]}

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


# Read papers
with open(PAPERS_PATH, "r", encoding="utf-8") as f:
    papers = json.load(f)

print(f"Total papers: {len(papers)}")

# Refilter
kept = []
for i, paper in enumerate(papers, 1):
    result = ai_filter(paper)
    status = "KEEP" if result else "SKIP"
    print(f"[{i}/{len(papers)}] {status}: {paper['title'][:60]}...")
    if result:
        kept.append(paper)

print(f"\nKept: {len(kept)} / {len(papers)} ({len(kept)/len(papers)*100:.1f}%)")

# Save filtered result
output_path = "D:/11433/VScode/mrzx/src/data/papers_filtered.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(kept, f, ensure_ascii=False, indent=2)

print(f"Saved to {output_path}")