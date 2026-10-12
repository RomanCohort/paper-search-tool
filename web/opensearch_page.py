#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染「OpenSearch」页 —— /opensearch/ 与 /opensearch/en/。

这是 **paper-search-tool 项目的现场体验**：站上那个「管理员帮你搜」本体。
它跟「每日文献」是两件事 —— 每日文献每天一篇、由站里的定时任务产出；
OpenSearch 是随用随搜的工具：按问题去多个学术库取数，再由管理员挑出相关几条。

页面内容（表单 + JS）在 osui.py 里，这一层只负责套站点外壳；数据库清单
由前端从 /api/sources 拿（只有一份来源），勾选结果作为 sources=... 传回去。
site.yml 里标 dynamic: true，让 sitepages 跳过本页（否则会被空 body 盖掉）。
"""
import os
import sys

sys.path.insert(0, '/opt/sitegen')
import sitegen as S          # noqa: E402
import sitepages as SP       # noqa: E402
import osui                  # noqa: E402


def main():
    cfg = S.load_config()
    page = None
    for p in (cfg.get('pages') or []):
        if p.get('id') == 'opensearch':
            page = p
            break
    if not page:
        print('[opensearch] site.yml 里没有 id: opensearch 的页，什么都不做')
        return 1
    base = page['path'].rstrip('/')
    for lang, suffix in (('zh', '/index.html'), ('en', '/en/index.html')):
        p = dict(page)
        p['body_zh' if lang == 'zh' else 'body_en'] = osui.page_body(lang == 'zh')
        html_out = SP.render_subpage(cfg, lang, p)
        out = os.path.join(S.WEBROOT, base.lstrip('/') + suffix)
        d = os.path.dirname(out)
        if not os.path.isdir(d):
            os.makedirs(d)
        tmp = out + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            fh.write(html_out)
        os.replace(tmp, out)
        print('[opensearch] 写入 %s (%d 字节)' % (out, len(html_out.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
