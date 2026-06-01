import time
import xml.etree.ElementTree as ET
from Bio import Entrez

_last_request_time = 0.0
_MIN_INTERVAL = 0.1  # 10 req/sec with API key


def _wait_for_rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_time = time.time()


def _configure_entrez(api_key: str, email: str):
    Entrez.api_key = api_key
    Entrez.email = email


def search_pubmed(keywords: str, api_key: str, email: str, max_results: int = 50) -> list[dict]:
    """Search PubMed by keywords, return top N articles sorted by relevance."""
    _configure_entrez(api_key, email)

    _wait_for_rate_limit()
    handle = Entrez.esearch(db="pubmed", term=keywords, retmax=max_results, sort="relevance")
    records = Entrez.read(handle)
    handle.close()

    id_list = records.get("IdList", [])
    if not id_list:
        return []

    _wait_for_rate_limit()
    handle = Entrez.efetch(db="pubmed", id=",".join(id_list), rettype="abstract", retmode="xml")
    xml_data = handle.read()
    handle.close()

    root = ET.fromstring(xml_data)
    articles = []
    for i, article_elem in enumerate(root.findall(".//PubmedArticle")):
        article = _parse_article(article_elem)
        article["pubmed_rank"] = i
        articles.append(article)

    return articles


def search_pubmed_broad(keywords: str, api_key: str, email: str, fetch_count: int = 100) -> list[dict]:
    """Fetch a broader set for local re-ranking."""
    return search_pubmed(keywords, api_key, email, max_results=fetch_count)


def _parse_article(article_elem) -> dict:
    medline = article_elem.find(".//MedlineCitation")
    article = medline.find(".//Article")

    title_elem = article.find(".//ArticleTitle")
    title = "".join(title_elem.itertext()) if title_elem is not None else ""

    abstract_elem = article.find(".//Abstract")
    abstract = ""
    if abstract_elem is not None:
        parts = []
        for t in abstract_elem.findall(".//AbstractText"):
            label = t.get("Label", "")
            text = "".join(t.itertext())
            parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(parts)

    authors = []
    author_list = article.find(".//AuthorList")
    if author_list is not None:
        for author in author_list.findall("Author"):
            last = author.find("LastName")
            fore = author.find("ForeName")
            if last is not None and fore is not None:
                authors.append(f"{fore.text} {last.text}")

    journal_elem = article.find(".//Journal")
    journal = ""
    year = ""
    if journal_elem is not None:
        j_title = journal_elem.find("Title")
        journal = j_title.text if j_title is not None else ""
        pub_date = journal_elem.find(".//PubDate")
        if pub_date is not None:
            yr = pub_date.find("Year")
            if yr is not None:
                year = yr.text

    pmid_elem = medline.find("PMID")
    pmid = pmid_elem.text if pmid_elem is not None else ""

    mesh_terms = []
    mesh_list = medline.find("MeshHeadingList")
    if mesh_list is not None:
        for mh in mesh_list.findall("MeshHeading"):
            dn = mh.find("DescriptorName")
            if dn is not None and dn.text:
                mesh_terms.append(dn.text)

    return {
        "pmid": pmid,
        "title": title,
        "authors": ", ".join(authors),
        "journal": journal,
        "year": year,
        "abstract": abstract,
        "mesh_terms": mesh_terms,
    }


