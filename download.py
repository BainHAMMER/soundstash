import argparse
import glob
import json
import os
import re
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv
from yt_dlp import YoutubeDL

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def find_ffmpeg():
    path = shutil.which('ffmpeg')
    if path:
        return os.path.dirname(path)
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    if local_appdata:
        winget_links = os.path.join(local_appdata, 'Microsoft', 'WinGet', 'Links')
        if os.path.exists(os.path.join(winget_links, 'ffmpeg.exe')):
            return winget_links
        pattern = os.path.join(local_appdata, 'Microsoft', 'WinGet', 'Packages', 'Gyan.FFmpeg*', '**', 'bin', 'ffmpeg.exe')
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return os.path.dirname(matches[0])
    return None


FFMPEG_LOCATION = find_ffmpeg()


def sanitize_filename(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def load_tracks_to_download(tracks_path: Path, json_path: Path):
    if not tracks_path.exists():
        print(f"✗ Файл {tracks_path} не найден! Сначала запустите: python merge.py")
        return []

    albums_map = {}
    if json_path.exists():
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                for item in json.load(f):
                    key = f"{item.get('artist', '')} - {item.get('name', '')}".strip(' -')
                    if item.get('album'):
                        albums_map[key] = item['album']
        except Exception:
            pass

    tracks = []
    with open(tracks_path, 'r', encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ' - ' in line:
                artist, name = line.split(' - ', 1)
            else:
                artist, name = '', line
            tracks.append({
                'artist': artist.strip(),
                'name': name.strip(),
                'album': albums_map.get(line, ''),
            })
    return tracks


def format_error_reason(err):
    raw = re.sub(r'\x1b\[[0-9;]*m', '', str(err)).strip()
    raw = re.sub(r'\s+', ' ', raw)
    low = raw.lower()
    if 'sign in to confirm your age' in low or 'inappropriate for some users' in low:
        vid = ''
        m = re.search(r'\[youtube\]\s*([a-zA-Z0-9_-]{11}):', raw)
        if m:
            vid = f" (https://youtu.be/{m.group(1)})"
        return f"Ограничение 18+ Age-restricted — нужны куки в cookies.txt{vid}"
    if 'http error 403' in low or '403: forbidden' in low:
        return f"HTTP 403 Forbidden (блокировка видеопотока YouTube) | {raw}"
    if 'video unavailable' in low or 'not available' in low:
        return f"Видео недоступно / заблокировано в регионе | {raw}"
    if 'private video' in low:
        return f"Приватное видео | {raw}"
    return raw


def download_one(track, index, total, cfg):
    artist = track['artist']
    name = track['name']
    display = f"{artist} - {name}" if artist else name

    download_folder = cfg['download_folder']
    audio_format = cfg['audio_format']
    audio_quality = cfg['audio_quality']
    embed_thumbnail = cfg['embed_thumbnail']
    add_metadata = cfg['add_metadata']
    cookie_file = cfg['cookie_file']

    download_folder.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(display) or f"track_{index}"
    out_file = download_folder / f"{safe_name}.{audio_format}"
    if out_file.exists():
        return True, None, None

    postprocessors = [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': audio_format,
        'preferredquality': '320' if audio_format == 'mp3' and audio_quality in ('0', 'best') else audio_quality,
    }]
    if add_metadata:
        postprocessors.append({'key': 'FFmpegMetadata', 'add_metadata': True})
    if embed_thumbnail and audio_format in ('mp3', 'm4a', 'opus', 'flac'):
        postprocessors.append({'key': 'EmbedThumbnail'})

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(download_folder / f"{safe_name}.%(ext)s"),
        'postprocessors': postprocessors,
        'writethumbnail': embed_thumbnail,
        'convert_thumbnails': 'jpg' if embed_thumbnail else None,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'retries': 10,
        'fragment_retries': 10,
        'retry_sleep_functions': {'http': lambda n: min(2 * n, 10)},
    }
    if FFMPEG_LOCATION:
        ydl_opts['ffmpeg_location'] = FFMPEG_LOCATION
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts['cookiefile'] = str(cookie_file)

    if artist and name:
        pp_args = ['-metadata', f'title={name}', '-metadata', f'artist={artist}']
        if track.get('album'):
            pp_args.extend(['-metadata', f"album={track['album']}"])
        ydl_opts['postprocessor_args'] = pp_args

    def cleanup_part_files():
        for p in glob.glob(str(download_folder / f"{glob.escape(safe_name)}.*")):
            if not p.endswith(f".{audio_format}"):
                try:
                    os.remove(p)
                except OSError:
                    pass

    def build_fallback_queries():
        queries = []
        first_artist = artist.split(',')[0].strip() if artist else ''
        clean_q = re.sub(r'[-–—()]', ' ', f"{first_artist} {name}")
        clean_q = re.sub(r'\s+', ' ', clean_q).strip()
        if clean_q and clean_q.lower() != display.lower():
            queries.append(clean_q)
        short_name = re.sub(r'\s*\(.*?\)', '', name).strip()
        if first_artist and short_name:
            q2 = re.sub(r'\s+', ' ', f"{first_artist} {short_name}").strip()
            if q2 not in queries:
                queries.append(q2)
        return queries

    try:
        cleanup_part_files()
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{display}", download=True)
            entries = (info or {}).get('entries') if isinstance(info, dict) else None
            if entries is not None and len(entries) == 0:
                for alt_q in build_fallback_queries():
                    info2 = ydl.extract_info(f"ytsearch1:{alt_q}", download=True)
                    entries2 = (info2 or {}).get('entries') if isinstance(info2, dict) else None
                    if entries2 and out_file.exists():
                        break
                if not out_file.exists():
                    raise RuntimeError("Не найдено в поиске YouTube (0 результатов по запросу)")
        if out_file.exists():
            return True, f"[{index}/{total}] ✓ {display}", None
        raise RuntimeError("Не найдено в поиске YouTube (аудиофайл не создан)")
    except Exception as first_err:
        reason = format_error_reason(first_err)
        if '403' in str(first_err) or 'аудиофайл не создан' in str(first_err):
            try:
                cleanup_part_files()
                fallback_opts = dict(ydl_opts)
                fallback_opts['extractor_args'] = {'youtube': {'player_client': ['android_vr', 'mweb', 'tv']}}
                with YoutubeDL(fallback_opts) as ydl:
                    ydl.download([f"ytsearch1:{display}"])
                if out_file.exists():
                    return True, f"[{index}/{total}] ✓ {display}", None
            except Exception as second_err:
                reason = format_error_reason(second_err)
        cleanup_part_files()
        return False, f"[{index}/{total}] ✗ {display} -> {reason}", reason


