#!/usr/bin/env python3
# Copying and distribution of this file, with or without modification,
# are permitted in any medium without royalty. This file is offered
# as-is, without any warranty.

import argparse, bs4, datetime, requests
from pathlib import Path
from tqdm import tqdm
from time import sleep

parser = argparse.ArgumentParser()
parser.add_argument('outfile')
parser.add_argument('-i', '--infile',
                    default=str(Path(__file__).parent / 'accounts.txt'))
parser.add_argument('-d', '--days', type=int, default=7)
args = parser.parse_args()

with open(args.infile) as f:
    accs = [line.strip().rpartition('/')[2]
            for line in f if line.strip()]
accset = {acc.casefold() for acc in accs}

now = datetime.datetime.now()
cutoff = now - datetime.timedelta(days=args.days)

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
        sleep(30)
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
            permalink = tweet.find('a', 'js-permalink')
            if permalink is None:
                page_bar.write("Couldn't find permalink")
                continue
            time = datetime.datetime.fromtimestamp(
                int(permalink.find('span')['data-time']))
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
        username = tweet.find('div', 'tweet')['data-screen-name']
        follow = username.casefold() in accset
        perma = tweet.find('a', 'js-permalink')
        permalink = f"https://twitter.com{perma['href']}"
        time = datetime.datetime.fromtimestamp(
            int(perma.find('span')['data-time']))
        for i, photo in enumerate(tweet.find_all('div', 'js-adaptive-photo')):
            img_url = photo.find('img')['src']
            identifier = img_url.rpartition('/')[2].partition('.')[0]
            # tweak the time so images appear in order
            # We want reverse order, so they appear in order during showtime
            imgs.add((time + datetime.timedelta(microseconds=i), f'''
<div class="tweet {'follow' if follow else 'nofollow'}"
 id="{identifier}" data-tweeter="{username}" data-url="{img_url}"
 data-time="{time}" onclick="mark('{identifier}');">
<strong><a href="{permalink}">@{username}</a></strong><br />
{time}<br />
{identifier}<br />
[<a href="javascript:filterTweeter('{username}');" title="Hide account">X</a>]
[<a href="{img_url}:orig" title="Full image">IMG</a>]
[<a href="{permalink}" title="Source">SRC</a>]<br />
<a href="{img_url}:orig"><img class="thumb" src="{img_url}:thumb"
 alt="{identifier}" /></a>
<hr />
</div>'''))
            image_bar.update()
acc_bar.close()
image_bar.close()

