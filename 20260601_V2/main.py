import streamlit as st
from config import load_config, save_config
from pubmed_client import search_pubmed_broad, find_by_title, find_similar_by_title, fetch_pmc_full_text
from summarizer import summarize
from pdf_parser import extract_text
from output_handler import save_markdown
from ranker import rerank
from journal_metrics import load_metrics

st.set_page_config(page_title="文献检索与概括", layout="wide")


def init_session():
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "search_results" not in st.session_state:
        st.session_state.search_results = []
    if "metrics" not in st.session_state:
        st.session_state.metrics = load_metrics()
    # Feature 2 state
    if "f2_article" not in st.session_state:
        st.session_state.f2_article = None
    if "f2_similar" not in st.session_state:
        st.session_state.f2_similar = []
    if "f2_summary" not in st.session_state:
        st.session_state.f2_summary = None
    if "f2_filepath" not in st.session_state:
        st.session_state.f2_filepath = None


def render_setup():
    st.title("初始配置")
    st.markdown("首次使用请配置 API Key。密钥保存在本地 `.env` 文件中。")

    config = load_config()
    pubmed_key = st.text_input(
        "PubMed API Key", value=config.get("PUBMED_API_KEY", ""), type="password"
    )
    deepseek_key = st.text_input(
        "DeepSeek API Key", value=config.get("DEEPSEEK_API_KEY", ""), type="password"
    )
    email = st.text_input(
        "PubMed 邮箱 (可选)", value=config.get("PUBMED_EMAIL", "")
    )

    if st.button("保存配置", type="primary"):
        save_config({
            "PUBMED_API_KEY": pubmed_key,
            "DEEPSEEK_API_KEY": deepseek_key,
            "PUBMED_EMAIL": email,
        })
        st.session_state.config = load_config()
        st.success("配置已保存！")
        st.rerun()


def render_feature1():
    st.title("PubMed 文献检索")
    st.markdown("输入关键词，检索 Top 50 文献（本地多因子重排）。")

    col1, col2 = st.columns([3, 1])
    with col1:
        keywords = st.text_input("关键词", placeholder="例如: gut microbiota brain axis",
                                  key="f1_keywords")
    with col2:
        search_btn = st.button("搜索", type="primary", use_container_width=True)

    if search_btn and keywords.strip():
        api_key = st.session_state.config.get("PUBMED_API_KEY", "")
        email = st.session_state.config.get("PUBMED_EMAIL", "")
        try:
            with st.spinner("正在检索 PubMed 并重排..."):
                articles = search_pubmed_broad(keywords.strip(), api_key, email, fetch_count=100)
                if articles:
                    metrics = st.session_state.metrics
                    articles = rerank(articles, keywords.strip(), metrics)
                    articles = articles[:50]
            st.session_state.search_results = articles
        except Exception as e:
            st.error(f"检索失败: {e}")
            st.session_state.search_results = []

    results = st.session_state.search_results
    if results:
        st.success(f"共找到 {len(results)} 篇文献（多因子重排后）")
        if st.checkbox("显示评分明细"):
            for i, article in enumerate(results, 1):
                st.text(
                    f"#{i} score={article.get('_score')} "
                    f"pos={article.get('_pos_score')} kw={article.get('_kw_score')} "
                    f"mesh={article.get('_mesh_score')} time={article.get('_time_score')} "
                    f"jrnl={article.get('_journal_score')} — {article['title'][:60]}"
                )
        st.markdown("---")
        for i, article in enumerate(results, 1):
            with st.expander(f"#{i} [{article.get('_score', '-')}] {article['title']}"):
                st.markdown(f"**Authors:** {article['authors']}")
                st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                st.markdown(f"**PMID:** {article['pmid']}")
                if article.get("mesh_terms"):
                    st.markdown(f"**MeSH:** {', '.join(article['mesh_terms'][:10])}")
                if article["abstract"]:
                    st.markdown(f"**Abstract:** {article['abstract']}")
    elif keywords.strip() and not results:
        st.warning("未找到相关文献。")


