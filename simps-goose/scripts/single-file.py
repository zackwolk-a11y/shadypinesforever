"""Build the single-file game from the Vite build (run `npx vite build` first).
   release/play.html          — complete standalone page (upload to Netlify / any static host as index.html)
   release/goose-artifact.html — the same game as an artifact page fragment
"""
import glob, re, os
os.makedirs('release', exist_ok=True)
html = open('dist/index.html').read()
js = open(glob.glob('dist/assets/index-*.js')[0]).read()
assert '</script' not in js.replace('<\\/script', '')
page = re.sub(r'<script type="module" crossorigin src="[^"]+"></script>', lambda m: '<script type="module">' + js + '</script>', html)
assert js[:200] in page, 'script tag not inlined'
open('release/play.html', 'w').write(page)
# artifact fragment: title + style + body content (the viewer supplies the document skeleton)
style = re.search(r'<style>.*?</style>', html, re.S).group(0).replace('html, body {', 'html, body { color-scheme: dark;', 1)
body = re.search(r'<body>(.*?)</body>', html, re.S).group(1)
body = re.sub(r'<script type="module" crossorigin src="[^"]+"></script>', '', body).strip()
open('release/goose-artifact.html', 'w').write('<title>Goose on the Loose</title>\n' + style + '\n' + body + '\n<script type="module">' + js + '</script>\n')
print('play.html', len(page) // 1024, 'KB; goose-artifact.html written')

# installable app folder for Netlify / any https host: drag release/pwa (or the zip) onto Netlify Drop
import shutil, zipfile
pwa = 'release/pwa'
shutil.rmtree(pwa, ignore_errors=True); os.makedirs(pwa)
open(os.path.join(pwa, 'index.html'), 'w').write(page)
for f in ['manifest.webmanifest', 'sw.js', 'apple-touch-icon.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png']:
    shutil.copy(os.path.join('dist', f), os.path.join(pwa, f))
open(os.path.join(pwa, '_headers'), 'w').write("/sw.js\n  Cache-Control: no-cache\n/index.html\n  Cache-Control: no-cache\n/manifest.webmanifest\n  Content-Type: application/manifest+json\n")
with zipfile.ZipFile('release/goose-pwa-netlify.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(pwa)): z.write(os.path.join(pwa, f), f)
print('pwa folder + release/goose-pwa-netlify.zip written')
