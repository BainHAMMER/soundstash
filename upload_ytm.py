import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv
from ytmusicapi import YTMusic, setup
from ytmusicapi.helpers import initialize_headers, sapisid_from_cookie, get_authorization

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def find_track_video_id(ytm_public, query, index, total):
    """Searches for a track first among official songs, then falls back to music videos."""
    try:
        songs = ytm_public.search(query, filter='songs', limit=1)
        if songs and songs[0].get('videoId'):
            s = songs[0]
            return s['videoId'], f"[{index}/{total}] 🎵 Песня: {query} -> {s.get('title')}"
        videos = ytm_public.search(query, filter='videos', limit=1)
        if videos and videos[0].get('videoId'):
            v = videos[0]
            return v['videoId'], f"[{index}/{total}] 🎬 Видео: {query} -> {v.get('title')}"
    except Exception as e:
        return None, f"[{index}/{total}] ✗ Ошибка поиска: {query} ({e})"
    return None, f"[{index}/{total}] ✗ Не найдено: {query}"


def generate_console_script(video_ids, title, description, privacy, out_js_path: Path):
    """Generates a self-contained browser Console script to create and populate the YTM playlist."""
    js_code = (
        "(async () => {\n"
        f"  const VIDEO_IDS = {json.dumps(video_ids)};\n"
        "  const m = document.cookie.match(/(?:^|;\\s*)(?:__Secure-3PAPISID|SAPISID)=([^;]+)/);\n"
        "  if (!m) { console.error('Не найден куки SAPISID — убедитесь, что вы залогинены на music.youtube.com'); return; }\n"
        "  const sapisid = m[1];\n"
        "  const origin = 'https://music.youtube.com';\n"
        "  const getAuth = async () => {\n"
        "    const ts = Math.floor(Date.now() / 1000);\n"
        "    const data = new TextEncoder().encode(ts + ' ' + sapisid + ' ' + origin);\n"
        "    const buf = await crypto.subtle.digest('SHA-1', data);\n"
        "    const hex = [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');\n"
        "    return 'SAPISIDHASH ' + ts + '_' + hex;\n"
        "  };\n"
        "  const ctx = window.ytcfg.get('INNERTUBE_CONTEXT');\n"
        "  const authUser = window.ytcfg.get('SESSION_INDEX') || '0';\n"
        "  const headers = async () => ({\n"
        "    'Content-Type': 'application/json',\n"
        "    'Authorization': await getAuth(),\n"
        "    'X-Goog-AuthUser': String(authUser),\n"
        "    'X-Origin': origin\n"
        "  });\n\n"
        "  console.log('Создаю плейлист...');\n"
        "  const createRes = await fetch('/youtubei/v1/playlist/create?prettyPrint=false', {\n"
        "    method: 'POST',\n"
        "    credentials: 'include',\n"
        "    headers: await headers(),\n"
        "    body: JSON.stringify({\n"
        "      context: ctx,\n"
        f"      title: {json.dumps(title, ensure_ascii=False)},\n"
        f"      description: {json.dumps(description, ensure_ascii=False)},\n"
        f"      privacyStatus: {json.dumps(privacy)}\n"
        "    })\n"
        "  }).then(r => r.json());\n\n"
        "  const playlistId = createRes.playlistId;\n"
        "  if (!playlistId) { console.error('Ошибка создания плейлиста:', createRes); return; }\n"
        "  const playlistUrl = origin + '/playlist?list=' + playlistId;\n"
        "  console.log('Плейлист создан:', playlistUrl);\n\n"
        "  for (let i = 0; i < VIDEO_IDS.length; i += 50) {\n"
        "    const batch = VIDEO_IDS.slice(i, i + 50);\n"
        "    await fetch('/youtubei/v1/browse/edit_playlist?prettyPrint=false', {\n"
        "      method: 'POST',\n"
        "      credentials: 'include',\n"
        "      headers: await headers(),\n"
        "      body: JSON.stringify({\n"
        "        context: ctx,\n"
        "        playlistId,\n"
        "        actions: batch.map(id => ({ action: 'ACTION_ADD_VIDEO', addedVideoId: id }))\n"
        "      })\n"
        "    });\n"
        "    console.log('Добавлено треков: ' + Math.min(i + 50, VIDEO_IDS.length) + ' / ' + VIDEO_IDS.length);\n"
        "    await new Promise(r => setTimeout(r, 800));\n"
        "  }\n"
        "  console.log('ГОТОВО! Ссылка на плейлист:', playlistUrl);\n"
        "  window.open(playlistUrl, '_blank');\n"
        "})();\n"
    )
    out_js_path.write_text(js_code, encoding='utf-8')