def render_feature2():
    st.title("文章概括")
    st.markdown("输入文章标题，获取全文并用 AI 生成概括报告。")

    title = st.text_input("文章标题", placeholder="输入完整的文章标题", key="f2_title")
    col1, col2 = st.columns([3, 1])
    with col2:
        find_btn = st.button("检索并概括", type="primary", use_container_width=True)

    if find_btn and title.strip():
        api_key = st.session_state.config.get("PUBMED_API_KEY", "")
        email = st.session_state.config.get("PUBMED_EMAIL", "")

        st.session_state.f2_article = None
        st.session_state.f2_similar = []
        st.session_state.f2_summary = None
        st.session_state.f2_filepath = None

        article = find_by_title(title.strip(), api_key, email)
        if article:
            st.session_state.f2_article = article
            st.rerun()
        else:
            similar = find_similar_by_title(title.strip(), api_key, email, max_results=5)
            if similar:
                st.session_state.f2_similar = similar
                st.rerun()
            else:
                st.error("未找到该文章，请检查标题。")
                st.info("也可以上传 PDF 文件。")
                uploaded_file = st.file_uploader("上传 PDF", type=["pdf"], key="f2_pdf_noresult")
                if uploaded_file is not None:
                    _handle_pdf_upload(uploaded_file)
                return

    # Fuzzy match: show candidates and wait for selection
    if st.session_state.f2_similar and not st.session_state.f2_article:
        st.warning("未找到精确匹配，以下是 5 篇最相似的文献：")
        similar = st.session_state.f2_similar
        options = {f"{a['title']} ({a['journal']}, {a['year']})": a for a in similar}
        choice = st.radio("请选择一篇", list(options.keys()), key="f2_choice")
        if st.button("确认选择", type="primary"):
            st.session_state.f2_article = options[choice]
            st.session_state.f2_similar = []
            st.rerun()

    # If we have an article, process it
    if st.session_state.f2_article:
        article = st.session_state.f2_article
        deepseek_key = st.session_state.config.get("DEEPSEEK_API_KEY", "")

        with st.status("正在处理...", expanded=True) as status:
            st.write(f"✅ PubMed 标题: {article['title']}")
            st.write(f"   PMID: {article['pmid']}")
            st.write("📄 获取 PMC 全文...")
            full_text = None
            if article.get("has_pmc"):
                st.write(f"PMC ID: {article['pmcid']}")
                pmc_data = fetch_pmc_full_text(article["pmcid"])
                if pmc_data:
                    pmc_title = pmc_data.get("title", "")
                    if pmc_title and pmc_title.lower() != article["title"].lower():
                        st.warning(
                            f"⚠️ **标题不一致！**\n\n"
                            f"PubMed 记录: {article['title']}\n\n"
                            f"PMC 全文标题: {pmc_title}\n\n"
                            f"将以 PMC 全文实际标题为准。"
                        )
                        article["title"] = pmc_title  # Use PMC title
                    full_text = (
                        f"标题: {pmc_title}\n\n"
                        f"摘要: {pmc_data.get('abstract', '')}\n\n"
                        f"正文:\n{pmc_data['body']}"
                    )
                    st.write(f"✅ 已获取 PMC 全文。")
                    st.write(f"   全文标题: {pmc_title}")
                    with st.expander("查看全文前 500 字符"):
                        st.text(full_text[:500])
                else:
                    st.write("⚠️ 无法解析 PMC 全文。")
            else:
                st.write("⚠️ 该文章未收录于 PMC。")

            if full_text is None:
                status.update(label="需要上传 PDF", state="running")

        if full_text is None:
            st.warning("该文章无 PMC 全文。请上传 PDF 文件。")
            uploaded_file = st.file_uploader("上传 PDF", type=["pdf"], key="f2_pdf_upload")
            if uploaded_file is not None:
                _handle_pdf_upload(uploaded_file, article)
            return

        _summarize_and_display(full_text, article)

    # Always show saved summary if available
    if st.session_state.f2_summary and st.session_state.f2_filepath:
        st.markdown("---")
        st.markdown("## 生成报告")
        st.markdown(st.session_state.f2_summary)
        with open(st.session_state.f2_filepath, "r", encoding="utf-8") as f:
            st.download_button(
                label="下载 Markdown",
                data=f,
                file_name=st.session_state.f2_filepath.rsplit("\\", 1)[-1]
                if "\\" in st.session_state.f2_filepath
                else st.session_state.f2_filepath.rsplit("/", 1)[-1],
                mime="text/markdown",
                key="dl_persist",
            )


def _handle_pdf_upload(uploaded_file, article=None):
    try:
        file_bytes = uploaded_file.read()
        full_text = extract_text(file_bytes)
        if not full_text.strip():
            st.error("无法从 PDF 中提取文本，可能是扫描件。")
            return
        st.success("✅ PDF 文本提取成功。")
        _summarize_and_display(full_text, article)
    except Exception as e:
        st.error(str(e))


def _summarize_and_display(full_text, article=None):
    deepseek_key = st.session_state.config.get("DEEPSEEK_API_KEY", "")

    with st.status("正在概括...", expanded=True) as summary_status:
        st.write("🤖 AI 概括中...")
        try:
            title_for_prompt = article["title"] if article else ""
            summary = summarize(full_text, deepseek_key, article_title=title_for_prompt)
            st.write("✅ 概括完成。")
            summary_status.update(label="完成！", state="complete")
        except Exception as e:
            st.error(f"概括失败: {e}")
            return

    title = article["title"] if article else "untitled"
    filepath = save_markdown(title, summary)

    st.success(f"报告已保存至: `{filepath}`")

    st.session_state.f2_summary = summary
    st.session_state.f2_filepath = filepath

    # Display immediately
    st.markdown("---")
    st.markdown("## 生成报告")
    st.markdown(summary)
    with open(filepath, "r", encoding="utf-8") as f:
        st.download_button(
            label="下载 Markdown",
            data=f,
            file_name=filepath.rsplit("\\", 1)[-1]
            if "\\" in filepath else filepath.rsplit("/", 1)[-1],
            mime="text/markdown",
            key=f"dl_{article['pmid'] if article else 'untitled'}",
        )


def main():
    init_session()

    config = st.session_state.config
    configured = bool(
        config.get("PUBMED_API_KEY") and config.get("DEEPSEEK_API_KEY")
    )

    st.sidebar.title("文献检索与概括 V2")
    if configured:
        st.sidebar.success("API 已配置")
    else:
        st.sidebar.warning("请先配置 API Key")

    page = st.sidebar.radio(
        "功能选择",
        ["Setup", "PubMed 检索", "文章概括"],
        index=0 if not configured else 1,
        label_visibility="collapsed",
    )

    if page == "Setup":
        render_setup()
    elif page == "PubMed 检索":
        if not configured:
            st.warning("请先在 Setup 页面配置 API Key。")
        else:
            render_feature1()
    elif page == "文章概括":
        if not configured:
            st.warning("请先在 Setup 页面配置 API Key。")
        else:
            render_feature2()


if __name__ == "__main__":
    main()
