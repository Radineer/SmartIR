import asyncio, json, httpx
from app.publish.note_client import NoteClient

async def main():
    nc = NoteClient()
    await nc.login()
    
    # Now read session and fetch articles
    session_path = '/Users/apple/.smartir/note_session.json'
    with open(session_path) as f:
        cookies_raw = json.load(f)
    if isinstance(cookies_raw, list):
        cookies = {c['name']: str(c['value']) for c in cookies_raw if 'name' in c and c.get('value') is not None}
    else:
        cookies = {k: str(v) for k, v in cookies_raw.items() if v is not None}
    
    client = httpx.Client(cookies=cookies, headers={'User-Agent': 'Mozilla/5.0'})
    r = client.get('https://note.com/api/v2/creators/mine')
    data = r.json().get('data', {})
    urlname = data.get('urlname', 'N/A')
    nickname = data.get('nickname', 'N/A')
    note_count = data.get('noteCount', 0)
    follower = data.get('followerCount', 0)
    print(f'urlname: {urlname}')
    print(f'nickname: {nickname}')
    print(f'note_count: {note_count}')
    print(f'followers: {follower}')
    print()
    
    all_notes = []
    for page in range(1, 20):
        r2 = client.get(f'https://note.com/api/v2/creators/{urlname}/contents?kind=note&page={page}&per=20')
        notes = r2.json().get('data', {}).get('contents', [])
        if not notes:
            break
        all_notes.extend(notes)
    
    print(f'Total articles: {len(all_notes)}')
    print()
    for n in all_notes:
        name = n.get('name', '?')
        price = n.get('price', 0)
        likes = n.get('likeCount', 0)
        key = n.get('key', '')
        created = (n.get('publishAt') or '')[:10]
        body_len = len(n.get('body', '') or '')
        tag = f'¥{price}' if price > 0 else '無料'
        print(f'{created} | {tag:>6} | {likes:>3}likes | {name}')

asyncio.run(main())
