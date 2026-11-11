import argparse
import csv
import glob
import json
import os
import re
import unicodedata
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def strip_accents(s: str) -> str:
    s = (
        s.replace('æ', 'ae').replace('Æ', 'Ae')
        .replace('ø', 'o').replace('Ø', 'O')
        .replace('ß', 'ss').replace('ё', 'е').replace('Ё', 'Е')
    )
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )


def clean_artist(artist: str) -> str:
    if not artist:
        return ''
    artist = artist.replace('\xa0', ' ')
    artist = re.sub(r'[░♬★]+', '', artist)
    artist = re.sub(r'^\d+\.\s*', '', artist)
    # Normalize artist separators (';', 'feat.', 'ft.', Russian ' и ') into ', '
    artist = re.sub(r'\s*;\s*', ', ', artist)
    artist = re.sub(r'\s+и\s+', ', ', artist)
    artist = re.sub(r'\s+(?:feat\.?|ft\.?)\s+', ', ', artist, flags=re.I)

    # Deduplicate repeated artist names while preserving order
    parts = [p.strip() for p in artist.split(',') if p.strip()]
    unique_parts = []
    seen_norm = set()
    for p in parts:
        norm = strip_accents(p).lower().strip()
        if norm and norm not in seen_norm:
            seen_norm.add(norm)
            unique_parts.append(p)
    return ', '.join(unique_parts)


def clean_yandex_nbsp_suffix(title: str) -> str:
    """Handles Yandex Music subtitle suffixes separated by non-breaking space (\\xa0)."""
    if '\xa0' not in title:
        return title
    main_part, suffix = title.split('\xa0', 1)
    main_part = main_part.strip()
    suffix = suffix.strip()

    # Common non-informative suffixes to drop completely
    junk_patterns = (
        r'^original\s+(?:mix|version)$',
        r'^(?:radio|single|album)\s+(?:edit|version)$',
        r'^remaster(?:ed)?(?:\s+\d{4})?$',
        r'^bonus\s+track$',
        r'^with\s*out\s+interlude$',
        r'^(?:feat\.?|ft\.?|duet\s+w/|prod\.?\s+by).*$',
        r'^из\s+(?:фильма|трейлера|сериала|игры|мультфильма).*$',
        r'^from\s+["«].*$',
        r'^ost\b.*$',
    )
    for pat in junk_patterns:
        if re.match(pat, suffix, flags=re.I):
            return main_part

    # Keep meaningful version tags (Remix, Mix, Instrumental, Version, Live, Acoustic, Cover) in parentheses
    suffix = re.sub(r';\s*(?:feat\.?|ft\.?).*$', '', suffix, flags=re.I).strip()
    if re.search(r'\b(?:remix|mix|instrumental|version|live|acoustic|cover|vip|edit)\b', suffix, flags=re.I):
        return f"{main_part} ({suffix})"
    return main_part


def clean_title(title: str) -> str:
    if not title:
        return ''
    title = clean_yandex_nbsp_suffix(title)
    title = title.replace('\xa0', ' ')
    title = re.sub(r'[░♬★]+', '', title)
    title = re.sub(r'#\S+', '', title)

    # Remove technical/video/quality tags in brackets and parentheses
    title = re.sub(
        r'\s*\[\s*(?:official|lyric|audio|music\s+video|video|visualizer|hd|hq|4k|deluxe|320\s*kbps).*?\]',
        '',
        title,
        flags=re.I,
    )
    title = re.sub(
        r'\s*\(\s*(?:official|lyric|audio|music\s+video|studio\s+video|video|visualizer|hd|hq|4k).*?\)',
        '',
        title,
        flags=re.I,
    )
    title = re.sub(r'\s*\(\s*(?:feat\.?|ft\.?)\s+[^)]+\)', '', title, flags=re.I)
    title = re.sub(r'\s*\[\s*(?:feat\.?|ft\.?)\s+[^\]]+\]', '', title, flags=re.I)
    title = re.sub(r'\s+(?:feat\.?|ft\.?)\s+.*$', '', title, flags=re.I)
    title = re.sub(r'\s*\(\s*(?:\d{4}\s+)?remaster(?:ed)?(?:\s+\d{4})?\s*\)', '', title, flags=re.I)
    title = re.sub(
        r'\s*\(\s*(?:bonus(?:\s+track)?|original(?:\s+mix)?|radio\s+edit|single\s+edit|deluxe.*?|special\s+edition.*?|320\s*kbps)\s*\)',
        '',
        title,
        flags=re.I,
    )
    title = re.sub(r'\s*\(\s*album\s+version.*?\)', '', title, flags=re.I)
    title = re.sub(
        r'\s*-\s*(?:\d{4}\s+)?(?:remaster(?:ed)?|radio\s+edit|new\s+version|bonus\s+track|single\s+version|album\s+version).*$',
        '',
        title,
        flags=re.I,
    )
    title = re.sub(r'[\(\[\s-]+$', '', title)

    return re.sub(r'\s+', ' ', title).strip()


