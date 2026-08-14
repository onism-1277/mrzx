import requests
import json
import os
from datetime import datetime, timedelta
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

# RSS feeds for Chinese journals
RSS_FEEDS = [
    {
        "name": "野生动物学报",
        "url": "https://ysdw.nefu.edu.cn/rc-pub/front/rss?periodId=currentIssue&siteId=726",
    },
]

KEYWORDS = [
    # 动物学
    "zoology", "animal", "wildlife", "mammal", "avian", "bird",
    "fauna", "vertebrate", "migration", "migratory",
    "hibernation", "home range", "reproduction", "reproductive",
    # 生态学
    "ecology", "ecological", "ecosystem",
    "population", "habitat", "environmental DNA", "eDNA",
    # 遗传学
    "genomics", "genetics", "genome",
    # 进化
    "evolution", "evolutionary", "phylogenetic",
    # 种群遗传学
    "population genetics", "gene flow", "genetic drift",
    # 生物信息学
    "bioinformatics", "computational biology", "sequence analysis", "MaxEnt",
    # 保护生物学
    "conservation", "biodiversity", "endangered species",
    "threatened species", "wildlife management", "red list", "IUCN",
    "extinction risk", "poach", "poaching", "wildlife trade",
    "non-invasive sampling", "noninvasive sampling",
    # 行为学
    "behavior", "behaviour", "ethology",
    # 古生物学
    "paleontology", "fossil",
    # 生物地理学
    "biogeography", "species distribution",
    # 分类学
    "taxonomy", "classification",
    # 生物技术
    "biotechnology", "genetic engineering", "CRISPR",
]

DAYS_BACK = 3


def translate_title(title):
    try:
        import google.generativeai as genai
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            print("No GEMINI_API_KEY found")
            return ""
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Translate the following paper title to Chinese. Return only the translation, no explanation:\n\n{title}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Translation failed: {e}")
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
        try:
            resp = requests.get(search_url, timeout=30)
            resp.raise_for_status()
            search_data = resp.json()
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                print(f"  {journal}: No new papers")
                continue
            print(f"  {journal}: Found {len(id_list)} papers, fetching details...")
            ids = ",".join(id_list)
            fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
            resp = requests.get(fetch_url, timeout=30)
            resp.raise_for_status()
            papers = parse_pubmed_xml(resp.text, journal)
            filtered = filter_by_keywords(papers)
            print(f"  {journal}: {len(filtered)} papers after filtering")
            all_papers.extend(filtered)
        except Exception as e:
            print(f"  {journal}: Failed - {e}")
    return all_papers

def fetch_rss_papers():
    papers = []
    for feed in RSS_FEEDS:
        print(f"Fetching {feed['name']} via RSS...")
        try:
            resp = requests.get(feed["url"], timeout=30)
            resp.raise_for_status()
            papers.extend(parse_rss(resp.text, feed["name"]))
            print(f"  {feed['name']}: {len(papers)} papers")
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

            title_cn = translate_title(title)

            papers.append({
                "title": title.strip(),
                "title_cn": title_cn,
                "journal": journal_name,
                "date": pub_date,
                "authors": "",
                "abstract": abstract,
                "doi": "",
                "url": link,
                "pmid": f"ysdw-{title[:30]}",
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
            title_cn = translate_title(title)
            if title_cn:
                print(f"    OK {title[:60]}... -> {title_cn[:40]}...")
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
                "title_cn": title_cn,
                "journal": journal,
                "date": pub_date,
                "authors": author_str,
                "abstract": abstract.strip()[:500],
                "doi": doi,
                "url": url,
                "pmid": pmid,
            })
        except Exception:
            continue
    return papers


def filter_by_keywords(papers):
    filtered = []
    for paper in papers:
        text = (paper["title"] + " " + paper["abstract"]).lower()
        matched_keywords = []
        for kw in KEYWORDS:
            if kw.lower() in text:
                matched_keywords.append(kw)
                if len(matched_keywords) >= 3:
                    break  # 找到3个就够，不必继续

        if len(matched_keywords) >= 1:
            paper["category"] = get_category(matched_keywords[0])
            paper["match_count"] = len(matched_keywords)
            paper["is_hot"] = len(matched_keywords) >= 3  # 3个以上标记为热点
            filtered.append(paper)
    return filtered


def ai_filter_papers(papers):
    """Use Gemini AI to filter papers based on wildlife relevance"""
    filtered = []
    for paper in papers:
        try:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                print("  No GEMINI_API_KEY, falling back to keyword filter")
                return filter_by_keywords(papers)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            prompt = f"""You are a wildlife biology expert. Determine if the following paper is relevant to WILD VERTEBRATE research.

Topics that ARE relevant:
- Basic ecology of wild vertebrates (mammals, birds, reptiles, amphibians, fish)
- Conservation of wild vertebrate species
- Human-wildlife interactions and conflict
- Wildlife diseases and health
- Genetics and evolution of wild vertebrates
- Technical methods applicable to wildlife research
- Wildlife policy, management, and planning

Topics that are NOT relevant:
- Plant biology or botany
- Domestic animals (livestock, pets) unless directly related to wildlife
- Human medicine (unless zoonotic disease from wildlife)
- Pure molecular biology without wildlife application
- Marine invertebrates

Paper Title: {paper['title']}
Paper Abstract: {paper['abstract'][:500]}

Answer with ONLY:
1. First line: YES or NO (is it relevant to wild vertebrate research?)
2. If YES, second line: one short Chinese sentence summarizing the paper's main finding
3. If YES, third line: one category from: ecology, conservation, human-wildlife, disease-health, genetics-evolution, methods, policy-management

Example:
YES
本研究利用GPS追踪揭示了东北虎的家域大小和活动节律。
ecology
"""

            response = model.generate_content(prompt)
            result = response.text.strip()
            lines = result.split('\n')

            is_relevant = lines[0].strip().upper() == "YES" if lines else False

            if is_relevant:
                paper["title_cn_summary"] = lines[1].strip() if len(lines) > 1 else ""
                paper["ai_category"] = lines[2].strip() if len(lines) > 2 else "ecology"
                filtered.append(paper)
                print(f"    AI KEEP: {paper['title'][:60]}...")

        except Exception as e:
            print(f"    AI filter failed for {paper['title'][:40]}: {e}")
            # 如果 AI 失败，回退到关键词筛选
            text = (paper["title"] + " " + paper["abstract"]).lower()
            if any(kw in text for kw in KEYWORDS):
                paper["ai_category"] = "other"
                filtered.append(paper)

    return filtered