def main():
    default_data_dir = os.getenv('DATA_DIR', '.').strip() or '.'
    default_format = os.getenv('AUDIO_FORMAT', 'mp3').strip().lower()
    default_quality = os.getenv('AUDIO_QUALITY', '0').strip()
    default_folder = os.getenv('DOWNLOAD_FOLDER', 'downloads').strip()
    default_workers = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '4'))
    embed_thumb = os.getenv('EMBED_THUMBNAIL', 'true').strip().lower() in ('1', 'true', 'yes', 'y')
    add_meta = os.getenv('ADD_METADATA', 'true').strip().lower() in ('1', 'true', 'yes', 'y')

    parser = argparse.ArgumentParser(description='Download tracks from a text list in maximum audio quality via yt-dlp + FFmpeg.')
    parser.add_argument('--data-dir', default=default_data_dir, help='Working directory for track lists (default: DATA_DIR from .env or ".")')
    parser.add_argument('--input', '-i', help='Input track list file (default: <data-dir>/tracks.txt)')
    parser.add_argument('--out-dir', '-o', help='Output folder for downloaded audio (default: <data-dir>/downloads)')
    parser.add_argument('--format', '-f', default=default_format, choices=['mp3', 'opus', 'm4a', 'flac'], help='Audio format (default: mp3)')
    parser.add_argument('--workers', '-w', type=int, default=default_workers, help='Parallel downloads count (default: 4)')
    parser.add_argument('--cookies', help='Path to Netscape cookies.txt file for age-restricted tracks')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    tracks_path = Path(args.input) if args.input else data_dir / 'tracks.txt'
    json_path = data_dir / 'tracks.json'
    download_folder = Path(args.out_dir) if args.out_dir else data_dir / default_folder
    failed_path = data_dir / 'failed_tracks.txt'
    cookie_file = args.cookies or (str(data_dir / 'cookies.txt') if (data_dir / 'cookies.txt').exists() else ('cookies.txt' if os.path.exists('cookies.txt') else None))

    tracks = load_tracks_to_download(tracks_path, json_path)
    if not tracks:
        return

    cfg = {
        'download_folder': download_folder,
        'audio_format': args.format,
        'audio_quality': default_quality,
        'embed_thumbnail': embed_thumb,
        'add_metadata': add_meta,
        'cookie_file': cookie_file,
    }

    print("=== Скачивание треков в максимальном качестве (yt-dlp + FFmpeg) ===")
    print(f"Треков в очереди: {len(tracks)} | Формат: {args.format.upper()} | Потоков: {args.workers}")
    print(f"Папка: {download_folder.resolve()}\n")

    ok = 0
    skipped = 0
    failed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(download_one, t, idx, len(tracks), cfg): (idx, t)
            for idx, t in enumerate(tracks, 1)
        }
        for fut in as_completed(futures):
            idx, track = futures[fut]
            success, msg, reason = fut.result()
            if msg:
                print(msg)
            if success:
                ok += 1
                if msg is None:
                    skipped += 1
            else:
                failed.append((idx, track, reason))

    failed.sort(key=lambda x: x[0])
    if failed:
        with open(failed_path, 'w', encoding='utf-8') as f:
            for _, t, reason in failed:
                line = f"{t['artist']} - {t['name']}" if t['artist'] else t['name']
                f.write(f"{line} | Причина: {reason}\n")
    elif failed_path.exists():
        failed_path.unlink()

    print(f"\n=== Готово! Всего в наличии: {ok}/{len(tracks)} (пропущено уже скачанных: {skipped}) | Ошибок: {len(failed)} ===")
    if failed:
        print(f"Неудачные треки с причинами записаны в {failed_path}")


if __name__ == '__main__':
    main()
