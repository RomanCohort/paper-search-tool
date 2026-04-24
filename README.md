# 论文搜索整理辅助工具 (Paper Search Tool)

基于 AI 的论文搜索与整理工具，提供多模型推理、结果融合与在线验证。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-orange)

## 功能特性

- **主题搜索**：输入感兴趣的研究主题，AI 自动检索并整理
- **多模型融合**：多个 AI 模型并行推理，结果智能融合
- **熔断机制**：防止单模型故障影响整体服务（可配置阈值与冷却时间）
- **在线验证**：对生成结果进行自动校验
- **可配置参数**：创造性、超时、重试策略等均可调节

## 项目结构

```
├── streamlit.py          # Web 前端入口
├── utils.py              # 核心工具函数与流水线
├── import_requests.py    # 论文数据获取模块
├── Xmind.py              # XMind 格式导出支持
├── identify_fake.py      # 论文真伪识别
├── neural_network.py     # 神经网络验证码识别
├── check_imports.py      # 依赖检查工具
├── Type_plus.cpp         # Windows 点击器 (C++)
├── 生成训练用验证码.cpp    # 验证码训练样本生成器
└── requirements.txt      # Python 依赖
```

## 安装

```bash
git clone https://github.com/RomanCohort/paper-search-tool.git
cd paper-search-tool
pip install -r requirements.txt
```

## 运行

```bash
streamlit run streamlit.py
```

## 配置

运行后在界面中输入 API Key，或设置环境变量。

## 依赖

- streamlit >= 1.32
- langchain, openai, tiktoken
- requests, beautifulsoup4
- pillow, numpy

## 许可证

MIT License
