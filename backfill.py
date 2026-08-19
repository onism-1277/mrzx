import requests
import json
import os
import time
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import re

# ============================================
# Backfill Configuration
# ============================================

JOURNALS = [
    "Nature",
    "Science",
    "Proc Natl Acad Sci U S A",
    "Sci Adv",
    "Nat Commun",
    "Mol Biol Evol",
    "Gene",
    "Biol Conserv",
    "Conserv Biol",
    "Front Ecol Environ",
    "J Wildl Manage",
    "Wildl Monogr",
    "Eur J Wildl Res",
    "Wildl Biol",
    "J Mammal",
    "J Zool",
    "Zool Res",
]

KEYWORDS = [
    "zoology", "animal", "wildlife", "mammal", "avian", "bird",
    "fauna", "vertebrate", "migration", "migratory",
    "hibernation", "home range", "reproduction", "reproductive",
    "ecology", "ecological", "ecosystem",
    "population", "habitat", "environmental DNA", "eDNA",
    "genomics", "genetics", "genome",
    "evolution", "evolutionary", "phylogenetic",
    "population genetics", "gene flow", "genetic drift",
    "bioinformatics", "computational biology", "sequence analysis", "MaxEnt",
    "conservation", "biodiversity", "endangered species",
    "threatened species", "wildlife management", "red list", "IUCN",
    "extinction risk", "poach", "poaching", "wildlife trade",
    "non-invasive sampling", "noninvasive sampling",
    "behavior", "behaviour", "ethology",
    "paleontology", "fossil",
    "biogeography", "species distribution",
    "taxonomy", "classification",
    "biotechnology", "genetic engineering", "CRISPR",
]

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

START_DATE = "2026/06/01"


def clean_translation(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip().strip('"“”\'')
    text = re.sub(r"^(中文翻译|翻译|译文|标题翻译)[:：]\s*", "", text)
    return text.strip()


def translate_title(title):
    if not DEEPSEEK_API_KEY or not title:
        return ""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "deepseek-chat",
        "messages": [
            {
                "role": "system",
                "content": "你是专业生命科学翻译。请将论文标题准确翻译为中文，只返回译文，不要解释。",
            },
            {"role": "user", "content": title},
        ],
        "max_tokens": 100,
        "temperature": 0.3,
    }

    for attempt in range(3):
        try:
            time.sleep(1.2)
            resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            choices = result.get("choices") or []
            if choices:
                translation = clean_translation(
                    (choices[0].get("message") or {}).get("content", "")
                )
                if translation:
                    return translation
            print(f"    Empty translation (attempt {attempt+1})")
        except Exception as e:
            print(f"    Translation attempt {attempt+1} failed: {e}")
        time.sleep(3)

    return ""


def ai_filter(paper):
    if not DEEPSEEK_API_KEY:
        text = (paper["title"] + " " + paper["abstract"]).lower()
        return any(kw.lower() in text for kw in KEYWORDS)

    prompt = f"""请判断下面的论文是否属于野生脊椎动物研究。

可以保留的主题：
- 野生哺乳动物、鸟类、爬行动物、两栖动物和鱼类的生态学
- 野生动物保护、生物多样性和濒危物种
- 人兽冲突和野生动物管理
- 野生动物疾病和健康
- 野生脊椎动物的遗传学、基因组学和进化
- 可应用于野生动物研究的技术和方法

应当排除的主题：
- 植物、农业和园艺
- 家畜、宠物等家养动物，除非明确涉及野生动物
- 与野生动物无关的人类医学
- 没有动物或野生动物应用场景的纯分子生物学
- 海洋无脊椎动物

论文标题：{paper['title']}
论文摘要：{paper['abstract'][:500]}

只返回 YES 或 NO。"""

    try:
        time.sleep(1.2)
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是野生动物学论文评审专家。只返回 YES 或 NO。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 10,
                "temperature": 0.1,
            },
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        content = clean_translation(
            (result.get("choices", [{}])[0].get("message") or {}).get("content", "")
        ).upper()
        return content == "YES"
    except Exception as e:
        print(f"    AI filter failed: {e}")
        text = (paper["title"] + " " + paper["abstract"]).lower()
        return any(kw.lower() in text for kw in KEYWORDS)


def get_category(keyword):
    kw = keyword.lower()
    if kw in ["zoology", "animal", "wildlife", "mammal", "avian", "bird",
              "fauna", "vertebrate", "migration", "migratory",
              "hibernation", "home range", "reproduction", "reproductive"]:
        return "zoology"
    elif kw in ["ecology", "ecological", "ecosystem", "population",
                "habitat", "environmental dna", "edna"]:
        return "ecology"
    elif kw in ["genomics", "genetics", "genome"]:
        return "genetics"
    elif kw in ["evolution", "evolutionary", "phylogenetic"]:
        return "evolution"
    elif kw in ["population genetics", "gene flow", "genetic drift"]:
        return "population genetics"
    elif kw in ["bioinformatics", "computational biology", "sequence analysis", "maxent"]:
        return "bioinformatics"
    elif kw in ["conservation", "biodiversity", "endangered species",
                "threatened species", "wildlife management", "red list", "iucn",
                "extinction risk", "poach", "poaching", "wildlife trade",
                "non-invasive sampling", "noninvasive sampling"]:
        return "conservation"
    elif kw in ["behavior", "behaviour", "ethology"]:
        return "behavior"
    elif kw in ["paleontology", "fossil"]:
        return "paleontology"
    elif kw in ["biogeography", "species distribution"]:
        return "biogeography"
    elif kw in ["taxonomy", "classification"]:
        return "taxonomy"
    elif kw in ["biotechnology", "genetic engineering", "crispr"]:
        return "biotechnology"
    return "other"