def find_by_title(title: str, api_key: str, email: str) -> dict | None:
    """Find an article by exact title match. Returns dict with pmid, pmcid, title, abstract, has_pmc, mesh_terms."""
    _configure_entrez(api_key, email)

    _wait_for_rate_limit()
    handle = Entrez.esearch(db="pubmed", term=f'"{title}"[Title]', retmax=5)
    records = Entrez.read(handle)
    handle.close()

    id_list = records.get("IdList", [])
    if not id_list:
        return None

    best_pmid = id_list[0]

    _wait_for_rate_limit()
    handle = Entrez.efetch(db="pubmed", id=best_pmid, rettype="xml", retmode="xml")
    xml_data = handle.read()
    handle.close()

    root = ET.fromstring(xml_data)
    article_elem = root.find(".//PubmedArticle")
    if article_elem is None:
        return None

    article = _parse_article(article_elem)
    canonical_title = article["title"]

    pmcid = None
    article_ids = article_elem.findall(".//PubmedData/ArticleIdList/ArticleId")
    for aid in article_ids:
        if aid.get("IdType") == "pmc":
            raw = aid.text.strip() if aid.text else ""
            pmcid = raw.replace("PMC", "") if raw.startswith("PMC") else raw

    pmid_elem = article_elem.find(".//MedlineCitation/PMID")
    pmid = pmid_elem.text if pmid_elem is not None else best_pmid

    return {
        "pmid": pmid,
        "pmcid": pmcid,
        "title": canonical_title,
        "abstract": article["abstract"],
        "has_pmc": pmcid is not None,
        "mesh_terms": article["mesh_terms"],
    }


def find_similar_by_title(title: str, api_key: str, email: str, max_results: int = 5) -> list[dict]:
    """Fuzzy search by title keywords. Returns up to max_results articles."""
    _configure_entrez(api_key, email)

    _wait_for_rate_limit()
    handle = Entrez.esearch(db="pubmed", term=title, retmax=max_results, sort="relevance")
    records = Entrez.read(handle)
    handle.close()

    id_list = records.get("IdList", [])
    if not id_list:
        return []

    _wait_for_rate_limit()
    handle = Entrez.efetch(db="pubmed", id=",".join(id_list), rettype="xml", retmode="xml")
    xml_data = handle.read()
    handle.close()

    root = ET.fromstring(xml_data)
    articles = []
    for article_elem in root.findall(".//PubmedArticle"):
        article = _parse_article(article_elem)
        pmcid = None
        article_ids = article_elem.findall(".//PubmedData/ArticleIdList/ArticleId")
        for aid in article_ids:
            if aid.get("IdType") == "pmc":
                raw = aid.text.strip() if aid.text else ""
                pmcid = raw.replace("PMC", "") if raw.startswith("PMC") else raw
        article["pmcid"] = pmcid
        article["has_pmc"] = pmcid is not None
        articles.append(article)

    return articles


def fetch_pmc_full_text(pmcid: str) -> dict | None:
    """Fetch and parse PMC full text XML. Returns dict with 'title', 'abstract', 'body' or None."""
    pmcid = pmcid.replace("PMC", "").strip()
    try:
        _wait_for_rate_limit()
        handle = Entrez.efetch(db="pmc", id=pmcid, rettype="xml", retmode="xml")
        xml_data = handle.read()
        handle.close()
    except Exception:
        return None

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return None

    ns_prefix = "{http://www.ncbi.nlm.nih.gov/pmc/xml}"

    # Extract title from PMC front matter
    pmc_title = ""
    title_elem = root.find(f".//{ns_prefix}front//{ns_prefix}article-title")
    if title_elem is None:
        title_elem = root.find(f".//{ns_prefix}article-meta//{ns_prefix}title-group//{ns_prefix}article-title")
    if title_elem is not None:
        pmc_title = "".join(title_elem.itertext()).strip()

    # Extract abstract from PMC
    pmc_abstract = ""
    abstract_elem = root.find(f".//{ns_prefix}abstract")
    if abstract_elem is not None:
        parts = []
        for p in abstract_elem.iter():
            tag = p.tag.split("}")[-1] if "}" in p.tag else p.tag
            if tag == "p":
                text = "".join(p.itertext()).strip()
                if text:
                    parts.append(text)
        pmc_abstract = " ".join(parts)

    # Extract body text
    body_elem = root.find(f".//{ns_prefix}body")
    if body_elem is None:
        body_elem = root.find(".//body")

    if body_elem is None:
        return None

    paragraphs = []
    for p in body_elem.iter():
        tag = p.tag.split("}")[-1] if "}" in p.tag else p.tag
        if tag == "p":
            text = "".join(p.itertext()).strip()
            if text:
                paragraphs.append(text)

    body_text = "\n\n".join(paragraphs)
    if not body_text:
        return None

    return {
        "title": pmc_title,
        "abstract": pmc_abstract,
        "body": body_text,
    }
