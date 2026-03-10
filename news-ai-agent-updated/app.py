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
    page_title="Digital Media Assisstant",
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


def extract_article_from_url(url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
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
                extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
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


def call_llm_for_analysis(article_title: str, article_text: str) -> dict:
    client = build_client()
    model = get_model_name()

    prompt = f"""
You are a professional digital media analyst.
Analyze the following news article and return ONLY valid JSON.

Requirements:
- Create a detailed summary that is not too short.
- Extract key points.
- Extract prominent people.
- Extract organizations.
- Extract locations.
- Extract dates.
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
  "prominent_people": ["..."],
  "organizations": ["..."],
  "locations": ["..."],
  "dates": ["..."],
  "search_query": "...",
  "telegram_post_ar": "...",
  "linkedin_post_en": "..."
}}

Article title:
{article_title}

Article text:
{article_text[:15000]}
"""

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    raw = response.output_text.strip()
    raw = re.sub(r"^```json", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()

    try:
        return json.loads(raw)
    except Exception:
        return {
            "main_event": "",
            "detailed_summary_en": raw,
            "detailed_summary_ar": raw,
            "key_points": [],
            "prominent_people": [],
            "organizations": [],
            "locations": [],
            "dates": [],
            "search_query": article_title,
            "telegram_post_ar": "",
            "linkedin_post_en": ""
        }


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
st.title("📰 Digital Media Assisstant")
st.caption("Analyze global news articles, summarize them, discover related coverage, and export ready-to-post content.")

api_key = get_api_key()
if not api_key:
    st.warning("Please add OPENAI_API_KEY in your environment variables or Streamlit secrets before running the app.")

input_mode = st.radio("Choose input type", ["News URL", "Raw News Text"], horizontal=True)
article_title = ""
article_text = ""
url_value = ""

if input_mode == "News URL":
    url_value = st.text_input("Enter the news article URL")
else:
    article_title = st.text_input("Optional title")
    article_text = st.text_area("Paste the news text", height=280)

run = st.button("Analyze News", type="primary", use_container_width=True)

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

    search_query = analysis.get("search_query") or analysis.get("main_event") or article_title or "latest news event"

    with st.spinner("Finding related sources..."):
        related_sources = search_related_sources(search_query)

    tab1, tab2, tab3 = st.tabs(["Summery", "Related Sources Found", "Export"])

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

       ''' c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.subheader("Prominent People")
            people = analysis.get("prominent_people", [])
            st.write("\n".join([f"• {x}" for x in people]) if people else "Not available")
        with c2:
            st.subheader("Organizations")
            orgs = analysis.get("organizations", [])
            st.write("\n".join([f"• {x}" for x in orgs]) if orgs else "Not available")
        with c3:
            st.subheader("Locations")
            locations = analysis.get("locations", [])
            st.write("\n".join([f"• {x}" for x in locations]) if locations else "Not available")
        with c4:
            st.subheader("Dates")
            dates = analysis.get("dates", [])
            st.write("\n".join([f"• {x}" for x in dates]) if dates else "Not available")'''

    with tab2:
        st.subheader("Related Sources Found")
        if not related_sources:
            st.info("No related sources were found.")
        for idx, item in enumerate(related_sources, start=1):
            with st.container(border=True):
                st.markdown(f"### {idx}. {item['title']}")
                if item.get("source"):
                    st.caption(f"Source: {item['source']} | Published: {item.get('published', '')}")
                else:
                    st.caption(f"Published: {item.get('published', '')}")
                if item.get("summary"):
                    st.write(item["summary"])
                if item.get("link"):
                    st.link_button("Open Source", item["link"])

    with tab3:
        st.subheader("Telegram Post")
        telegram_post = analysis.get("telegram_post_ar", "")
        st.text_area("Telegram-ready post", value=telegram_post, height=220)

        st.subheader("LinkedIn Post")
        linkedin_post = analysis.get("linkedin_post_en", "")
        st.text_area("LinkedIn-ready post", value=linkedin_post, height=260)

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
