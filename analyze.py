import json

d = json.load(open('annotations.json', 'r', encoding='utf-8'))
relevant = [v for v in d.values() if v.get('relevant')]
not_relevant = [v for v in d.values() if not v.get('relevant')]

print('=== 你认为相关的10篇 ===')
for v in relevant[:10]:
    print(f"  [{v.get('ai_category','')}] {v['title'][:100]}")

print()
print('=== 你认为不相关的10篇 ===')
for v in not_relevant[:10]:
    print(f"  [{v.get('ai_category','')}] {v['title'][:100]}")