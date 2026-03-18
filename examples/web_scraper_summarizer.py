"""Web scraper summarizer — fetch a URL and summarize with LLM.

This shows:
- HTTP requests in a CodeNode (using httpx)
- HTML text extraction
- LLMNode summarizing web content

Run with:
    reasonflow run examples/web_scraper_summarizer.py -v url="https://example.com"
"""

import re

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def fetch_page(state):
    """Fetch a web page and extract text content."""
    import httpx

    url = state.get("url", "https://example.com")

    response = httpx.get(url, follow_redirects=True, timeout=15)
    response.raise_for_status()

    html = response.text

    # Strip HTML tags (simple approach)
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else url

    # Truncate for LLM context
    max_chars = 6000
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]

    return {
        "page_title": title,
        "page_text": text,
        "page_url": url,
        "page_length": len(response.text),
        "truncated": truncated,
    }


@LLMNode(model="claude-haiku", budget="$0.05")
def summarize_page(state):
    """You are a research assistant. Summarize this web page concisely.

    Title: {page_title}
    URL: {page_url}

    Content:
    {page_text}

    Provide:
    1. A 2-3 sentence summary
    2. Key points (3-5 bullet points)
    3. The primary topic/category

    Return as JSON with keys: "summary", "key_points" (list), "category".
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("web-scraper", budget="$0.10", debug=True)

dag.connect(fetch_page >> summarize_page)


if __name__ == "__main__":
    result = dag.run(url="https://example.com")
    print(result.trace.summary())
    print()
    if result.success:
        print(f"URL: {result.state.get('page_url')}")
        print(f"Title: {result.state.get('page_title')}")
        print(f"\nSummary: {result.state.get('summary', 'N/A')}")
        print(f"\nKey Points:")
        for point in result.state.get("key_points", []):
            print(f"  - {point}")
        print(f"\nCategory: {result.state.get('category', 'N/A')}")
    else:
        print(f"Error: {result.error}")