def ai_filter_papers(papers):
    """Use Gemini AI to filter papers based on wildlife relevance"""
    filtered = []
    for paper in papers:
        try:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                print("  No GEMINI_API_KEY, falling back to keyword filter")
                return filter_by_keywords(papers)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            prompt = f"""You are a wildlife biology expert. Determine if the following paper is relevant to WILD VERTEBRATE research.

Topics that ARE relevant:
- Basic ecology of wild vertebrates (mammals, birds, reptiles, amphibians, fish)
- Conservation of wild vertebrate species
- Human-wildlife interactions and conflict
- Wildlife diseases and health
- Genetics and evolution of wild vertebrates
- Technical methods applicable to wildlife research
- Wildlife policy, management, and planning

Topics that are NOT relevant:
- Plant biology or botany
- Domestic animals (livestock, pets) unless directly related to wildlife
- Human medicine (unless zoonotic disease from wildlife)
- Pure molecular biology without wildlife application
- Marine invertebrates

Paper Title: {paper['title']}
Paper Abstract: {paper['abstract'][:500]}

Answer with ONLY:
1. First line: YES or NO (is it relevant to wild vertebrate research?)
2. If YES, second line: one short Chinese sentence summarizing the paper's main finding
3. If YES, third line: one category from: ecology, conservation, human-wildlife, disease-health, genetics-evolution, methods, policy-management

Example:
YES
本研究利用GPS追踪揭示了东北虎的家域大小和活动节律。
ecology
"""

            response = model.generate_content(prompt)
            result = response.text.strip()
            lines = result.split('\n')

            is_relevant = lines[0].strip().upper() == "YES" if lines else False

            if is_relevant:
                paper["title_cn_summary"] = lines[1].strip() if len(lines) > 1 else ""
                paper["ai_category"] = lines[2].strip() if len(lines) > 2 else "ecology"
                filtered.append(paper)
                print(f"    AI KEEP: {paper['title'][:60]}...")

        except Exception as e:
            print(f"    AI filter failed for {paper['title'][:40]}: {e}")
            # 如果 AI 失败，回退到关键词筛选
            text = (paper["title"] + " " + paper["abstract"]).lower()
            if any(kw in text for kw in KEYWORDS):
                paper["ai_category"] = "other"
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


if __name__ == "__main__":
    print("=" * 50)
    print("Fetching latest life science papers...")
    print(f"Date range: last {DAYS_BACK} days")
    print("=" * 50)
    papers = fetch_papers()
    rss_papers = fetch_rss_papers()
    papers.extend(rss_papers)

    # 用 AI 筛选（如果失败自动回退到关键词筛选）
    print("\nAI filtering papers...")
    papers = ai_filter_papers(papers)
    # 用 AI 筛选（如果失败自动回退到关键词筛选）
    print("\nAI filtering papers...")
    papers = ai_filter_papers(papers)
    seen = set()
    unique_papers = []
    for p in papers:
        if p["pmid"] not in seen:
            seen.add(p["pmid"])
            unique_papers.append(p)
    print(f"\nTotal: {len(unique_papers)} papers")
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "papers.json")
    existing_papers = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_papers = json.load(f)
        except Exception as e:
            print(f"Warning: failed to read existing papers.json: {type(e).__name__}: {e}")

    existing_by_pmid = {p.get("pmid", ""): p for p in existing_papers if p.get("pmid")}
    merged_papers = []
    for p in unique_papers:
        pmid = p.get("pmid")
        if not pmid:
            merged_papers.append(p)
            continue

        existing = existing_by_pmid.get(pmid)
        if existing:
            # Prefer the newly fetched record `p`, but carry forward an existing
            # `title_cn` when the new one is empty.
            if not p.get("title_cn") and existing.get("title_cn"):
                p["title_cn"] = existing["title_cn"]
            # Update existing with all fields from p (p wins), then use that
            existing.update(p)
            merged_papers.append(existing)
            del existing_by_pmid[pmid]
        else:
            merged_papers.append(p)

    # Append any remaining old records that weren't updated
    merged_papers.extend(existing_by_pmid.values())
    # Diagnostics: count translations before writing
    translated_count = sum(1 for x in merged_papers if x.get("title_cn"))
    print(f"Writing {len(merged_papers)} papers, translated titles: {translated_count}")

    existing_papers = merged_papers[:500]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_papers, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output_path} (total {len(existing_papers)} papers)")
    print("\nBuilding site...")
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)
    os.system("npm run build")
    print("Build complete!")