# Changelog

All notable changes to this project will be documented in this file.

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
