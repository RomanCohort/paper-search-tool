#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenSearch 前端的共用片段 —— 每日文献页与 OpenSearch 页只用这一份。

这些 JS 原来抄在 daily_page.py 里；搜索独立成 /opensearch/ 之后要是两边各写
一遍，迟早行为不一样（悬浮球那次就是这么漂的：只灌了一处，另外几页停在旧版）。

本模块**不依赖站点框架**（不 import sitegen/sitepages），所以仓库里那份
自包含演示页（web/standalone.py）也能直接用它。
"""

REPO = 'https://github.com/RomanCohort/paper-search-tool'

CORE_JS = u"""<script>
window.API = window.API || '';          // 同域时留空；自包含演示页可以指到别的后端
window.RCO = (function () {
  var cid = localStorage.getItem('rc_cid');
  if (!cid) { cid = 'c' + Math.random().toString(36).slice(2, 12); localStorage.setItem('rc_cid', cid); }
  function esc(t) { var d = document.createElement('div'); d.textContent = t == null ? '' : t; return d.innerHTML; }
  function itemHtml(it) {
    var u = it.url || it.abs_url || '';
    var links = ['<a href="' + esc(u) + '">abs</a>'];
    if (it.pdf_url) links.push('<a href="' + esc(it.pdf_url) + '">' + esc(it.file_label || 'PDF') + '</a>');
    return '<div class="item"><div class="when">' + esc((it.date || '').slice(0, 7)) + '</div><div>'
         + '<h3><a href="' + esc(u) + '">' + esc(it.title) + '</a></h3>'
         + '<p class="meta">' + (it.source_label ? '<span class="tag">' + esc(it.source_label) + '</span> ' : '') + esc(it.authors) + '</p>'
         + '<p class="meta">' + links.join(' · ') + '</p></div></div>';
  }
  // 一条结果（带序号、推荐标记、可展开的摘要）。序号和「管理员的话」里的
  // #0/#4 是同一套编号 —— 都用 all 里的下标，所以 0 起。
  function rowHtml(it, i, starred) {
    var u = it.url || it.abs_url || '';
    var links = ['<a href="' + esc(u) + '">abs</a>'];
    if (it.pdf_url) links.push('<a href="' + esc(it.pdf_url) + '">' + esc(it.file_label || 'PDF') + '</a>');
    var abs = it.abstract
      ? '<details><summary class="meta">摘要</summary><p class="meta">' + esc(it.abstract) + '</p></details>' : '';
    return '<div class="item"><div class="when">' + esc((it.date || '').slice(0, 7)) + '</div><div>'
         + '<h3>' + (starred ? '<span title="管理员挑出来的" style="color:#c60">★</span> ' : '')
         + '<span style="color:#999;font-size:.85em">#' + i + '</span> '
         + '<a href="' + esc(u) + '">' + esc(it.title) + '</a></h3>'
         + '<p class="meta">' + (it.source_label ? '<span class="tag">' + esc(it.source_label) + '</span> ' : '')
         + esc(it.authors) + '</p>'
         + '<p class="meta">' + links.join(' · ') + '</p>' + abs + '</div></div>';
  }
  function deadList(status) {
    var out = [];
    if (status) { for (var k in status) { if (status[k] && !status[k].ok) out.push(k); } }
    return out;
  }
  // 「中转下载」：开放获取的链接由本站代取（国内直连慢），副本留 1 小时。
  // 白名单只从 /api/dl/allow 拿，前端不再抄一份，免得两边漂移。
  var DL_ALLOW = null;
  function withAllow(cb) {
    if (DL_ALLOW) { cb(DL_ALLOW); return; }
    try {
      var c = JSON.parse(localStorage.getItem('rc_dlallow') || 'null');
      if (c && c.at && (Date.now() - c.at) < 86400000 && c.list) { DL_ALLOW = c.list; cb(DL_ALLOW); return; }
    } catch (e) {}
    fetch(window.API + '/api/dl/allow').then(function (r) { return r.json(); }).then(function (d) {
      DL_ALLOW = d.suffixes || [];
      try { localStorage.setItem('rc_dlallow', JSON.stringify({ at: Date.now(), list: DL_ALLOW })); } catch (e) {}
      cb(DL_ALLOW);
    }).catch(function () { DL_ALLOW = []; cb(DL_ALLOW); });
  }
  function decorate(scope) {
    withAllow(function (list) {
      if (!list.length) return;
      var as = (scope || document).querySelectorAll('a[href]');
      Array.prototype.forEach.call(as, function (a) {
        if (a.getAttribute('data-relay') === '1') return;
        var h;
        try { h = new URL(a.href, location.href).hostname.toLowerCase(); } catch (e) { return; }
        var ok = list.some(function (s) { return h === s || h.endsWith('.' + s); });
        if (!ok) return;
        a.setAttribute('data-relay', '1');
        var span = document.createElement('span');
        span.className = 'relay';
        span.appendChild(document.createTextNode(' · '));
        var lk = document.createElement('a');
        lk.href = window.API + '/api/dl?u=' + encodeURIComponent(a.href);
        lk.textContent = '中转下载';
        lk.title = '由本站代取（开放获取，副本留一小时）';
        span.appendChild(lk);
        a.parentNode.insertBefore(span, a.nextSibling);
      });
    });
  }
  // 这里导出的东西才是页面能用的 —— 少写一个就在运行时变成
  // "R.xxx is not a function"，然后被 fetch 的 .catch 吞成「网络出错了」。
  return { cid: cid, esc: esc, itemHtml: itemHtml, rowHtml: rowHtml,
           deadList: deadList, decorate: decorate };
})();
</script>
"""

# 只给页面补「中转下载」入口的页（每日文献）用这个。
RELAY_ONLY = CORE_JS + u"""<script>
(function () { if (window.RCO) window.RCO.decorate(document); })();
</script>
"""


DAILY_JSON = '/opt/arxiv-push/daily.json'


def daily_block(zh, path=None, keep=1):
    """搜索框上端那条「每日文献」。

    读站里那份 daily.json（读不到就返回空串 —— 仓库里那份自包含演示页
    没有这个文件，依然要能跑）。这是用户要的排布：每日文献在搜索框之上。
    """
    import html as _h
    import io as _io
    import json as _json
    try:
        with _io.open(path or DAILY_JSON, encoding='utf-8') as fh:
            items = (_json.load(fh).get('items') or [])[:keep]
    except Exception:
        return u''
    if not items:
        return u''
    it = items[0]
    title = _h.escape(str(it.get('title') or u'(无标题)'))
    note = _h.escape(str((it.get('summary_zh') if zh else it.get('summary_en'))
                         or it.get('summary_zh') or u'')[:240])
    date = _h.escape(str(it.get('date') or ''))
    return (u'<section id="daily-top" style="border-left:3px solid var(--rule);'
            u'padding:.2rem 0 .2rem .8rem;margin:0 0 1.2rem">\n'
            u'  <p class="meta" style="margin:0">%s</p>\n'
            u'  <h3 style="margin:.2rem 0">%s</h3>\n'
            u'  <p style="margin:.2rem 0">%s</p>\n'
            u'  <p class="meta" style="margin:.2rem 0">%s · <a href="%s">%s</a></p>\n'
            u'</section>\n'
            % (u'每日文献 · 今天' if zh else u'Daily paper',
               title, note, date,
               u'/daily/' if zh else u'/daily/en/',
               u'看全部 →' if zh else u'see all →'))


def page_block(zh, top=u""):
    """OpenSearch 页的正文档 —— 表单 + 结果区（数据库勾选框由 JS 填）。

    top：塞在表单**上端**的内容（每日文献那块就是这么来的）。
    """
    if zh:
        lead = (u'一句话说你要什么（中文就行），它去几个学术库里取数，'
                u'再由本站的管理员挑出真正相关的那几条，并说明理由。')
        how = (u'检索在 <b>arXiv</b>、<b>Europe PMC</b>、<b>OpenAlex</b>、'
               u'<b>Crossref</b>、<b>RCSB PDB</b> 上并行进行，可以只选你要的那几个；'
               u'重复的条目会按 DOI 与标题合并。结果只给来源链接，'
               u'开放获取的可以走「中转下载」，元数据（BibTeX / RIS / JSON）可导出。')
        src_line = u'项目源码：'
        dbt, sel = u'检索范围', u'全选'
        ph = u'例如：最近有什么关于 RNA 逆设计的好文章'
        btn, hint = u'让管理员搜', u'管理员正在翻资料…（多个库一起跑，可能要十几秒）'
        exp = u'导出这次结果'
    else:
        lead = (u'Describe what you need in one sentence. OpenSearch fans out to several '
                u'academic databases, then this site\'s administrator picks the few that '
                u'actually fit, and says why.')
        how = (u'Searching runs in parallel over <b>arXiv</b>, <b>Europe PMC</b>, '
               u'<b>OpenAlex</b>, <b>Crossref</b> and <b>RCSB PDB</b> — tick only the ones '
               u'you want; duplicates are merged by DOI and title. Results link back to the '
               u'source; open-access items offer a relay download, and metadata can be '
               u'exported as BibTeX / RIS / JSON.')
        src_line = u'Source: '
        dbt, sel = u'Databases', u'all'
        ph = u'e.g. anything good on RNA inverse design lately?'
        btn, hint = u'Ask the administrator', u'Searching several databases at once — this can take a while…'
        exp = u'Export these results'
    btn_css = ('padding:.5rem 1rem;border:1px solid var(--rule);border-radius:6px;'
               'cursor:pointer;font:inherit')
    inp_css = ('flex:1;padding:.5rem .6rem;border:1px solid var(--rule);'
               'border-radius:6px;font:inherit')
    mini_css = ('padding:.15rem .5rem;border:1px solid var(--rule);border-radius:5px;'
                'cursor:pointer;font:inherit;font-size:.85em')
    return u"""