def is_junk_track(artist: str, title: str) -> bool:
    a_low = artist.lower().strip()
    t_low = title.lower().strip()
    if not t_low:
        return True
    if t_low in ('без названия', 'untitled', 'unknown', 'unknown track', 'ost'):
        return True
    if re.match(r'^(?:дорожка|track)\s*\d+$', t_low):
        return True
    if a_low in ('неизвестен', 'неизвестный исполнитель', 'unknown artist') and t_low in ('без названия', 'untitled'):
        return True
    return False


def parse_text_line(line: str, source: str):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if line.startswith('[') and line.endswith(']'):
        line = line[1:-1].strip()

    artist, title = '', line
    for sep in (' - ', ' — ', ' – ', '\t'):
        if sep in line:
            artist, title = line.split(sep, 1)
            break

    artist = clean_artist(artist)
    title = clean_title(title)
    if is_junk_track(artist, title):
        return None

    return {
        'artist': artist,
        'name': title,
        'album': '',
        'source': source,
    }


def load_spotify(data_dir: Path, explicit_path: str = None):
    tracks = []
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            return []
        if p.suffix.lower() == '.csv':
            csv_files = [p]
            txt_files = []
        else:
            csv_files = []
            txt_files = [p]
    else:
        patterns = [str(data_dir / '*spotify*.csv'), str(data_dir / '*Spotify*.csv')]
        csv_files = [Path(p) for p in sorted(set(glob.glob(patterns[0]) + glob.glob(patterns[1])))]
        txt_path = data_dir / 'spotify.txt'
        txt_files = [txt_path] if txt_path.exists() else []

    for csv_file in csv_files:
        count = 0
        with open(csv_file, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                norm_row = {k.strip().lower(): (v or '').strip() for k, v in row.items() if k}
                raw_name = norm_row.get('track name') or norm_row.get('title') or norm_row.get('name') or ''
                raw_artist = norm_row.get('artist name(s)') or norm_row.get('artist name') or norm_row.get('artist') or ''
                album = norm_row.get('album name') or norm_row.get('album') or ''
                artist = clean_artist(raw_artist)
                name = clean_title(raw_name)
                if not is_junk_track(artist, name):
                    tracks.append({
                        'artist': artist,
                        'name': name,
                        'album': album.strip(),
                        'source': 'spotify',
                    })
                    count += 1
        print(f"✓ Spotify ({csv_file.name}): {count} треков")

    for txt_file in txt_files:
        tracks.extend(load_txt_source(txt_file, 'spotify'))

    return tracks


def load_txt_source(filepath: Path, source_label: str):
    if not filepath.exists():
        return []
    tracks = []
    with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
        for line in f:
            item = parse_text_line(line, source_label)
            if item:
                tracks.append(item)
    print(f"✓ {source_label.upper()} ({filepath.name}): {len(tracks)} треков")
    return tracks


def make_dedup_key(artist: str, name: str) -> str:
    """Builds a normalized deduplication key from primary artist and cleaned track title."""
    first_artist = artist.split(',')[0].strip().lower() if artist else ''
    first_artist = strip_accents(first_artist)
    first_artist = re.sub(r'^the\s+', '', first_artist)
    first_artist = re.sub(r'[^\w]', '', first_artist)

    norm_name = strip_accents(name.lower())
    norm_name = re.sub(r'[^\w]', '', norm_name)
    return f"{first_artist}|{norm_name}" if first_artist else norm_name


def merge_all(args):
    data_dir = Path(args.data_dir)
    print("=== Сборка и очистка списков треков ===\n")

    spotify = load_spotify(data_dir, args.spotify)
    yandex = load_txt_source(Path(args.yandex) if args.yandex else data_dir / 'yandex.txt', 'yandex')
    youtube = load_txt_source(Path(args.youtube) if args.youtube else data_dir / 'youtube.txt', 'youtube')
    vk = load_txt_source(Path(args.vk) if args.vk else data_dir / 'vk.txt', 'vk')

    all_tracks = spotify + yandex + youtube + vk
    if not all_tracks:
        print(f"✗ Файлы со списками не найдены в {data_dir.resolve()}!")
        return

    merged = {}
    for t in all_tracks:
        key = make_dedup_key(t['artist'], t['name'])
        if not key:
            continue
        if key not in merged:
            merged[key] = {
                'artist': t['artist'],
                'name': t['name'],
                'album': t.get('album', ''),
                'sources': [t['source']],
            }
        else:
            existing = merged[key]
            if t['source'] not in existing['sources']:
                existing['sources'].append(t['source'])
            if not existing.get('album') and t.get('album'):
                existing['album'] = t['album']
            if not existing.get('artist') and t.get('artist'):
                existing['artist'] = t['artist']

    result = list(merged.values())
    data_dir.mkdir(parents=True, exist_ok=True)

    tracks_txt = Path(args.output) if args.output else data_dir / 'tracks.txt'
    tracks_json = data_dir / 'tracks.json'
    delta_txt = data_dir / 'tracks_without_youtube.txt'

    with open(tracks_txt, 'w', encoding='utf-8') as f:
        for item in result:
            line = f"{item['artist']} - {item['name']}" if item['artist'] else item['name']
            f.write(line + '\n')

    with open(tracks_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    not_on_yt = [item for item in result if 'youtube' not in item['sources']]
    with open(delta_txt, 'w', encoding='utf-8') as f:
        for item in not_on_yt:
            line = f"{item['artist']} - {item['name']}" if item['artist'] else item['name']
            f.write(line + '\n')

    print(f"\n📊 Всего исходных записей: {len(all_tracks)}")
    print(f"✨ Уникальных очищенных треков: {len(result)} (удалено дублей: {len(all_tracks) - len(result)})")
    print(f"➖ Дельта (все треки минус YouTube): {len(not_on_yt)} -> {delta_txt}")
    print(f"📁 Сохранено в: {tracks_txt}, {tracks_json} и {delta_txt}")


def build_delta_from_existing_tracks(args):
    """Builds tracks_without_youtube.txt from existing tracks.txt minus youtube.txt without overwriting tracks.txt."""
    data_dir = Path(args.data_dir)
    tracks_txt = Path(args.output) if args.output else data_dir / 'tracks.txt'
    yt_path = Path(args.youtube) if args.youtube else data_dir / 'youtube.txt'
    delta_txt = data_dir / 'tracks_without_youtube.txt'

    if not tracks_txt.exists():
        print(f"✗ Файл {tracks_txt} не найден!")
        return

    youtube = load_txt_source(yt_path, 'youtube')
    yt_keys = {make_dedup_key(t['artist'], t['name']) for t in youtube}

    delta_lines = []
    total_current = 0
    with open(tracks_txt, 'r', encoding='utf-8-sig') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            total_current += 1
            parsed = parse_text_line(line, 'all')
            if not parsed:
                continue
            key = make_dedup_key(parsed['artist'], parsed['name'])
            if key not in yt_keys:
                delta_lines.append(line)

    with open(delta_txt, 'w', encoding='utf-8') as f:
        for line in delta_lines:
            f.write(line + '\n')

    print(f"📊 Всего в текущем {tracks_txt.name}: {total_current}")
    print(f"➖ Дельта (все треки минус YouTube): {len(delta_lines)} треков -> сохранено в {delta_txt}")


def main():
    default_data_dir = os.getenv('DATA_DIR', '.').strip() or '.'
    parser = argparse.ArgumentParser(
        description='Merge, clean, and deduplicate track lists from Spotify, Yandex Music, VK, and YouTube Music.'
    )
    parser.add_argument('--data-dir', default=default_data_dir, help='Working directory for track lists (default: DATA_DIR from .env or ".")')
    parser.add_argument('--spotify', help='Path to Spotify CSV file (Exportify format)')
    parser.add_argument('--yandex', help='Path to Yandex Music text file (default: <data-dir>/yandex.txt)')
    parser.add_argument('--youtube', help='Path to YouTube Music text file (default: <data-dir>/youtube.txt)')
    parser.add_argument('--vk', help='Path to VK Music text file (default: <data-dir>/vk.txt)')
    parser.add_argument('--output', '-o', help='Path to merged output file (default: <data-dir>/tracks.txt)')
    parser.add_argument('--delta', action='store_true', help='Only recalculate tracks_without_youtube.txt from existing tracks.txt without overwriting tracks.txt')
    args = parser.parse_args()

    if args.delta:
        build_delta_from_existing_tracks(args)
    else:
        merge_all(args)


if __name__ == '__main__':
    main()
