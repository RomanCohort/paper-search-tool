# Changelog

All notable changes to this project will be documented in this file.

## [1.2.1] - 2026-10-12

### Added
- **PubMed** 数据源（NCBI E-utilities）。不是为了"不重复"——实测同一时间点
  Europe PMC 三次查询全部握手超时（0 条），PubMed 三次都稳（0.34s、8 条）。
  语料重叠但**可达性不同**，多这一条生物医学那块才不至于整块消失

### Fixed
- **中转按钮只有前几条有**（真 bug）：OpenAlex 给的开放获取 PDF 落在
  sciengine / front-sci 这类平台上，手写白名单追不上 → 只有 arXiv 那几条能中转。
  改成「凡是我们从只给开放获取位置的接口（OpenAlex oa_url / Europe PMC OA 全文 /
  DOAJ / Unpaywall）拿到的 URL 都允许中转」，覆盖 8/23 → 17/23
- 中转按钮只挂在**文件链接**上：以前 abs 页面也挂，点了会去下 HTML 再被拒
- 中转改成**先校验再返回**：以前进了流式响应才发现不是 PDF，客户端只拿到 0 字节的 200
- 多检索词时源状态合并写成了「有一个词失败就算整源未连上」，明明拿回十几条也报未连上
- **arXiv 被自己打限流了**：它的 API 要求每 3 秒最多 1 次，多词并搜把请求翻了 3 倍 →
  实测 429 / 正文卡死。现在：走 https（省一次 301）、全局 3 秒闸、**只有主检索词查 arXiv**、
  连续失败 3 次进 15 分钟熔断

## [1.2.0] - 2026-10-12

### Added
- **检索词改成「多词同时搜」**：模型出 2-3 个不同角度的词，并行检索后按
  「主词 10 / 第二词 6 / 第三词 4」的配比合并（实测只用第一个词会扔掉一半结果：126 → 239 条）
- **DOAJ** 数据源（开放获取期刊目录，实测 0.27s）
- **Unpaywall 开放获取解析**：把只有 DOI 的结果换成合法 OA 位置，带 30 天缓存；
  没有 OA 副本的条目在页面上明说「无开放获取」
- **主题大纲 / 思维导图**：`/api/outline` 按主题聚类（不是按来源），页面可折叠展示，
  并可导出 `.md`（markmap 可渲染成脑图）与 `.xmind`（补上老仓库那句空头承诺）
- 中转白名单新增开放获取出版社：PLOS / Frontiers / BMC（实测能直连取到 PDF；MDPI 403 不收）

### Fixed
- 检索结果缓存没有版本号：改了挑选逻辑还会被旧结果端出来 → 加了缓存版本号 + 30 天清理

## [1.1.0] - 2026-10-12

### Added
- **OpenSearch**：自然语言论文检索 —— 一句话需求转检索词，多源并行取数，
  再由 LLM 挑出真正相关的 3-5 条并说明理由（`opensearch/ask.py`）
- 多源适配器注册表：arXiv / Europe PMC / OpenAlex / Crossref / RCSB PDB，
  统一条目形状 + 跨源去重（DOI 与标题双索引）（`opensearch/sources.py`）
- 前端可按数据库勾选检索范围；`/api/sources` 是清单的唯一来源
- 元数据导出：BibTeX / RIS / JSON（关键词检索与自然语言检索都能导）
- 开放获取中转下载：白名单 + 池子（1 小时）+ 单 IP 配额 + 全局并发 1（`opensearch/relay.py`）
- LLM 客户端本地优先、云端兜底，只依赖标准库（`opensearch/llm.py`）
- FastAPI 接口（`opensearch/app.py`）与无框架依赖的前端片段（`web/osui.py`）

### Fixed
- 一个源卡住不再拖垮整次检索：原来 `as_completed` 超时会把**已经回来的源一起丢掉**，
  页面显示「没有命中」；现在照收已完成的，慢源如实记为「超时未返回」
- PDB 无命中时 RCSB 返回空体，`json.loads("")` 直接抛错并白重试一次
- 下载文件名带中文会让响应头 latin-1 编码失败、整个导出 500（`str.isalnum()` 对汉字为真）

### Changed
- 线上站点把该栏目独立成 `/opensearch/`，作为本项目的现场体验

## [1.0.0] - 2026-04-24

### Added
- Streamlit Web 前端界面
- 多模型推理与结果融合
- 熔断机制与重试策略
- 在线验证系统
- 论文数据获取模块
- XMind 格式导出
- 论文真伪识别
- 验证码识别神经网络
