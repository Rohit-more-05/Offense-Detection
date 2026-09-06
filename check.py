import urllib.request
import re

html = urllib.request.urlopen('https://memeguard-frontend.onrender.com/assets/index-BzAnB7pe.js').read().decode('utf-8')
urls = set(re.findall(r'https?://[^\'\"\)\]]+', html))
for u in urls:
    if 'memeguard' in u or 'localhost' in u:
        print(u)