def build_auth_from_cookies_txt(cookies_path: Path, browser_json_path: Path):
    if not cookies_path.exists():
        return False
    pairs = {}
    with open(cookies_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split('\t')
            if len(parts) >= 7 and ('youtube.com' in parts[0] or 'google.com' in parts[0]):
                pairs[parts[5]] = parts[6]

    if '__Secure-3PAPISID' not in pairs:
        return False

    cookie_str = '; '.join(f"{k}={v}" for k, v in pairs.items())
    sapisid = sapisid_from_cookie(cookie_str)
    headers = dict(initialize_headers())
    headers['cookie'] = cookie_str
    headers['x-goog-authuser'] = '0'
    headers['origin'] = 'https://music.youtube.com'
    headers['x-origin'] = 'https://music.youtube.com'
    headers['authorization'] = get_authorization(f"{sapisid} https://music.youtube.com")

    with open(browser_json_path, 'w', encoding='utf-8') as f:
        json.dump(headers, f, indent=2)
    return True


def main():
    default_data_dir = os.getenv('DATA_DIR', '.').strip() or '.'
    parser = argparse.ArgumentParser(description='Search tracks on YouTube Music and create a playlist (via Console JS script or API).')
    parser.add_argument('--data-dir', default=default_data_dir, help='Working directory (default: DATA_DIR from .env or ".")')
    parser.add_argument('--input', '-i', help='Input track list file (default: <data-dir>/tracks_without_youtube.txt)')
    parser.add_argument('--title', '-t', default='Из старых запасов (Spotify + Яндекс + ВК)', help='Playlist title')
    parser.add_argument('--description', '-d', default='Дельта треков (все минус лайки YouTube)', help='Playlist description')
    parser.add_argument('--privacy', default='PRIVATE', choices=['PRIVATE', 'PUBLIC', 'UNLISTED'], help='Playlist privacy status')
    parser.add_argument('--workers', '-w', type=int, default=8, help='Parallel search workers (default: 8)')
    parser.add_argument('--api', action='store_true', help='Use direct ytmusicapi authentication (browser.json / cookies.txt) instead of generating Console JS')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    input_file = Path(args.input) if args.input else data_dir / 'tracks_without_youtube.txt'
    if not input_file.exists() and (data_dir / 'tracks.txt').exists():
        input_file = data_dir / 'tracks.txt'

    if not input_file.exists():
        print(f"✗ Файл {input_file} не найден! Сначала запустите: python merge.py")
        return

    state_file = data_dir / 'ytm_upload_state.json'
    not_found_file = data_dir / 'ytm_not_found.txt'
    out_js_path = data_dir / 'create_playlist_console.js'

    with open(input_file, 'r', encoding='utf-8-sig') as f:
        tracks = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    print(f"=== Подготовка плейлиста YouTube Music ({len(tracks)} треков из {input_file.name}) ===\n")
    ytm_search = YTMusic()

    state = {'playlist_id': None, 'found': {}, 'added_ids': []}
    if state_file.exists():
        try:
            state.update(json.loads(state_file.read_text(encoding='utf-8')))
        except Exception:
            pass

    to_search = [(idx, q) for idx, q in enumerate(tracks, 1) if q not in state['found']]
    not_found = []

    if to_search:
        print(f"🔍 Поиск {len(to_search)} треков в каталоге YouTube Music (в {args.workers} потоков)...\n")
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(find_track_video_id, ytm_search, q, idx, len(tracks)): q
                for idx, q in to_search
            }
            for fut in as_completed(futures):
                q = futures[fut]
                vid, msg = fut.result()
                print(msg)
                if vid:
                    state['found'][q] = vid
                else:
                    not_found.append(q)

        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    if not_found:
        with open(not_found_file, 'w', encoding='utf-8') as f:
            for q in not_found:
                f.write(q + '\n')

    # Collect unique videoIds preserving input order
    seen_ids = set()
    ordered_video_ids = []
    for q in tracks:
        vid = state['found'].get(q)
        if vid and vid not in seen_ids:
            seen_ids.add(vid)
            ordered_video_ids.append(vid)

    generate_console_script(ordered_video_ids, args.title, args.description, args.privacy, out_js_path)
    print(f"\n✓ Найдено уникальных треков: {len(ordered_video_ids)} (из {len(tracks)})")
    print(f"✓ Сгенерирован готовый скрипт для консоли браузера: {out_js_path}")

    if not args.api:
        print("\nКак создать плейлист за 10 секунд без выгрузки куков:")
        print(f"  1. Откройте {out_js_path} и скопируйте весь его текст (Ctrl+A, Ctrl+C)")
        print("  2. На вкладке https://music.youtube.com откройте F12 -> Console, вставьте скрипт и нажмите Enter.")
        return

    browser_json = data_dir / 'browser.json'
    if not browser_json.exists():
        if not build_auth_from_cookies_txt(data_dir / 'cookies.txt', browser_json):
            setup(filepath=str(browser_json))

    ytm = YTMusic(str(browser_json))
    if not state['playlist_id']:
        playlist_id = ytm.create_playlist(args.title, args.description, privacy_status=args.privacy)
        state['playlist_id'] = playlist_id
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

    already_added = set(state.get('added_ids', []))
    to_add = [vid for vid in ordered_video_ids if vid not in already_added]
    for i in range(0, len(to_add), 50):
        batch = to_add[i:i + 50]
        ytm.add_playlist_items(state['playlist_id'], batch, duplicates=False)
        state.setdefault('added_ids', []).extend(batch)
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  ✓ Добавлено {min(i + 50, len(to_add))}/{len(to_add)}")
        time.sleep(1)

    print(f"\n🔗 Плейлист готов: https://music.youtube.com/playlist?list={state['playlist_id']}")


if __name__ == '__main__':
    main()
