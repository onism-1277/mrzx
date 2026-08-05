import requests
import json
import os
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

# ============================================
# 閰嶇疆鍖猴細浣犲彲浠ュ湪杩欓噷淇敼鏈熷垔鍜屽叧閿瘝
# ============================================

# 浣犳兂杩借釜鐨勬湡鍒婂垪琛紙PubMed 鏈熷垔鍚嶇缉鍐欙級
JOURNALS = [
    "Nature",
    "Science",
    "Proc Natl Acad Sci U S A",    # PNAS
    "Sci Adv",                      # Science Advances
    "Nat Commun",                   # Nature Communications
    "Mol Biol Evol",                # Molecular Biology and Evolution
    "Gene",
]

# 鐢熷懡绉戝鏂瑰悜鍏抽敭璇嶏紙鍦ㄦ爣棰?鎽樿涓尮閰嶏級
KEYWORDS = [
    "virus", "viral", "virology",
    "microbiology", "microbial", "microbiome", "bacteria", "bacterial",
    "zoology", "animal", "wildlife",
    "evolution", "evolutionary", "phylogenetic",
    "genomics", "genetics", "gene", "genome",
    "immunology", "immune",
    "neuroscience", "neural",
    "cell biology", "molecular biology",
    "biochemistry", "protein",
    "ecology", "ecological",
]

# 鑾峰彇鏈€杩戝嚑澶╃殑璁烘枃
DAYS_BACK = 3

# DeepSeek API 閰嶇疆锛堢敤浜庣炕璇戞爣棰橈級
DEEPSEEK_API_KEY = "浣犵殑API瀵嗛挜"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


# ============================================
# 缈昏瘧鍔熻兘
# ============================================

def translate_title(title):
    """璋冪敤 DeepSeek 缈昏瘧鑻辨枃鏍囬涓轰腑鏂?""
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "浣犵殑API瀵嗛挜":
        return ""

    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "浣犳槸鐢熷懡绉戝棰嗗煙涓撲笟缈昏瘧锛岃灏嗕互涓嬭鏂囨爣棰樼炕璇戞垚绠€娲佸噯纭殑涓枃锛屽彧杩斿洖璇戞枃锛屼笉瑕佷换浣曡В閲娿€?
                },
                {
                    "role": "user",
                    "content": title
                }
            ],
            "max_tokens": 100,
            "temperature": 0.3
        }
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=15)
        result = resp.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"    缈昏瘧澶辫触: {e}")
        return ""


# ============================================
# 鏍稿績閫昏緫锛氫粠 PubMed 鑾峰彇璁烘枃
# ============================================

def fetch_papers():
    all_papers = []
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # 璁＄畻鏃ユ湡鑼冨洿
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS_BACK)
    start_str = start_date.strftime("%Y/%m/%d")
    end_str = end_date.strftime("%Y/%m/%d")

    for journal in JOURNALS:
        print(f"姝ｅ湪鑾峰彇 {journal} 鐨勮鏂?..")

        # 鎼滅储锛氭湡鍒婂悕 + 鏃ユ湡鑼冨洿
        search_query = f'"{journal}"[Journal]'
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
                print(f"  {journal}: 娌℃湁鏂拌鏂?)
                continue

            print(f"  {journal}: 鎵惧埌 {len(id_list)} 绡囷紝姝ｅ湪鑾峰彇璇︽儏...")

            ids = ",".join(id_list)
            fetch_url = f"{base_url}/efetch.fcgi?db=pubmed&id={ids}&retmode=xml"

            resp = requests.get(fetch_url, timeout=30)
            resp.raise_for_status()

            papers = parse_pubmed_xml(resp.text, journal)
            filtered = filter_by_keywords(papers)
            print(f"  {journal}: 绛涢€夊悗鍓╀綑 {len(filtered)} 绡囩敓鍛界瀛︾浉鍏宠鏂?)

            all_papers.extend(filtered)

        except Exception as e:
            print(f"  {journal}: 鑾峰彇澶辫触 - {e}")

    return all_papers


def parse_pubmed_xml(xml_text, journal):
    """瑙ｆ瀽 PubMed XML锛屾彁鍙栧叧閿俊鎭?""
    papers = []
    root = ET.fromstring(xml_text)

    for article in root.findall(".//PubmedArticle"):
        try:
            # 鏍囬
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""
            if not title:
                continue

            # 缈昏瘧鏍囬
            title_cn = translate_title(title)
            if title_cn:
                print(f"    鉁?{title[:60]}... 鈫?{title_cn[:40]}...")

            # 鎽樿
            abstract_parts = []
            for abs_elem in article.findall(".//AbstractText"):
                label = abs_elem.get("Label", "")
                text = abs_elem.text or ""
                abstract_parts.append(f"{label}: {text}" if label else text)
            abstract = " ".join(abstract_parts)

            # DOI
            doi = ""
            for eid in article.findall(".//ELocationID"):
                if eid.get("EIdType") == "doi":
                    doi = eid.text or ""

            # PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            # 鏃ユ湡 - 浠?PubMed 璁板綍涓彁鍙栫湡瀹炲彂琛ㄦ棩鏈?            pub_date = ""
            date_elem = article.find(".//PubDate")
            if date_elem is not None:
                year = date_elem.find("Year")
                month = date_elem.find("Month")
                day = date_elem.find("Day")
                y = year.text if year is not None else ""
                m = month.text if month is not None else "01"
                d = day.text if day is not None else "01"
                # 鏈堜唤鍙兘鏄嫳鏂囩缉鍐欙紝杞暟瀛?                try:
                    m = str(datetime.strptime(m, "%b").month).zfill(2)
                except:
                    pass
                pub_date = f"{y}-{m.zfill(2) if len(m) < 2 else m}-{d.zfill(2) if len(d) < 2 else d}"

            # URL
            if doi:
                url = f"https://doi.org/{doi}"
            else:
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

            # 浣滆€咃紙鍙栧墠涓夛級
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
    """鏍规嵁鍏抽敭璇嶇瓫閫夌敓鍛界瀛︾浉鍏宠鏂?""
    filtered = []
    for paper in papers:
        text = (paper["title"] + " " + paper["abstract"]).lower()
        for kw in KEYWORDS:
            if kw.lower() in text:
                paper["category"] = get_category(kw)
                filtered.append(paper)
                break
    return filtered


def get_category(keyword):
    """鏍规嵁鍏抽敭璇嶈繑鍥炲垎绫?""
    kw = keyword.lower()
    if kw in ["virus", "viral", "virology"]:
        return "virology"
    elif kw in ["microbiology", "microbial", "microbiome", "bacteria", "bacterial"]:
        return "microbiology"
    elif kw in ["zoology", "animal", "wildlife"]:
        return "zoology"
    elif kw in ["evolution", "evolutionary", "phylogenetic"]:
        return "evolution"
    elif kw in ["genomics", "genetics", "gene", "genome"]:
        return "genetics"
    elif kw in ["immunology", "immune"]:
        return "immunology"
    elif kw in ["neuroscience", "neural"]:
        return "neuroscience"
    elif kw in ["cell biology", "molecular biology"]:
        return "cell biology"
    elif kw in ["biochemistry", "protein"]:
        return "biochemistry"
    elif kw in ["ecology", "ecological"]:
        return "ecology"
    return "other"


