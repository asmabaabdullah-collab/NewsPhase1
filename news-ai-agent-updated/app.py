import os
import re
import json
import html
import feedparser
import requests
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import quote_plus

try:
    import trafilatura
except Exception:
    trafilatura = None

from openai import OpenAI


# =========================
# Page Config
# =========================
st.set_page_config(
    page_title="Digital Media Assistant",
    page_icon="📰",
    layout="wide",
)


# =========================
# Helpers
# =========================
def get_api_key() -> str:
    key = ""
    try:
        key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        key = ""

    if not key:
        key = os.getenv("OPENAI_API_KEY", "")

    return key


def get_model_name() -> str:
    model = ""
    try:
        model = st.secrets.get("OPENAI_MODEL", "")
    except Exception:
        model = ""

    if not model:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    return model


def build_client() -> OpenAI:
    return OpenAI(api_key=get_api_key())


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


# =========================
# Article Extraction
# =========================
def extract_article_from_url(url: str) -> dict:

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        html_content = response.text
    except Exception as e:
        return {
            "title": "",
            "text": "",
            "error": f"Failed to fetch URL: {e}"
        }

    title = ""
    text = ""

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        if soup.title and soup.title.string:
            title = clean_text(soup.title.string)
    except Exception:
        pass

    if trafilatura:
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                extracted = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=False
                )
                if extracted:
                    text = clean_text(extracted)
        except Exception:
            pass

    if not text:
        try:
            soup = BeautifulSoup(html_content, "html.parser")
            paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
            text = clean_text(" ".join(paragraphs))
        except Exception:
            text = ""

    return {
        "title": title,
        "text": text,
        "error": ""
    }


# =========================
# AI Analysis
# =========================
def call_llm_for_analysis(article_title: str, article_text: str) -> dict:

    client = build_client()
    model = get_model_name()

    prompt = f"""
You are a professional digital media analyst.

Analyze the following news article and return ONLY valid JSON.

Requirements:
- Create a detailed summary.
- Extract key points.
- Extract the main event in one sentence.
- Write an Arabic telegram post.
- Write a professional LinkedIn post in English.
- Create a search query for finding related coverage.

Return JSON with this structure:

{{
  "main_event": "...",
  "detailed_summary_en": "...",
  "detailed_summary_ar": "...",
  "key_points": ["..."],
  "search_query": "...",
  "telegram_post_ar": "...",
  "linkedin_post_en": "..."
}}

Article title:
{article_title}

Article text:
{article_text[:12000]}
"""

    response = client.responses.create(
        model=model,
        input=prompt
    )

    raw = ""
    for item in response.output:
        if item.type == "output_text":
            raw += item.text

    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return {
            "main_event": "",
            "detailed_summary_en": raw,
            "detailed_summary_ar": raw,
            "key_points": [],
            "search_query": article_title,
            "telegram_post_ar": "",
            "linkedin_post_en": ""
        }


# =========================
# Google News Search
# =========================
def search_related_sources(query: str, limit: int = 8) -> list:

    rss_url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"

    feed = feedparser.parse(rss_url)

    items = []

    for entry in feed.entries[:limit]:

        source_name = ""

        if hasattr(entry, "source") and isinstance(entry.source, dict):
            source_name = entry.source.get("title", "")

        items.append({
            "title": getattr(entry, "title", ""),
            "link": getattr(entry, "link", ""),
            "published": getattr(entry, "published", ""),
            "source": source_name,
            "summary": clean_text(getattr(entry, "summary", "")),
        })

    return items


# =========================
# UI
# =========================
st.title("📰 Digital Media Assistant")

st.caption(
    "Analyze global news articles, summarize them, discover related coverage, and export ready-to-post content."
)

api_key = get_api_key()

if not api_key:
    st.warning("Please add OPENAI_API_KEY before running the app.")


input_mode = st.radio(
    "Choose input type",
    ["News URL", "Raw News Text"],
    horizontal=True
)

article_title = ""
article_text = ""
url_value = ""

if input_mode == "News URL":

    url_value = st.text_input("Enter the news article URL")

else:

    article_title = st.text_input("Optional title")

    article_text = st.text_area(
        "Paste the news text",
        height=280
    )


run = st.button(
    "Analyze News",
    type="primary",
    use_container_width=True
)


# =========================
# Run Analysis
# =========================
if run:

    if input_mode == "News URL":

        if not url_value.strip():
            st.error("Please enter a valid URL.")
            st.stop()

        with st.spinner("Extracting article content..."):

            extraction = extract_article_from_url(url_value.strip())

        if extraction.get("error"):
            st.error(extraction["error"])
            st.stop()

        article_title = extraction.get("title", "")
        article_text = extraction.get("text", "")

    if not article_text.strip():
        st.error("No article text was found to analyze.")
        st.stop()

    with st.spinner("Analyzing article with AI..."):

        analysis = call_llm_for_analysis(article_title, article_text)

    search_query = (
        analysis.get("search_query")
        or analysis.get("main_event")
        or article_title
        or "latest news event"
    )

    with st.spinner("Finding related sources..."):

        related_sources = search_related_sources(search_query)

    tab1, tab2, tab3 = st.tabs(["Summary", "Related Sources Found", "Export"])


    # =========================
    # Tab 1 Summary
    # =========================
    with tab1:

        st.subheader("Main Event")
        st.write(analysis.get("main_event", "Not available"))

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Detailed Summary (English)")
            st.write(analysis.get("detailed_summary_en", "Not available"))

        with col2:
            st.subheader("الملخص التفصيلي (العربية)")
            st.write(analysis.get("detailed_summary_ar", "غير متوفر"))

        st.subheader("Key Points")

        for point in analysis.get("key_points", []):
            st.markdown(f"- {point}")


    # =========================
    # Tab 2 Sources
    # =========================
    with tab2:

        st.subheader("Related Sources Found")

        if not related_sources:
            st.info("No related sources were found.")

        for idx, item in enumerate(related_sources, start=1):

            with st.container(border=True):

                st.markdown(f"### {idx}. {item['title']}")

                if item.get("source"):
                    st.caption(
                        f"Source: {item['source']} | Published: {item.get('published', '')}"
                    )
                else:
                    st.caption(f"Published: {item.get('published', '')}")

                if item.get("summary"):
                    st.write(item["summary"])

                if item.get("link"):
                    st.link_button("Open Source", item["link"])


    # =========================
    # Tab 3 Export
    # =========================
    with tab3:

        st.subheader("Telegram Post")

        telegram_post = analysis.get("telegram_post_ar", "")

        st.text_area(
            "Telegram-ready post",
            value=telegram_post,
            height=220
        )

        st.subheader("LinkedIn Post")

        linkedin_post = analysis.get("linkedin_post_en", "")

        st.text_area(
            "LinkedIn-ready post",
            value=linkedin_post,
            height=260
        )

        st.download_button(
            "Download Telegram Post",
            data=telegram_post.encode("utf-8"),
            file_name="telegram_post.txt",
            mime="text/plain",
            use_container_width=True,
        )

        st.download_button(
            "Download LinkedIn Post",
            data=linkedin_post.encode("utf-8"),
            file_name="linkedin_post.txt",
            mime="text/plain",
            use_container_width=True,
        )
