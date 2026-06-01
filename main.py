import streamlit as st
from config import load_config, save_config, is_configured
from pubmed_client import search_pubmed, find_by_title, fetch_pmc_full_text
from summarizer import summarize
from pdf_parser import extract_text
from output_handler import save_markdown

st.set_page_config(page_title="文献检索与概括", layout="wide")


def init_session():
    if "config" not in st.session_state:
        st.session_state.config = load_config()
    if "search_results" not in st.session_state:
        st.session_state.search_results = []


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
    st.markdown("输入关键词，搜索 PubMed Top 30 相关文献。")

    col1, col2 = st.columns([3, 1])
    with col1:
        keywords = st.text_input("关键词", placeholder="例如: gut microbiota brain axis")
    with col2:
        search_btn = st.button("搜索", type="primary", use_container_width=True)

    if search_btn and keywords.strip():
        api_key = st.session_state.config.get("PUBMED_API_KEY", "")
        email = st.session_state.config.get("PUBMED_EMAIL", "")
        try:
            with st.spinner("正在检索 PubMed..."):
                results = search_pubmed(keywords.strip(), api_key, email, max_results=30)
            st.session_state.search_results = results
        except Exception as e:
            st.error(f"检索失败: {e}")
            st.session_state.search_results = []

    results = st.session_state.search_results
    if results:
        st.success(f"共找到 {len(results)} 篇文献")
        st.markdown("---")
        for i, article in enumerate(results, 1):
            with st.expander(f"{i}. {article['title']}"):
                st.markdown(f"**Authors:** {article['authors']}")
                st.markdown(f"**Journal:** {article['journal']} ({article['year']})")
                st.markdown(f"**PMID:** {article['pmid']}")
                if article["abstract"]:
                    st.markdown(f"**Abstract:** {article['abstract']}")
    elif keywords.strip() and not results:
        st.warning("未找到相关文献。")


def render_feature2():
    st.title("文章概括")
    st.markdown("输入文章标题，获取全文并用 AI 生成概括报告。")

    title = st.text_input("文章标题", placeholder="输入完整的文章标题")
    col1, col2 = st.columns([3, 1])
    with col2:
        find_btn = st.button("检索并概括", type="primary", use_container_width=True)

    if find_btn and title.strip():
        api_key = st.session_state.config.get("PUBMED_API_KEY", "")
        email = st.session_state.config.get("PUBMED_EMAIL", "")
        deepseek_key = st.session_state.config.get("DEEPSEEK_API_KEY", "")

        with st.status("正在处理...", expanded=True) as status:
            # Step 1: Find article
            st.write("🔍 第 1 步: 在 PubMed 中检索文章...")
            article = find_by_title(title.strip(), api_key, email)
            if article is None:
                st.error("未找到该文章，请检查标题。")
                return
            st.write(f"✅ 找到文章: {article['title']}")

            # Step 2: Get full text
            st.write("📄 第 2 步: 获取全文...")
            full_text = None
            if article["has_pmc"]:
                st.write(f"找到 PMC ID: {article['pmcid']}")
                full_text = fetch_pmc_full_text(article["pmcid"])
                if full_text:
                    st.write("✅ 已获取 PMC 全文。")
                else:
                    st.write("⚠️ 无法解析 PMC 全文。")
            else:
                st.write("⚠️ 该文章未收录于 PMC。")

            # Step 3: If no full text, ask for PDF
            if full_text is None:
                status.update(label="需要上传 PDF", state="running")
        if full_text is None:
            st.warning("该文章无 PMC 全文。请上传 PDF 文件。")
            uploaded_file = st.file_uploader("上传 PDF", type=["pdf"])
            if uploaded_file is not None:
                try:
                    file_bytes = uploaded_file.read()
                    full_text = extract_text(file_bytes)
                    if not full_text.strip():
                        st.error("无法从 PDF 中提取文本，可能是扫描件。")
                        return
                    st.success("✅ PDF 文本提取成功。")
                except Exception as e:
                    st.error(str(e))
                    return
            else:
                return

        # Step 4: Summarize
        with st.status("正在概括...", expanded=True) as summary_status:
            st.write("🤖 第 3 步: AI 概括中...")
            try:
                summary = summarize(full_text, deepseek_key)
                st.write("✅ 概括完成。")
                summary_status.update(label="完成！", state="complete")
            except Exception as e:
                st.error(f"概括失败: {e}")
                return

        # Step 5: Save
        filepath = save_markdown(article["title"], summary)

        # Display
        st.success(f"报告已保存至: `{filepath}`")
        st.markdown("---")
        st.markdown("## 生成报告")
        st.markdown(summary)

        with open(filepath, "r", encoding="utf-8") as f:
            st.download_button(
                label="下载 Markdown",
                data=f,
                file_name=filepath.rsplit("\\", 1)[-1] if "\\" in filepath else filepath.rsplit("/", 1)[-1],
                mime="text/markdown",
            )


def main():
    init_session()

    config = st.session_state.config
    configured = bool(
        config.get("PUBMED_API_KEY") and config.get("DEEPSEEK_API_KEY")
    )

    st.sidebar.title("文献检索与概括")
    # Show API status
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