with open(args.outfile, 'w') as f:
    print(f'''<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"/>
<title>Twitnon report {datetime.datetime.now()}</title>
'''r'''<style>
div.tweet { display: inline-block; width: 160px; font-size: 0.6em; }
div.nofollow { background-color: #ffeeee; }
div.follow { background-color: #eeffee; }
div.marked { background-color: #bbbbff; }
img#viewer { height: 500px; max-width: 1000px; }
</style>
<script>
"use strict";

// Remove all of an account's tweets
function filterTweeter(name) {
    document.querySelectorAll('[data-tweeter="' + name + '"]').forEach(
        function (tweet) {
            tweet.remove();
        }
    )
}

const abbrevs = new Map([
    // General
    ["al", "Alphys"], ["un", "Undyne"], ["ag", "Asgore"], ["to", "Toriel"], ["gr", "Group"],
    // MTT crew
    ["mt", "Mettaton"], ["bp", "Burgerpants"], ["nb", "Napstablook"], ["ob", "Other bots"],
    // Skeletons
    ["sa", "Sans"], ["pa", "Papyrus"], ["ga", "Gaster"],
    // Children
    ["fr", "Frisk"], ["ch", "Chara"], ["as", "Asriel"], ["fl", "Flowey"], ["mk", "Monster kid"], ["hu", "human"],
    // AUs
    ["ss", "Storyshift"], ["sw", "Swap"], ["fe", "Underfell"], ["sf", "Swapfell"], ["ho", "Horrortale"],
    ["ms", "Misc. Skeletons"]
]);

const groups = new Map([
    // The ordering of this decides which groups have priority over others
    // e.g. alphys,mettaton goes to General, frisk,burgerpants goes to MTT
    ["General", ["Alphys", "Undyne", "Asgore", "Toriel", "Group"]],
    ["MTT", ["Mettaton", "Burgerpants", "Napstablook", "Other bots"]],
    ["Skeletons", ["Sans", "Papyrus", "Gaster"]],
    ["Children", ["Frisk", "Chara", "Asriel", "Flowey", "Monster kid", "human"]],
    ["AUs", ["Storyshift", "Swap", "Underfell", "Swapfell", "Horrortale", "Misc. Skeletons"]],
]);

const groupOrder = ["Children", "General", "Other", "MTT", "Skeletons", "AUs"];

const specs = [];

function capitalize(word) {
    return word.charAt(0).toUpperCase() + word.slice(1);
}

function normalize(word) {
    word = word.trim();
    return abbrevs.get(word) || capitalize(word);
}

class Spec {
    constructor(text, url) {
        const specparts = text.split('/');
        const characters = specparts[0];
        this.comments = specparts.slice(1);
        this.characters = [];
        this.url = url;
        for (let character of characters.split(',')) {
            const split = character.split('!');
            if (split.length > 1) {
                this.characters.push(normalize(split[0]) + '!' + normalize(split[1]));
            } else {
                this.characters.push(normalize(split[0]));
            }
        }
        this.characters.sort();
    }

    get characterString() {
        return this.characters.join(' & ');
    }

    toString() {
        let repr = '<a href="' + this.url + '">' + this.url + '</a>';
        for (let comment of this.comments) {
            repr += ' (' + escapeChars(comment) + ')';
        }
        return repr;
    }

    categorize() {
        for (let character of this.characters) {
            if (character.includes('!')) {
                return "AUs";
            }
        }
        for (let [name, members] of groups) {
            for (let character of this.characters) {
                if (members.includes(character)) {
                    return name;
                }
            }
        }
        return "Other";
    }
}

// Sort by number of names first, then alphabetically
function sortCharacters(a, b) {
    let aLength = a.split('&').length;
    let bLength = b.split('&').length;
    if (aLength < bLength) return -1;
    if (aLength > bLength) return 1;
    if (a < b) return -1;
    if (a > b) return 1;
    return 0;
}

function buildListing() {
    const sorted = new Map();
    for (let group of groupOrder) {
        sorted.set(group, new Map());
    }
    for (let spec of specs) {
        let group = sorted.get(spec.categorize());
        if (group.has(spec.characterString)) {
            group.get(spec.characterString).push(spec);
        } else {
            group.set(spec.characterString, [spec]);
        }
    }
    let output = "";
    for (let [groupName, group] of sorted) {
        output += escapeChars("* " + groupName + "\n");
        for (let characters of [...group.keys()].sort(sortCharacters)) {
            output += escapeChars(">" + characters + "\n");
            for (let spec of group.get(characters)) {
                output += spec.toString() + "\n";
            }
            output += "\n";
        }
        output += "\n";
    }
    output += "Sources and full catalog: " + document.location.toString().split('#')[0];
    return output;
}

// Toggle whether a tweet is marked
function mark(ident) {
    let div = document.getElementById(ident);
    if (div.classList.contains('marked')) {
        div.classList.remove('marked');
    } else {
        div.classList.add('marked');
    }
}

// Remove unmarked tweets, return marked tweets with url set
function cleanup() {
    let interesting = [];
    let unused = [];
    let tweets = document.getElementById('tweets');
    for (let tweet of tweets.getElementsByClassName('tweet')) {
        if (!tweet.classList.contains('marked')) {
            unused.push(tweet);
        } else {
            interesting.push(tweet);
        }
    }
    for (let tweet of unused) {
        tweet.remove();
    }
    for (let tweet of interesting) {
        tweet.url = tweet.attributes['data-url'].value;
    }
    return interesting;
}

// Escape special characters
function escapeChars(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Refresh the showtime view
function render() {
    let todo = cleanup();
    let done = getDone();

    function renderTodo() {
        let text = "";
        for (let tweet of todo) {
            let url = tweet.url + ':orig';
            text += '<a href="' + url + '">' + url + '</a>\n';
        }
        return text;
    }

    document.getElementById('todo').innerHTML = renderTodo();
    document.getElementById('done').innerHTML = buildListing();
    showCurrent();
    let current = getCurrent();
    if (current) {
        document.location.hash = current.id;
    }
    document.getElementById('reader').focus();
}

// Return the next tweet in the showtime queue
function getCurrent() {
    let marked = document.getElementsByClassName('marked');
    return marked[marked.length - 1];
}

// Get the done pre
function getDone() {
    return document.getElementById('done').items;
}

// Display the image of the current tweet
function showCurrent() {
    let viewer = document.getElementById('viewer');
    let viewerlink = document.getElementById('viewerlink');
    let current = getCurrent();
    if (current) {
        viewerlink.href = current.url + ':orig';
        viewer.src = current.url;
    } else {
        viewer.remove();
    }
}

function processInput() {
    let current = getCurrent();
    current.remove();
    let field = document.getElementById('reader');
    let text = field.value;
    field.value = '';
    if (text) {
        specs.push(new Spec(text, current.url + ':orig'));
    }
    render();
}

function showtime() {
    let viewerlink = document.getElementById('viewerlink');
    let sorterform = document.getElementById('sorterform');
    let viewer = document.createElement('img');
    let reader = document.createElement('input');
    viewer.id = 'viewer';
    viewerlink.appendChild(viewer);
    reader.type = 'text';
    reader.id = 'reader';
    sorterform.appendChild(reader);
    document.getElementById('showtime').remove();
    render();
}

window.onload = function() {
    document.getElementById('sorterform').addEventListener(
        'submit',
        function (event) {
            event.preventDefault();
            processInput();
        }
    );
}
</script>
</head><body>
<div id="tweets">''', file=f)
    for img in sorted(imgs, reverse=True):
        print(img[1], file=f)
    print("""
</div>
<div id="sorter">
    <button onclick="showtime();" id="showtime">Showtime</button><br />
    <a id="viewerlink"></a>
    <form id="sorterform" onsubmit="return false;"></form>
    <pre id="done">
To sort images, first click on them above to select them. Then press Showtime.
For each image, enter the characters, and maybe a comment, and press enter.
Many characters and AUs have two-letter abbreviations.
If you enter "fl,ss!as/this is a comment", it becomes
>Storyshift!Asriel &amp; Flowey
https://pbs.twimg.com/media/[...].jpg:orig (this is a comment)
The names are capitalized and sorted.
To dismiss an image, press enter without entering anything.
    </pre>
    <pre id="todo"></pre>
</div>
<br /><br />Followed accounts are green, retweets are red.""", file=f)
    acclist = ', '.join(f'<a href="https://twitter.com/{acc}">{acc}</a>'
                        for acc in accs)
    print(f"""<br /> <br />
Followed accounts: {acclist}""", file=f)
    print('''<br /><br />
<a href="https://github.com/hushbugger/twitnon">Source code</a>
</body></html>''', file=f)
