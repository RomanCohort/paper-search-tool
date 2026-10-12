#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM 客户端 —— 只需要一个 chat()，够 ask / explain 用。

为什么手写而不拉 SDK：这套东西总共就发一个 OpenAI 兼容的 POST，标准库
urllib 足够；少一层依赖，也让「本地优先、云端兜底」这条策略一眼看得见。

环境变量：
    OPENAI_BASE_URL / OPENAI_API_KEY / OPENAI_MODEL          云端（兜底那份）
    LOCAL_LLM_BASE_URL / LOCAL_LLM_API_KEY / LOCAL_LLM_MODEL 本地（优先那份）
    PAPER_LLM_SKIP_LOCAL=1     跳过本地那份（本地机器停着时能省掉一轮必失败的等待）
    OPENSEARCH_LLM_TIMEOUT     秒，默认 90
    OPENSEARCH_LLM_MAX_TOKENS  默认 2048

线上部署时 LOCAL_LLM_BASE_URL 指向跑在开发机上的 llama.cpp（经隧道回来），
云端那份是 DeepSeek。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


class LLMError(Exception):
    pass


def _entry(base_url, api_key, model):
    return {"base_url": (base_url or "").rstrip("/"), "api_key": api_key or "", "model": model or ""}


class LLM:
    """一个 chat(messages, temperature=None) -> str 的壳。

    primary 挂了（超时 / 5xx / 连不上）就自动走 fallback —— 线上主端点跑在
    开发机上，那台机器训练或出图时随时可能不理人。
    """

    def __init__(self, primary, fallback=None, timeout=90.0, temperature=0.7,
                 max_tokens=2048):
        self.primary = primary
        self.fallback = fallback
        self.timeout = float(timeout)
        self.temperature = float(temperature)
        self.max_tokens = int(max_tokens)

    def _one(self, entry, messages, temperature, timeout):
        if not entry.get("base_url"):
            raise LLMError("没有配置 base_url")
        body = json.dumps({
            "model": entry.get("model") or "default",
            "messages": messages,
            "temperature": self.temperature if temperature is None else float(temperature),
            "max_tokens": self.max_tokens,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if entry.get("api_key"):
            headers["Authorization"] = "Bearer " + entry["api_key"]
        req = urllib.request.Request(entry["base_url"] + "/chat/completions",
                                     data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        choices = data.get("choices") or []
        if not choices:
            raise LLMError("返回里没有 choices")
        return ((choices[0].get("message") or {}).get("content") or "").strip()

    def chat(self, messages, temperature=None):
        try:
            return self._one(self.primary, messages, temperature, self.timeout)
        except Exception as e:
            if not self.fallback:
                raise
            last = e
        return self._one(self.fallback, messages, temperature, self.timeout)


def from_env():
    """按环境变量拼一个客户端：本地优先，云端兜底。"""
    cloud = _entry(os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
                   os.environ.get("OPENAI_API_KEY", ""),
                   os.environ.get("OPENAI_MODEL", "deepseek-chat"))
    local = None
    if os.environ.get("LOCAL_LLM_BASE_URL"):
        local = _entry(os.environ["LOCAL_LLM_BASE_URL"],
                       os.environ.get("LOCAL_LLM_API_KEY", ""),
                       os.environ.get("LOCAL_LLM_MODEL", "local"))
    kw = dict(timeout=float(os.environ.get("OPENSEARCH_LLM_TIMEOUT", "90")),
              max_tokens=int(os.environ.get("OPENSEARCH_LLM_MAX_TOKENS", "2048")))
    if local and os.environ.get("PAPER_LLM_SKIP_LOCAL") != "1":
        return LLM(local, fallback=cloud, **kw)
    return LLM(cloud, **kw)
