# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本地文献检索与概括工具，基于 Streamlit。两个核心功能：
1. PubMed 关键词检索 Top 30 文献（按相关性排序）
2. 按标题获取文章全文（优先 PMC），用 DeepSeek AI 概括为 Markdown

## 运行

```bash
pip install -r requirements.txt
streamlit run main.py
```

首次启动进入 Setup 页面配置 API key，密钥保存到 `.env` 文件。

## 架构

模块依赖自上而下：

```
main.py          # Streamlit UI，所有页面渲染 + session state
├── config.py    # .env 读写（load_config/save_config/is_configured）
├── pubmed_client.py  # PubMed E-utilities 封装
│   ├── search_pubmed()      # esearch → efetch → parse XML → list[dict]
│   ├── find_by_title()      # 精确标题匹配，返回 dict 含 pmcid/has_pmc
│   └── fetch_pmc_full_text()  # PMC XML body → 纯文本
├── summarizer.py    # DeepSeek API（OpenAI 兼容协议）
│   └── summarize()  # 注入 SUMMARIZE_PROMPT，带指数退避重试
├── pdf_parser.py    # pdfplumber 提取 PDF 文本
├── prompts.py       # SUMMARIZE_PROMPT 常量（中文，5-section 格式要求）
└── output_handler.py  # Markdown 保存 + 文件名 sanitize
```

### 两个数据流

**功能1 — 检索**: 关键词 → `search_pubmed()` → Entrez.esearch (sort=relevance) → 获取 PMID 列表 → Entrez.efetch → 解析 PubMed XML → `list[dict]` 含 title/authors/journal/year/abstract → Streamlit 表格 + 可展开详情

**功能2 — 概括**: 标题 → `find_by_title()` (exact title match `"[Title]"`) → 提取 PMCID → `fetch_pmc_full_text()` 解析 PMC XML body 段落 → DeepSeek 概括 → `save_markdown()` 到 `outputs/` 目录

### API key 管理

`.env` 文件存持久配置（不在 git 中），Streamlit `session_state` 做运行时缓存。`config.py` 的 `is_configured()` 检查双 key 是否为非空 — UI 据此拦截未配置用户。

### PubMed 速率限制

`pubmed_client.py` 模块级 `_MIN_INTERVAL = 0.1s`（10 req/s，需要 API key）。每次 Entrez 调用前 `_wait_for_rate_limit()` 确保最小间隔。

### PMC 全文获取路径

1. 有 PMCID → 调用 Entrez.efetch(db="pmc")，解析 XML `<body>` 下所有 `<p>` 标签
2. 无 PMCID 或解析失败 → Streamlit UI 提示用户上传 PDF → `pdf_parser.extract_text()` 提取文本
3. 两种情况最终都送入 `summarizer.summarize()`，超长文本截断至 60K 字符

### 概括输出格式

5-section 中文 Markdown：文章标题 → 英文摘要 → 中文全文概括(≤500字) → 科学问题 → 每张图含义+研究方法
