#!/usr/bin/env python3
# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty. This file is offered
# as-is, without any warranty.

import bs4, datetime, os, requests, sys
from tqdm import tqdm
from time import sleep

with open(os.path.join(os.path.dirname(__file__), 'accounts.txt')) as f:
    accs = [line.strip().rpartition('/')[2]
            for line in f if line.strip()]

now = datetime.datetime.now()
cutoff = now - datetime.timedelta(days=7)
outfile = sys.argv[1]

imgs = set()


def tweets(account, cutoff):
    url = f"https://twitter.com/i/profiles/show/{acc}/timeline/tweets"
    params = {}
    might_be_pinned = True
    page_bar = tqdm(desc=f"Pages read ({account})")
    while True:
        page_bar.update()
        resp = requests.get(url, params=params, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:60.0) '
            'Gecko/20100101 Firefox/60.0'})
        sleep(1)
        try:
            data = resp.json()
        except:
            page_bar.write(f"{account} got {resp.status_code}")
            page_bar.close()
            return
        min_position = data['min_position']
        params['max_position'] = min_position
        html = data['items_html']
        if not html.strip():
            page_bar.close()
            return
        soup = bs4.BeautifulSoup(html, 'html.parser')
        found_something = False
        for tweet in soup.find_all('li', 'stream-item'):
            time = datetime.datetime.fromtimestamp(
                int(tweet.find('a', 'js-permalink').find('span')['data-time']))
            if time < cutoff:
                # We should skip this one
                if ('data-retweet-id' not in tweet.find('div').attrs and
                        not might_be_pinned):
                    # It's not a retweet, so stop looking altogether
                    page_bar.close()
                    return
                continue
            found_something = True
            might_be_pinned = False
            yield tweet
        if not found_something:
            # All we found on this page was old retweets, better abort
            page_bar.close()
            return


image_bar = tqdm(desc="Images found")
acc_bar = tqdm(accs, desc="Accounts")
for acc in acc_bar:
    acc_bar.write(acc)
    for tweet in tweets(acc, cutoff):
        name = tweet.find(class_='fullname').text
        perma = tweet.find('a', 'js-permalink')
        permalink = f"https://twitter.com{perma['href']}"
        time = datetime.datetime.fromtimestamp(
            int(perma.find('span')['data-time']))
        for i, photo in enumerate(tweet.find_all('div', 'js-adaptive-photo')):
            img_url = photo.find('img')['src']
            # tweak the time so images appear in order
            imgs.add((time - datetime.timedelta(microseconds=i),
                      f'''<div>
<strong><a href="{permalink}">{name}</a></strong><br />
{time}<br />
{img_url.rpartition('/')[2].partition('.')[0]}<br />
[<a href="{img_url}:orig">IMG</a>] [<a href="{permalink}">SRC</a>]<br />
<a href="{img_url}:orig"><img src="{img_url}:thumb" /></a>
<hr />
</div>'''))
            image_bar.update()
acc_bar.close()
image_bar.close()

with open(outfile, 'w') as f:
    print(f'''<!DOCTYPE html><html><head>
<meta charset="UTF-8"/>
<title>Twitnon report {now}</title>
''''''<style type="text/css">
div { display: inline-block; width: 160px; font-size: 0.6em; }
</style>
</head><body>''', file=f)
    for img in sorted(imgs, key=lambda x: x[0], reverse=True):
        print(img[1], file=f)
    print('''<br /><br />
<a href="https://github.com/hushbugger/twitnon">Source code</a>
</body></html>''', file=f)
