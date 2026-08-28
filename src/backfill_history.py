import json
import os
import time
from datetime import datetime

import requests

from fetch_papers import (
    JOURNALS,
    RSS_FEEDS,
    ai_filter_papers,
    parse_pubmed_xml,
    parse_rss,
    summarize_papers,
    translate_papers,
)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "data", "papers.json")
MARKER_PATH = os.path.join(os.path.dirname(__file__), "data", "history_backfill.json")
HISTORY_START_DATE = "2026-01-01"


def fetch_journal_history(journals, start_date, end_date):
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    papers = []
    for journal in journals:
        print(f"Fetching history for {journal}...")
        query = (
            f'"{journal}"[Journal] AND ('
            "zoology[MeSH] OR ecology[MeSH] OR genetics[MeSH] OR "
            "evolution[MeSH] OR genetics, population[MeSH] OR "
            "computational biology[MeSH] OR conservation of natural resources[MeSH] OR "
            "behavior, animal[MeSH] OR paleontology[MeSH] OR biogeography[MeSH] OR "
            "classification[MeSH] OR biotechnology[MeSH])"
        )
        url = (
            f"{base_url}/esearch.fcgi?db=pubmed&term={query}"
            f"&retmax=500&retmode=json&mindate={start_date}"
            f"&maxdate={end_date}&datetype=pdat"
        )
        ids = []
        for attempt in range(3):
            try:
                time.sleep(1.5)
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                ids = response.json().get("esearchresult", {}).get("idlist", [])
                break
            except Exception as exc:
                print(f"  Search attempt {attempt + 1} failed: {exc}")
                time.sleep(4)
        if not ids:
            print("  No papers found")
            continue

        for attempt in range(3):
            try:
                time.sleep(1.5)
                detail_url = f"{base_url}/efetch.fcgi?db=pubmed&id={','.join(ids)}&retmode=xml"
                response = requests.get(detail_url, timeout=60)
                response.raise_for_status()
                parsed = parse_pubmed_xml(response.text, journal)
                papers.extend(parsed)
                print(f"  Parsed {len(parsed)} papers")
                break
            except Exception as exc:
                print(f"  Fetch attempt {attempt + 1} failed: {exc}")
                time.sleep(4)
    return papers


def main():
    if os.path.exists(MARKER_PATH):
        print("History backfill already completed; fixed data will not be reprocessed.")
        return

    with open(OUTPUT_PATH, "r", encoding="utf-8") as file:
        existing = json.load(file)

    today = datetime.now().strftime("%Y-%m-%d")
    existing_journals = {
        paper.get("journal")
        for paper in existing
        if paper.get("date") and HISTORY_START_DATE <= paper["date"] <= today
    }
    missing_journals = [journal for journal in JOURNALS if journal not in existing_journals]
    print(f"Existing history journals: {len(existing_journals)}")
    print(f"Missing PubMed journals to backfill: {len(missing_journals)}")

    new_papers = fetch_journal_history(missing_journals, HISTORY_START_DATE, today)

    if "野生动物学报" not in existing_journals:
        print("Fetching missing RSS journal history...")
        for feed in RSS_FEEDS:
            response = requests.get(feed["url"], timeout=30)
            response.raise_for_status()
            rss_papers = parse_rss(response.text, feed["name"])
            new_papers.extend(
                paper for paper in rss_papers
                if paper.get("date") and HISTORY_START_DATE <= paper["date"] <= today
            )

    filtered = ai_filter_papers(new_papers)
    unique = []
    seen = {paper.get("pmid") for paper in existing}
    for paper in filtered:
        if paper.get("pmid") not in seen:
            seen.add(paper.get("pmid"))
            unique.append(paper)

    unique = translate_papers(unique)
    unique = summarize_papers(unique)
    existing[0:0] = unique

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(existing[:3000], file, ensure_ascii=False, indent=2)
    with open(MARKER_PATH, "w", encoding="utf-8") as file:
        json.dump({"completedAt": today, "journals": JOURNALS + ["野生动物学报"]}, file, ensure_ascii=False, indent=2)

    print(f"Backfill complete: added {len(unique)} fixed papers")
    print(f"Saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
