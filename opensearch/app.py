#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI 应用 —— 把检索 / 导出 / 讲解 / 中转挂成 HTTP 接口。

线上站点（https://www.romancohort.cloud/opensearch/）跑的就是这个 app，
前面套一层 nginx。

    pip install -r requirements-opensearch.txt
    uvicorn opensearch.app:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import asyncio
import json as _json
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from . import ask as askmod
from . import explain as explainmod
from . import relay as relaymod
from . import search as searchmod
from . import sources as srcmod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("opensearch.app")

app = FastAPI(title="OpenSearch", version="1.1.0",
              description="Multi-database paper search with an LLM picking the relevant hits.")


def _stem(q: str, default: str = "opensearch") -> str:
    """下载文件名里那一段 —— **必须纯 ASCII**。

    中文查询会让 starlette 用 latin-1 编响应头时抛 UnicodeEncodeError，
    整个导出 500。注意 str.isalnum() 对汉字返回 True，拿它筛没用。
    """
    stem = "".join(c if (c.isascii() and c.isalnum()) else "-" for c in (q or ""))
    stem = "-".join(x for x in stem.split("-") if x)[:36].strip("-")
    return stem or default


@app.get("/")
def index():
    return {"name": "OpenSearch", "version": app.version,
            "endpoints": ["/api/sources", "/api/papers", "/api/export", "/api/asksearch",
                          "/api/askexport", "/api/explain", "/api/dl", "/api/dl/allow"]}


@app.get("/api/sources")
def api_sources():
    """可选数据库清单 —— 前端勾选框用，只有这一份来源。"""
    return {"sources": [{"key": k, "label": srcmod.LABELS.get(k, k)} for k in srcmod.ADAPTERS]}


@app.get("/api/papers")
async def api_papers(q: str = "", client_id: str = "", source: str = "all"):
    """关键词检索。不中转 PDF —— 只给来源链接。"""
    try:
        return await asyncio.to_thread(searchmod.search, (q or "").strip(),
                                       (client_id or "")[:64], (source or "all")[:24])
    except Exception as e:
        logger.warning("[papers] 失败: %r" % (e,))
        return {"query": q, "items": [], "error": "检索暂时不可用。"}


@app.get("/api/export")
async def api_export(q: str = "", format: str = "json", source: str = "all",
                     client_id: str = ""):
    """把关键词检索的结果导出成文件（json / bibtex / ris）。复用同一次检索的缓存。"""
    fmt = (format or "json").strip().lower()
    if fmt not in ("json", "bibtex", "ris"):
        raise HTTPException(status_code=400, detail="format 只能是 json / bibtex / ris。")
    try:
        data = await asyncio.to_thread(searchmod.search, (q or "").strip(),
                                       (client_id or "")[:64], (source or "all")[:24])
    except Exception as e:
        logger.warning("[export] 失败: %r" % (e,))
        raise HTTPException(status_code=503, detail="导出暂时不可用。")
    return _download(data.get("items") or [], fmt, q, "papers")


@app.get("/api/asksearch")
async def api_asksearch(q: str = "", client_id: str = "", sources: str = ""):
    """「管理员帮你搜」：一句话需求 -> 检索词 -> 多源检索 -> 挑出相关的几条。

    sources: 逗号分隔的数据库 key（如 "arxiv,pdb"），不传 = 全部。
    不认识的 key 直接拒绝，别让前端悄悄降级成「全都搜了」。
    """
    q = (q or "").strip()
    if len(q) < 4:
        return {"error": "多说几个字吧（至少 4 个字符）。"}
    want = [x.strip() for x in (sources or "").split(",") if x.strip()]
    bad = [x for x in want if x not in srcmod.ADAPTERS]
    if bad:
        return {"error": "不认识的数据库：%s" % ", ".join(bad[:6])}
    try:
        return await asyncio.to_thread(askmod.ask, q, (client_id or "")[:64], want or None)
    except Exception as e:
        logger.warning("[asksearch] 失败: %r" % (e,))
        return {"error": "管理员暂时不在，稍后再试。"}


