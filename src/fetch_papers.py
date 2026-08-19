import requests
import json
import os
import time
from datetime import datetime, timedelta
from functools import lru_cache
import xml.etree.ElementTree as ET
import re


# ============================================
# Configuration
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

RSS_FEEDS = [
    {
        "name": "野生动物学报",
        "url": "https://ysdw.nefu.edu.cn/rc-pub/front/rss?periodId=currentIssue&siteId=726",
    },
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

DAYS_BACK = 3

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def clean_translation(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:\w+)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip().strip('"“”\'')
    text = re.sub(r"^(中文翻译|翻译|译文|标题翻译)[:：]\s*", "", text)
    return text.strip()


def contains_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


@lru_cache(maxsize=1000)
def translate_title(title):
    """Translate a paper title with DeepSeek API."""
    title = (title or "").strip()
    if not title:
        return ""
    if contains_chinese(title):
        return title
    if not DEEPSEEK_API_KEY:
        print("    No DEEPSEEK_API_KEY, skip title translation")
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
            response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            choices = result.get("choices") or []
            if choices:
                translation = clean_translation(
                    (choices[0].get("message") or {}).get("content", "")
                )
                if translation:
                    print(f"    DeepSeek translated: {translation[:40]}...")
                    return translation
            print(f"    DeepSeek returned empty translation (attempt {attempt + 1})")
        except requests.HTTPError as e:
            body = e.response.text[:300] if e.response is not None else ""
            print(f"    DeepSeek HTTP error (attempt {attempt + 1}): {e} {body}")
        except Exception as e:
            print(f"    DeepSeek translation failed (attempt {attempt + 1}): {e}")
        time.sleep(3)

    print(f"    Title translation failed: {title[:60]}...")
    return ""


def fetch_papers():
    all_papers = []
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS_BACK)
    start_str = start_date.strftime("%Y/%m/%d")
    end_str = end_date.strftime("%Y/%m/%d")

    for journal in JOURNALS:
        print(f"Fetching {journal}...")

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
            f"?db=pubmed&term={search_query}&retmax=50&retmode=json"
            f"&mindate={start_str}&maxdate={end_str}&datetype=pdat"
        )

        for attempt in range(3):
            try:
                time.sleep(1.5)
                resp = requests.get(search_url, timeout=30)
                resp.raise_for_status()
                search_data = resp.json()
                id_list = search_data.get("esearchresult", {}).get("idlist", [])
                break
            except Exception as e:
                print(f"  {journal}: search attempt {attempt+1} failed - {e}")
                id_list = []
                time.sleep(5)

        if not id_list:
            print(f"  {journal}: No new papers")
            continue

        print(f"  {journal}: Found {len(id_list)} papers, fetching details...")

        papers = []
        for attempt in range(3):
            try:
                time.sleep(1.5)
                ids = ",".join(id_list)
                fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
                resp = requests.get(fetch_url, timeout=30)
                resp.raise_for_status()
                papers = parse_pubmed_xml(resp.text, journal)
                break
            except Exception as e:
                print(f"  {journal}: fetch attempt {attempt+1} failed - {e}")
                time.sleep(5)

        print(f"  {journal}: {len(papers)} papers parsed")
        all_papers.extend(papers)

    return all_papers


def fetch_rss_papers():
    papers = []
    for feed in RSS_FEEDS:
        print(f"Fetching {feed['name']} via RSS...")
        try:
            resp = requests.get(feed["url"], timeout=30)
            resp.raise_for_status()
            feed_papers = parse_rss(resp.text, feed["name"])
            papers.extend(feed_papers)
            print(f"  {feed['name']}: {len(feed_papers)} papers")
        except Exception as e:
            print(f"  {feed['name']}: Failed - {e}")
    return papers


def parse_rss(xml_text, journal_name):
    papers = []
    root = ET.fromstring(xml_text)
    for item in root.findall(".//item"):
        try:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date_elem = item.find("pubDate")
            pub_date = ""
            if pub_date_elem is not None and pub_date_elem.text:
                pub_date = pub_date_elem.text.strip()
                try:
                    pub_date = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y-%m-%d")
                except:
                    try:
                        pub_date = datetime.strptime(pub_date[:11], "%a, %d %b %Y").strftime("%Y-%m-%d")
                    except:
                        pub_date = ""

            description = item.find("description").text if item.find("description") is not None else ""
            abstract = re.sub(r'<[^>]+>', '', description)[:500]

            papers.append({
                "title": title.strip(),
                "title_cn": "",
                "title_cn_summary": "",
                "journal": journal_name,
                "date": pub_date,
                "authors": "",
                "abstract": abstract,
                "doi": "",
                "url": link,
                "pmid": f"ysdw-{title[:30]}",
                "category": "",
            })
        except Exception:
            continue
    return papers


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


