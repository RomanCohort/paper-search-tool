#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 OpenSearch 的前端片段拼成一个**自包含**的单文件演示页。

前端片段（osui.py）本来是嵌在站点生成器里的，这里只做一件事：给它一个
最小外壳，让没有那套框架的人也能跑起来看。

    python web/standalone.py > opensearch.html          # 同域后端
    python web/standalone.py --api http://127.0.0.1:8000 > opensearch.html
    python web/standalone.py --lang en > opensearch-en.html

打开这个 html 就能用（前提是后端在 --api 那个地址上跑着）。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osui          # noqa: E402

TPL = """<!doctype html>
<html lang="%(lang)s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OpenSearch</title>
<style>
  :root { --rule: #d8d8d8; --ink: #222; }
  body { max-width: 52rem; margin: 2rem auto; padding: 0 1rem; color: var(--ink);
         font: 16px/1.7 -apple-system, "Segoe UI", Roboto, "Noto Sans SC", sans-serif; }
  h1 { font-size: 1.4rem; margin-bottom: .2rem; }
  .meta { color: #666; font-size: .9rem; }
  .lead { font-size: 1.02rem; }
  blockquote { margin: .9rem 0; padding: .7rem 1rem; border-left: 3px solid var(--rule);
               background: #fafafa; }
  .item { display: flex; gap: 1rem; padding: .9rem 0; border-top: 1px solid var(--rule); }
  .item h3 { margin: .1rem 0 .3rem; font-size: 1rem; }
  .when { width: 6rem; flex: none; color: #888; font-size: .85rem; }
  .tag { border: 1px solid var(--rule); border-radius: 4px; padding: 0 .3rem; font-size: .8em; }
  .relay { color: #06c; }
</style>
</head>
<body>
<h1>OpenSearch</h1>
<p class="meta">paper-search-tool · %(repo)s</p>
%(body)s
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--api', default='', help='后端地址；留空 = 同域')
    ap.add_argument('--lang', default='zh', choices=('zh', 'en'))
    a = ap.parse_args()
    sys.stdout.write(TPL % {'lang': 'zh-CN' if a.lang == 'zh' else 'en',
                            'repo': osui.REPO,
                            # top='' ：不看站里的 daily.json，纯工具页
                            'body': osui.page_body(a.lang == 'zh', a.api, top=u'')})
    return 0


if __name__ == '__main__':
    sys.exit(main())