# ============================================
# 涓荤▼搴忥細杩愯骞朵繚瀛樼粨鏋?# ============================================

if __name__ == "__main__":
    print("=" * 50)
    print("寮€濮嬭幏鍙栫敓鍛界瀛﹂鍩熸渶鏂拌鏂?..")
    print(f"鏃ユ湡鑼冨洿锛氭渶杩?{DAYS_BACK} 澶?)
    print("=" * 50)

    papers = fetch_papers()

    # 鍘婚噸锛堟寜 PMID锛?    seen = set()
    unique_papers = []
    for p in papers:
        if p["pmid"] not in seen:
            seen.add(p["pmid"])
            unique_papers.append(p)

    print(f"\n鍏辫幏鍙?{len(unique_papers)} 绡囩敓鍛界瀛︾浉鍏宠鏂?)

    # 鍔犺浇宸叉湁璁烘枃锛屽悎骞?    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "papers.json")

    existing_papers = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r", encoding="utf-8") as f:
                existing_papers = json.load(f)
        except:
            pass

    # 鍚堝苟锛氱敤 PMID 鍘婚噸锛屾柊璁烘枃浼樺厛
    existing_pmids = {p.get("pmid", "") for p in existing_papers}
    for p in unique_papers:
        if p["pmid"] not in existing_pmids:
            existing_papers.insert(0, p)
            existing_pmids.add(p["pmid"])

    # 鏈€澶氫繚鐣?00绡?    existing_papers = existing_papers[:500]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(existing_papers, f, ensure_ascii=False, indent=2)

    print(f"宸蹭繚瀛樺埌 {output_path}锛堟€昏 {len(existing_papers)} 绡囷級")

    # 閲嶆柊鏋勫缓 Astro 缃戠珯
    print("\n姝ｅ湪閲嶆柊鏋勫缓缃戠珯...")
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_dir)
    os.system("npm run build")
    print("鏋勫缓瀹屾垚锛乨ist/ 鏂囦欢澶逛腑鐨勫唴瀹瑰彲浠ラ儴缃插埌鏈嶅姟鍣ㄣ€?)