def ai_filter_papers(papers):
    """Use DeepSeek to filter papers based on wildlife relevance."""
    if not DEEPSEEK_API_KEY:
        print("  No DEEPSEEK_API_KEY, falling back to keyword filter")
        return filter_by_keywords(papers)

    filtered = []
    system_prompt = (
        "你是野生动物学和生命科学领域的论文评审专家。"
        "请判断论文是否与野生脊椎动物研究直接相关。"
        "只返回 YES 或 NO，不要解释。"
    )

    for paper in papers:
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
            response = requests.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 10,
                    "temperature": 0.1,
                },
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            content = clean_translation(
                (result.get("choices", [{}])[0].get("message") or {}).get("content", "")
            ).upper()

            if content == "YES":
                text = (paper["title"] + " " + paper["abstract"]).lower()
                matched = [kw for kw in KEYWORDS if kw.lower() in text]
                paper["category"] = get_category(matched[0]) if matched else "zoology"
                filtered.append(paper)
                print(f"    DeepSeek KEEP: {paper['title'][:60]}...")
            else:
                print(f"    DeepSeek SKIP: {paper['title'][:60]}...")
        except Exception as e:
            print(f"    DeepSeek filter failed: {e}")
            text = (paper["title"] + " " + paper["abstract"]).lower()
            if any(kw.lower() in text for kw in KEYWORDS):
                filtered.append(paper)

    return filtered


def filter_by_keywords(papers):
    filtered = []
    for paper in papers:
        text = (paper["title"] + " " + paper["abstract"]).lower()
        matched_keywords = []
        for kw in KEYWORDS:
            if kw.lower() in text:
                matched_keywords.append(kw)
                if len(matched_keywords) >= 3:
                    break
        if len(matched_keywords) >= 1:
            paper["category"] = get_category(matched_keywords[0])
            paper["match_count"] = len(matched_keywords)
            paper["is_hot"] = len(matched_keywords) >= 3
            filtered.append(paper)
    return filtered


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


def translate_papers(papers):
    """Translate selected paper titles after AI filtering."""
    untranslated = [paper for paper in papers if not paper.get("title_cn") and paper.get("title")]
    print(f"\nTranslating {len(untranslated)} selected paper titles with DeepSeek...")

    for index, paper in enumerate(untranslated, start=1):
        paper["title_cn"] = translate_title(paper["title"])
        if paper["title_cn"]:
            print(f"    [{index}/{len(untranslated)}] OK: {paper['title'][:50]}...")
        else:
            print(f"    [{index}/{len(untranslated)}] FAILED: {paper['title'][:50]}...")

    return papers


if __name__ == "__main__":
    print("=" * 50)
    print("Fetching latest wildlife science papers...")
    print(f"Date range: last {DAYS_BACK} days")
    print("=" * 50)

    papers = fetch_papers()
    rss_papers = fetch_rss_papers()
    papers.extend(rss_papers)

    print(f"\nTotal raw papers: {len(papers)}")

    print("\nAI filtering papers...")
    papers = ai_filter_papers(papers)

    seen = set()
    unique_papers = []
    for p in papers:
        if p["pmid"] not in seen:
            seen.add(p["pmid"])
            unique_papers.append(p)

    unique_papers = translate_papers(unique_papers)
    print(f"\nAfter AI filtering: {len(unique_papers)} papers")

    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "papers.json")

    existing_papers = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_papers = json.load(f)
        except:
            pass

    existing_pmids = {p.get("pmid", "") for p in existing_papers}
    for p in unique_papers:
        if p["pmid"] not in existing_pmids:
            existing_papers.insert(0, p)
            existing_pmids.add(p["pmid"])

    existing_papers = existing_papers[:3000]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_papers, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_path} (total {len(existing_papers)} papers)")

    print("\nBuilding site...")
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)
    os.system("npm run build")
    print("Build complete!")