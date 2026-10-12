#!/usr/bin/env python3
"""Build the public GitHub Pages copy of the club site.

The claude.ai artifact (https://claude.ai/artifact/YADtXb155N8ELUqTMrMS5Y) is the
editing back end. Download its published files into SRC (index.html, data/, img/),
then run:  python3 tools/build.py SRC .

What it changes for the public copy:
- removes private member fields (birthday, spouse, spouse birthday, RI number)
- removes the admin link
- points the "分享到 FB" button at a per-post page, p/<id>.html
- lets https://rotarykn.github.io/#ev-<id> open that post directly
- writes p/<id>.html with Facebook preview tags (title, text, photo)
"""
import html, json, os, re, shutil, sys

SITE = 'https://rotarykn.github.io'
ARTIFACT = 'https://claude.ai/artifact/YADtXb155N8ELUqTMrMS5Y'
PRIVATE_MEMBER_FIELDS = ('bd', 'spouse', 'sbd', 'ri')

# Runs inside the page's main script, so it can see S, evTab, evYr, route and renderEvents.
DEEPLINK_JS = (
    "(function(){let want=null,tries=0;"
    "const open=()=>{if(!want)return;const it=S.events.find(x=>String(x.id)===want);"
    "if(!it){if(++tries<40)setTimeout(open,250);return}"
    "evTab=it.cat||CATS[0];evYr='all';history.replaceState(null,'','#events');route();renderEvents();"
    "const a=document.getElementById('ev-'+want);want=null;if(!a)return;"
    "const to=()=>{const h=document.querySelector('header');window.scrollTo(0,a.getBoundingClientRect().top+scrollY-(h?h.offsetHeight:0)-12)};"
    "[50,600,1500].forEach(t=>setTimeout(to,t))};"
    "const go=()=>{const m=/^#ev-(.+)$/.exec(location.hash);if(m){want=decodeURIComponent(m[1]);tries=0;open()}};"
    "window.addEventListener('hashchange',go);go()})();"
)


def sub_once(pattern, repl, text, label):
    new, n = re.subn(pattern, repl, text, count=1)
    if n != 1:
        sys.exit('build: could not find ' + label)
    return new


def first_image(it):
    imgs = [o for o in (it.get('imgs') or []) if isinstance(o, dict) and o.get('s') and not o['s'].startswith('data:')]
    pick = next((o for o in imgs if o.get('b')), imgs[0] if imgs else None)
    return pick['s'] if pick else ''


def post_page(it):
    pid = str(it['id'])
    title = it.get('title') or '活動花絮'
    body = re.sub(r'\s+', ' ', it.get('body') or '').strip()
    desc = (body[:150] + '…') if len(body) > 150 else body
    img = first_image(it)
    target = '/#ev-' + pid
    e = lambda s: html.escape(s, quote=True)
    tags = [
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="高雄北區扶輪社">',
        '<meta property="og:title" content="%s">' % e(title),
        '<meta property="og:description" content="%s">' % e(desc),
        '<meta property="og:url" content="%s/p/%s.html">' % (SITE, e(pid)),
    ]
    if img:
        tags.append('<meta property="og:image" content="%s/%s">' % (SITE, e(img)))
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s｜高雄北區扶輪社</title><meta name="description" content="%s">%s'
            '<link rel="canonical" href="%s/p/%s.html">'
            '<script>location.replace(%s)</script></head>'
            '<body style="font-family:sans-serif;padding:24px"><p>正在前往「%s」…</p>'
            '<p><a href="%s">如果沒有自動跳轉，請按這裡</a></p></body></html>\n'
            % (e(title), e(desc), ''.join(tags), SITE, e(pid), json.dumps(target), e(title), e(target)))


def main(src, out):
    t = open(os.path.join(src, 'index.html'), encoding='utf-8').read()

    m = re.search(r'(<script type="application/json" id="members-data">)(.*?)(</script>)', t, re.S)
    if not m:
        sys.exit('build: members-data not found')
    members = json.loads(m.group(2))
    for x in members:
        for k in PRIVATE_MEMBER_FIELDS:
            x.pop(k, None)
    t = t[:m.start(2)] + json.dumps(members, ensure_ascii=False).replace('</', '<\\/') + t[m.end(2):]

    t = sub_once(r'｜<a href="#admin">消息管理</a>', '', t, 'admin link')
    t = sub_once(r"encodeURIComponent\('" + re.escape(ARTIFACT) + r"'\)",
                 "encodeURIComponent('" + SITE + "/p/'+encodeURIComponent(it.id)+'.html')", t, 'share url')
    t = sub_once(r"const a=el\('article','ev'\),im=norm\(it\.imgs\);",
                 "const a=el('article','ev'),im=norm(it.imgs);if(it.id)a.id='ev-'+it.id;", t, 'event article')
    og = ('<meta property="og:title" content="高雄北區扶輪社">'
          '<meta property="og:description" content="高雄北區扶輪社官方網站：例會、活動花絮、社友與歷屆大事紀。">'
          '<meta property="og:url" content="%s/">' % SITE)
    t = sub_once(r'<title>高雄北區扶輪社</title>', '<title>高雄北區扶輪社</title>' + og, t, 'title')
    t = sub_once(r"renderMembers\(\);route\(\);Object\.keys\(YF\)",
                 lambda m: 'renderMembers();route();' + DEEPLINK_JS + 'Object.keys(YF)', t, 'startup code')

    for d in ('data', 'img', 'p'):
        shutil.rmtree(os.path.join(out, d), ignore_errors=True)
    shutil.copytree(os.path.join(src, 'data'), os.path.join(out, 'data'))
    shutil.copytree(os.path.join(src, 'img'), os.path.join(out, 'img'))
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(t)
    open(os.path.join(out, '.nojekyll'), 'w').close()

    os.makedirs(os.path.join(out, 'p'))
    n = 0
    for f in sorted(os.listdir(os.path.join(src, 'data'))):
        if f.startswith('events-') and f.endswith('.json'):
            for it in json.load(open(os.path.join(src, 'data', f), encoding='utf-8')):
                if it.get('id'):
                    open(os.path.join(out, 'p', str(it['id']) + '.html'), 'w', encoding='utf-8').write(post_page(it))
                    n += 1
    print('built index.html, %d members, %d post pages' % (len(members), n))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
