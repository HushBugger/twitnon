#!/usr/bin/env python3
# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty. This file is offered
# as-is, without any warranty.

import bs4, datetime, os, requests

with open(os.path.join(os.path.dirname(__file__), 'accounts.txt')) as f:
    accs = f.read().split()

now = datetime.datetime.now()
cutoff = now - datetime.timedelta(days=7)

found = {}

for acc in accs:
    soup = bs4.BeautifulSoup(requests.get(acc).text, 'html.parser')
    for tweet in soup.find_all('li', 'stream-item'):
        photo = tweet.find('div', 'js-adaptive-photo')
        if photo is None:
            continue
        img_url = photo.find('img')['src'] + ':orig'
        name = tweet.find(class_='fullname').text
        perma = tweet.find('a', 'js-permalink')
        permalink = f"https://twitter.com{perma['href']}"
        conv_id = perma['data-conversation-id']
        time = datetime.datetime.fromtimestamp(
            int(perma.find('span')['data-time']))
        if time < cutoff:
            continue
        found[conv_id] = (time, f'''<div>
<strong><a href="{permalink}">{name}</a></strong><br />
{time}<br />
<a href="{img_url}"><img src="{img_url}" /></a><br />
<a href="{img_url}" class="source">{img_url}</a><br />
<a href="{permalink}" class="source">{permalink}</a>
</div>''')

print(f'''<!DOCTYPE html><html><head>
<title>Twitnon report {now}</title>
''''''<style type="text/css">
div { display: inline-block; }
img { width: 200px; max-width: 100%; }
a.source { font-size: 0.4em; }
</style>
</head><body>''')
print(''.join(
    tw[1] for tw in sorted(found.values(), key=lambda x: x[0], reverse=True)))
print('''<br /><br />
<a href="https://github.com/hushbugger/twitnon">Source code</a>
</body></html>''')