<section id="opensearch">
  <p class="lead">%s</p>
  <p class="meta">%s</p>
  <p class="meta">%s<a href="%s">%s</a></p>
  %s
  <form id="askform" autocomplete="off">
    <div id="dbset" style="margin:.6rem 0">
      <span class="meta" style="margin-right:.4rem">%s</span>
      <span><button type="button" id="dball" style="%s">%s</button></span>
    </div>
    <div style="display:flex;gap:.5rem;max-width:40rem">
      <input id="askq" type="search" placeholder="%s" aria-label="%s" style="%s">
      <button type="submit" id="askbtn" style="%s">%s</button>
    </div>
  </form>
  <p class="meta" id="askmsg"></p>
  <div id="asksay"></div>
  <div id="askexp" class="meta"></div>
  <div id="askres"></div>
</section>
""" % (lead, how, src_line, REPO, REPO.split('//', 1)[1],
       top, dbt, mini_css, sel, ph, ph, inp_css, btn_css, btn)


# 页面上直接用的文案（生成时替换进下面的 %HINT% / %EXP%）
HINT_ZH = u'管理员正在翻资料…（多个库一起跑，可能要十几秒）'
HINT_EN = u'Searching several databases at once — this can take a while…'
EXP_ZH = u'导出这次结果'
EXP_EN = u'Export these results'

ASK_JS = u"""
<script>
(function () {
  var API = window.API || '';
  var R = window.RCO;
  if (!R) return;
  var form = document.getElementById('askform');
  if (!form) return;
  var q = document.getElementById('askq'), msg = document.getElementById('askmsg'),
      say = document.getElementById('asksay'), res = document.getElementById('askres'),
      exp = document.getElementById('askexp'), btn = document.getElementById('askbtn'),
      db = document.getElementById('dbset');

  function picked() {
    var out = [];
    db.querySelectorAll('input[type=checkbox]').forEach(function (c) { if (c.checked) out.push(c.value); });
    return out;
  }
  // 分页：一次给 10 条，能翻到全部（服务端最多带回 60 条）。
  var PAGE = 10, page = 1, LAST = null;
  function show(d) {
    LAST = d;
    var all = d.all || [];
    var total = d.total || all.length;
    var star = {};
    (d.picks || []).forEach(function (i) { star[i] = 1; });
    var pages = Math.max(1, Math.ceil(all.length / PAGE));
    if (page > pages) page = pages;
    if (page < 1) page = 1;
    var html = '';
    if (!all.length) {
      html = '<p class="meta">它这次没翻到结果。</p>';
    } else {
      var from = (page - 1) * PAGE;
      all.slice(from, from + PAGE).forEach(function (it, k) {
        html += R.rowHtml(it, from + k, star[from + k]);
      });
      html += '<p class="meta">共 ' + total + ' 条'
            + (all.length < total ? '（带回前 ' + all.length + ' 条）' : '')
            + ' · 第 ' + page + ' / ' + pages + ' 页 '
            + '<button type="button" id="askprev"' + (page <= 1 ? ' disabled' : '') + '>上一页</button> '
            + '<button type="button" id="asknext"' + (page >= pages ? ' disabled' : '') + '>下一页</button></p>';
    }
    res.innerHTML = html;
    var pb = document.getElementById('askprev'), nb = document.getElementById('asknext');
    if (pb) pb.addEventListener('click', function () { page -= 1; show(LAST); });
    if (nb) nb.addEventListener('click', function () { page += 1; show(LAST); });
    R.decorate(res);
  }
  // 数据库清单只从 /api/sources 来，页面里不写死
  fetch(API + '/api/sources').then(function (r) { return r.json(); }).then(function (d) {
    (d.sources || []).forEach(function (s) {
      var lab = document.createElement('label');
      lab.style.cssText = 'margin-right:.8rem;white-space:nowrap';
      var cb = document.createElement('input');
      cb.type = 'checkbox'; cb.value = s.key; cb.checked = true;
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(' ' + s.label));
      db.appendChild(lab);
    });
  }).catch(function (e) { msg.textContent = '数据库清单没取到：' + ((e && e.message) || '网络请求失败'); });
  document.getElementById('dball').addEventListener('click', function () {
    var boxes = db.querySelectorAll('input[type=checkbox]');
    var on = picked().length !== boxes.length;
    boxes.forEach(function (c) { c.checked = on; });
  });

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var kw = (q.value || '').trim();
    var srcs = picked();
    if (kw.length < 4) { msg.textContent = '多说几个字吧（至少 4 个字符）。'; return; }
    if (!srcs.length) { msg.textContent = '至少选一个数据库。'; return; }
    msg.textContent = '%HINT%';
    say.innerHTML = ''; res.innerHTML = ''; exp.innerHTML = '';
    btn.disabled = true;
    var qs = 'q=' + encodeURIComponent(kw) + '&sources=' + encodeURIComponent(srcs.join(','))
           + '&client_id=' + encodeURIComponent(R.cid);
    fetch(API + '/api/asksearch?' + qs)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btn.disabled = false;
        if (d.error) { msg.textContent = d.error; return; }
        var bits = [];
        if (d.queries && d.queries.length) bits.push('检索词：' + d.queries.join(' / '));
        if (d.cached) bits.push('缓存');
        var dead = R.deadList(d.status);
        if (dead.length) bits.push('本次未连上：' + dead.join(', '));
        msg.textContent = bits.join('｜');
        say.innerHTML = d.say ? '<blockquote>' + R.esc(d.say) + '</blockquote>' : '';
        page = 1;
        show(d);
        // 导出走同一份缓存，不会再打一次第三方
        var base = API + '/api/askexport?' + qs + '&format=';
        exp.innerHTML = '%EXP%：'
          + '<a href="' + base + 'bibtex">BibTeX</a> · '
          + '<a href="' + base + 'ris">RIS</a> · '
          + '<a href="' + base + 'json">JSON</a>';
      })
      // 别把任何异常都说成「网络出错」——那会把页面自己的 JS 错误藏起来。
      .catch(function (e) {
        btn.disabled = false;
        msg.textContent = '出错了：' + ((e && e.message) || '请求失败');
      });
  });
})();
</script>
"""


def page_body(zh, api_base="", top=None):
    """整块页面内容（表单 + JS）。api_base 留空 = 同域（站上就是这么用的）。

    top 默认取站里的每日文献（仓库里那份演示页没有 daily.json，自动为空）。
    """
    if top is None:
        top = daily_block(zh)
    js = ASK_JS.replace('%HINT%', HINT_ZH if zh else HINT_EN)
    js = js.replace('%EXP%', EXP_ZH if zh else EXP_EN)
    # **HTML 必须在脚本之前**：脚本按文档顺序执行，反过来跑的话
    # document.getElementById('askform') 拿到 null，整段 JS 直接 return ——
    # 勾选框和搜索框一起消失（线上就是这么坏的，浏览器缓存不是原因）。
    return (page_block(zh, top)
            + u'<script>window.API = %s;</script>\n' % (u"'" + api_base + u"'")
            + CORE_JS
            + js
            + u'<script>(function(){ if (window.RCO) window.RCO.decorate(document); })();</script>\n')
