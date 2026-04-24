# 论文搜索整理辅助工具

一个基于 AI 的论文搜索和整理工具，提供多模型推理、结果融合和在线验证功能。

## 功能特性

- **主题搜索**：输入感兴趣的研究主题
- **多模型融合**：支持多个 AI 模型并行推理，结果智能融合
- **熔断机制**：防止单模型故障影响整体服务
- **在线验证**：对生成结果进行校验
- **可配置参数**：支持调整创造性、超时、熔断阈值等

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
streamlit run streamlit.py
```

## 项目结构

- `streamlit.py` - Web 前端入口
- `utils.py` - 核心工具函数
- `import_requests.py` - 论文数据获取模块
- `Xmind.py` - XMind 格式支持
- `identify_fake.py` - 论文真伪识别

## 配置

运行前需要配置 API Key，可在界面中输入或设置环境变量。