def fetch_backfill():
    all_papers = []
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    end_str = datetime.now().strftime("%Y/%m/%d")

    for journal in JOURNALS:
        print(f"\n{'='*50}")
        print(f"Fetching {journal} from {START_DATE} to {end_str}...")
        print(f"{'='*50}")

        search_query = (
            f'"{journal}"[Journal] AND ('
            f'zoology[MeSH] OR ecology[MeSH] OR genetics[MeSH] OR '
            f'evolution[MeSH] OR genetics, population[MeSH] OR '
            f'computational biology[MeSH] OR conservation of natural resources[MeSH] OR '
            f'behavior, animal[MeSH] OR paleontology[MeSH] OR biogeography[MeSH] OR '
            f'classification[MeSH] OR biotechnology[MeSH]'
            f')'
        )
        search_url = (
            f"{base_url}/esearch.fcgi"
            f"?db=pubmed&term={search_query}&retmax=200&retmode=json"
            f"&mindate={START_DATE}&maxdate={end_str}&datetype=pdat"
        )

        for attempt in range(3):
            try:
                time.sleep(2)
                resp = requests.get(search_url, timeout=60)
                resp.raise_for_status()
                search_data = resp.json()
                id_list = search_data.get("esearchresult", {}).get("idlist", [])
                total_count = int(search_data.get("esearchresult", {}).get("count", 0))
                break
            except Exception as e:
                print(f"  Search attempt {attempt+1} failed: {e}")
                id_list = []
                total_count = 0
                time.sleep(5)

        if not id_list:
            print(f"  {journal}: No papers found")
            continue

        print(f"  {journal}: {total_count} total papers, fetched {len(id_list)}")

        for i in range(0, len(id_list), 100):
            batch = id_list[i:i+100]

            for attempt in range(3):
                try:
                    time.sleep(2)
                    ids = ",".join(batch)
                    fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
                    resp = requests.get(fetch_url, timeout=60)
                    resp.raise_for_status()
                    papers = parse_pubmed_xml(resp.text, journal)
                    all_papers.extend(papers)
                    print(f"    Batch {i//100 + 1}: {len(papers)} papers parsed")
                    break
                except Exception as e:
                    print(f"    Fetch attempt {attempt+1} failed: {e}")
                    time.sleep(5)

    return all_papers


def parse_pubmed_xml(xml_text, journal):
    papers = []
    root = ET.fromstring(xml_text)
    for article in root.findall(".//PubmedArticle"):
        try:
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""
            if not title:
                continue

            abstract_parts = []
            for abs_elem in article.findall(".//AbstractText"):
                label = abs_elem.get("Label", "")
                text = abs_elem.text or ""
                abstract_parts.append(f"{label}: {text}" if label else text)
            abstract = " ".join(abstract_parts)

            doi = ""
            for eid in article.findall(".//ELocationID"):
                if eid.get("EIdType") == "doi":
                    doi = eid.text or ""

            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            pub_date = ""
            date_elem = article.find(".//PubDate")
            if date_elem is not None:
                year = date_elem.find("Year")
                month = date_elem.find("Month")
                day = date_elem.find("Day")
                y = year.text if year is not None else ""
                m = month.text if month is not None else "01"
                d = day.text if day is not None else "01"
                try:
                    m = str(datetime.strptime(m, "%b").month).zfill(2)
                except:
                    pass
                pub_date = f"{y}-{m.zfill(2) if len(m) < 2 else m}-{d.zfill(2) if len(d) < 2 else d}"

            if doi:
                url = f"https://doi.org/{doi}"
            else:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            authors = []
            for author in article.findall(".//Author"):
                last = author.find("./LastName")
                init = author.find("./Initials")
                if last is not None:
                    name = last.text or ""
                    if init is not None and init.text:
                        name += f" {init.text}"
                    authors.append(name)
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += " et al."

            papers.append({
                "title": title.strip(),
                "title_cn": "",
                "title_cn_summary": "",
                "journal": journal,
                "date": pub_date,
                "authors": author_str,
                "abstract": abstract.strip()[:500],
                "doi": doi,
                "url": url,
                "pmid": pmid,
                "category": "",
            })

        except Exception:
            continue

    return papers


if __name__ == "__main__":
    print("=" * 60)
    print("Backfill: 2026-06-01 to today")
    print("=" * 60)

    papers = fetch_backfill()
    print(f"\nTotal raw papers: {len(papers)}")

    # 去重
    seen = set()
    unique_raw = []
    for p in papers:
        if p["pmid"] not in seen:
            seen.add(p["pmid"])
            unique_raw.append(p)
    print(f"After dedup: {len(unique_raw)}")

    # AI filter + translate
    print("\nAI filtering and translating...")
    filtered = []
    for i, paper in enumerate(unique_raw, 1):
        if ai_filter(paper):
            text = (paper["title"] + " " + paper["abstract"]).lower()
            matched = [kw for kw in KEYWORDS if kw.lower() in text]
            paper["category"] = get_category(matched[0]) if matched else "zoology"
            paper["title_cn"] = translate_title(paper["title"])
            filtered.append(paper)
            print(f"  [{i}/{len(unique_raw)}] KEEP: {paper['title'][:50]}...")
        else:
            print(f"  [{i}/{len(unique_raw)}] SKIP")

    # 保存
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "papers.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(filtered)} papers to {output_path}")
    print("Backfill complete!")