@app.get("/api/askexport")
async def api_askexport(q: str = "", sources: str = "", format: str = "bibtex"):
    """导出「管理员帮你搜」的结果。复用那次的缓存，不会再打一次第三方。"""
    fmt = (format or "bibtex").strip().lower()
    if fmt not in ("json", "bibtex", "ris"):
        raise HTTPException(status_code=400, detail="format 只能是 json / bibtex / ris。")
    want = [x.strip() for x in (sources or "").split(",") if x.strip()]
    bad = [x for x in want if x not in srcmod.ADAPTERS]
    if bad:
        raise HTTPException(status_code=400, detail="不认识的数据库：%s" % ", ".join(bad[:6]))
    q = (q or "").strip()
    if len(q) < 4:
        raise HTTPException(status_code=400, detail="问题太短。")
    try:
        data = await asyncio.to_thread(askmod.ask, q, "export", want or None)
    except Exception as e:
        logger.warning("[askexport] 失败: %r" % (e,))
        raise HTTPException(status_code=503, detail="导出暂时不可用。")
    if data.get("error"):
        raise HTTPException(status_code=409, detail=data["error"])
    return _download(data.get("all") or data.get("items") or [], fmt, q)


@app.get("/api/explain")
async def api_explain(arxiv_id: str = "", title: str = "", abstract: str = "",
                      client_id: str = ""):
    """讲讲一篇论文（缓存一篇一次 + 全局间隔 + 单客户端配额，见 explain.py）。"""
    try:
        return await asyncio.to_thread(explainmod.explain, arxiv_id, title, abstract,
                                       (client_id or "")[:64])
    except Exception as e:
        logger.warning("[explain] 失败: %r" % (e,))
        return {"error": "讲解暂时不可用。"}


@app.get("/api/dl/allow")
def api_dl_allow():
    """中转白名单（前端据此决定哪些下载链接配一个「中转下载」）。"""
    return {"suffixes": relaymod.suffixes()}


@app.get("/api/dl")
def api_dl(request: Request, u: str = ""):
    """文献中转：开放获取的源由本站代取，副本在池子里留 1 小时。

    **不是通用代理** —— 白名单 + 大小上限 + 单 IP 配额 + 全局并发 1，见 relay.py。
    """
    ip = (request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
          or (request.client.host if request.client else "") or "")
    ip = ip.split(",")[0].strip()[:64] or "unknown"
    try:
        job = relaymod.begin(u, ip)
    except relaymod.DlError as e:
        raise HTTPException(status_code=e.code, detail=str(e))
    except Exception as e:
        logger.warning("[dl] 失败: %r" % (e,))
        raise HTTPException(status_code=502, detail="取不到这个文件。")
    headers = {"Content-Disposition": 'attachment; filename="%s"' % job["filename"],
               "X-Content-Type-Options": "nosniff"}
    if job.get("internal"):
        headers["X-Accel-Redirect"] = job["internal"]
        headers["Cache-Control"] = "private, max-age=600"
        return Response(content=b"", media_type=job["ctype"], headers=headers)
    return StreamingResponse(job["gen"](), media_type=job["ctype"], headers=headers)


def _download(items, fmt: str, q: str, prefix: str = "opensearch") -> Response:
    """把条目拼成可下载的响应（json / bibtex / ris），文件名走纯 ASCII。"""
    if fmt == "bibtex":
        body, mime, ext = srcmod.to_bibtex(items), "application/x-bibtex", "bib"
    elif fmt == "ris":
        body, mime, ext = srcmod.to_ris(items), "application/x-research-info-systems", "ris"
    else:
        body = _json.dumps({"query": q, "items": items}, ensure_ascii=False, indent=2)
        mime, ext = "application/json", "json"
    return Response(content=body, media_type=mime + "; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="%s-%s.%s"'
                                                     % (prefix, _stem(q), ext)})
