# SoundStash — Cross-Platform Music Library Merger, Downloader & YouTube Music Importer

**[🇷🇺 Русская версия (README.ru.md)](README.ru.md)**

A lightweight, fast Python toolkit to:
1. **Export & Merge** your liked tracks from **Spotify**, **Yandex Music**, **VK Music**, and **YouTube Music** into a single clean, deduplicated list (`tracks.txt` + `tracks.json`).
2. **Calculate Deltas** (e.g., all tracks from Spotify + Yandex + VK that are **not** yet in your YouTube Music likes → `tracks_without_youtube.txt`).
3. **Download** your entire library in maximum audio quality (**MP3 320 kbps**, **Opus**, **M4A**, or **FLAC**) with embedded cover art thumbnails and ID3 metadata (`Artist`, `Title`, `Album`) using `yt-dlp` + `FFmpeg`.
4. **Import to YouTube Music** by automatically resolving catalog `videoId`s in multi-threaded mode and generating a self-contained browser Console script (`create_playlist_console.js`) that creates and populates your playlist right inside your active `music.youtube.com` tab — **no OAuth setup, no cookie extraction, and no locked browser database errors**.

---

## 🚀 Quick Start

### 1. Requirements
- **Python 3.10+**
- **FFmpeg** installed on your system:
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

```bash
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

---

## 📥 Step 1: Export Your Track Lists

Ready-to-paste browser Console scripts that **automatically scroll to the bottom and download `.txt` files** are located in the [`extractors/`](extractors/) folder. Place the resulting files in your working directory (root `.` or `DATA_DIR` set in `.env`):

> **Tip for Chrome / Edge DevTools:** If the Console shows `Warning: Don’t paste code into the DevTools Console...`, type `allow pasting` manually on your keyboard, press **Enter**, and then paste the script.

### 1. Spotify (`spotify.txt` or `*spotify*.csv`) — [`extractors/spotify.js`](extractors/spotify.js)
- **Option A (Console JS):** Open **Liked Songs** (`open.spotify.com/collection/tracks`) or any playlist in the Spotify Web Player, open `F12` → **Console**, and paste [`extractors/spotify.js`](extractors/spotify.js) — it auto-scrolls the virtualized list and downloads `spotify.txt`:
```javascript
(async () => {
  const seen = new Set();
  const getScrollParent = (node) => {
    while (node && node !== document.body) {
      const style = getComputedStyle(node);
      if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight) return node;
      node = node.parentElement;
    }
    return document.querySelector('[data-overlayscrollbars-viewport]')
      || document.querySelector('.main-view-container__scroll-node')
      || document.scrollingElement
      || document.documentElement;
  };
  let scroller = null;
  const collect = () => {
    document.querySelectorAll('[data-testid="tracklist-row"], [role="row"]').forEach(row => {
      if (!scroller && row.getAttribute('data-testid') === 'tracklist-row') scroller = getScrollParent(row);
      const titleEl = row.querySelector('[data-testid="internal-track-link"] div, [data-testid="internal-track-link"], [aria-colindex="2"] div[dir="auto"]');
      const title = titleEl?.textContent?.trim();
      const artists = [...row.querySelectorAll('a[href*="/artist/"]')].map(a => a.textContent.trim()).filter(Boolean);
      if (artists.length && title) seen.add(`${artists.join(', ')} - ${title}`);
    });
  };
  collect();
  if (!scroller) scroller = getScrollParent(document.querySelector('[data-testid="tracklist-row"]'));
  scroller.scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 500));
  let stuck = 0, lastTop = -1;
  while (stuck < 6) {
    collect();
    console.log(`Collected from Spotify: ${seen.size}...`);
    scroller.scrollBy(0, 500);
    await new Promise(r => setTimeout(r, 450));
    const curTop = scroller.scrollTop;
    if (Math.abs(curTop - lastTop) < 5) stuck++;
    else stuck = 0;
    lastTop = curTop;
  }
  collect();
  const list = [...seen];
  if (list.length > 0) {
    const blob = new Blob([list.join('\n')], { type: 'text/plain;charset=utf-8' });
    Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'spotify.txt' }).click();
  }
  console.log(`Done! Exported to spotify.txt: ${list.length}`);
})();
```
- **Option B (Exportify CSV with Album names):** Export your **Liked Songs** or playlist in 1 click via **[Exportify](https://exportify.net/)** and save the CSV in the project folder (e.g. `Liked_Songs_Spotify.csv`).

### 2. Yandex Music (`yandex.txt`) — [`extractors/yandex.js`](extractors/yandex.js)
Open **Collection → Liked** on `music.yandex.ru`, scroll to the very top, open DevTools (`F12` → **Console**), and paste [`extractors/yandex.js`](extractors/yandex.js) — it handles Yandex's virtual scrolling automatically and downloads `yandex.txt`:
```javascript
(async () => {
  const seen = new Set();
  const scroller = document.querySelector('[data-virtuoso-scroller="true"]')
    || document.querySelector('[class*="CommonPage_content"]')
    || document.scrollingElement
    || document.documentElement;

  const collect = () => {
    document.querySelectorAll('[class*="HorizontalCardContainer_root"], [data-intersection-property-id]').forEach(row => {
      const title = row.querySelector('[class*="Meta_title"], [class*="Title_title"]')?.innerText?.trim();
      const artist = row.querySelector('[class*="Meta_artists"], [class*="Artists_artists"]')?.innerText?.trim();
      if (artist && title) seen.add(`${artist} - ${title}`);
    });
    document.querySelectorAll('.d-track').forEach(row => {
      const title = row.querySelector('.d-track__title')?.innerText?.trim();
      const artist = row.querySelector('.d-track__artists')?.innerText?.trim();
      if (artist && title) seen.add(`${artist} - ${title}`);
    });
  };

  scroller.scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 500));

  let stuck = 0, lastTop = -1;
  while (stuck < 5) {
    collect();
    console.log(`Collected tracks: ${seen.size}...`);
    scroller.scrollBy(0, 600);
    await new Promise(r => setTimeout(r, 400));
    const curTop = scroller.scrollTop;
    if (Math.abs(curTop - lastTop) < 5) stuck++;
    else stuck = 0;
    lastTop = curTop;
  }
  collect();

  const list = [...seen];
  const blob = new Blob([list.join('\n')], { type: 'text/plain;charset=utf-8' });
  Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'yandex.txt' }).click();
  console.log(`Done! Exported to yandex.txt: ${list.length}`);
})();
```

### 3. VK Music (`vk.txt`) — [`extractors/vk.js`](extractors/vk.js)
Open **My Music** on VK (`vk.com/audios...` or `vk.ru/audios...`), open `F12` → **Console**, and paste [`extractors/vk.js`](extractors/vk.js) — it works with the new hashed React VK UI, auto-scrolls to the end, and downloads `vk.txt`:
```javascript
(async () => {
  const seen = new Set();
  const getScrollParent = (node) => {
    while (node && node !== document.body) {
      const style = getComputedStyle(node);
      if (/(auto|scroll)/.test(style.overflowY) && node.scrollHeight > node.clientHeight) return node;
      node = node.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  };
  let scroller = null;
  const collect = () => {
    const docs = [document, ...[...document.querySelectorAll('iframe')].map(f => {
      try { return f.contentDocument; } catch { return null; }
    }).filter(Boolean)];
    for (const doc of docs) {
      for (const el of doc.querySelectorAll('span, div, time')) {
        if (el.children.length === 0 && /^\d{1,2}:\d{2}$/.test(el.textContent.trim())) {
          if (!scroller) scroller = getScrollParent(el);
          let row = el.parentElement;
          while (row && row.parentElement && row.parentElement.offsetHeight < 140) row = row.parentElement;
          if (!row) continue;
          const parts = row.innerText.split('\n').map(s => s.trim())
            .filter(s => s && !/^\d{1,2}:\d{2}$/.test(s) && !/^(E|Explicit|·|-)$/i.test(s));
          if (parts.length >= 2) seen.add(`${parts[1]} - ${parts[0]}`);
        }
      }
    }
  };
  collect();
  if (!scroller) scroller = document.scrollingElement || document.documentElement;
  let prevSize = -1, stuck = 0;
  while (stuck < 5) {
    collect();
    console.log(`Collected tracks: ${seen.size}`);
    scroller.scrollBy(0, 900);
    window.scrollBy(0, 900);
    await new Promise(r => setTimeout(r, 900));
    if (seen.size === prevSize) stuck++;
    else stuck = 0;
    prevSize = seen.size;
  }
  const list = [...seen];
  if (list.length > 0) {
    const blob = new Blob([list.join('\n')], { type: 'text/plain;charset=utf-8' });
    Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'vk.txt' }).click();
  }
  console.log(`Done! Exported to vk.txt: ${list.length}`);
})();
```

### 4. YouTube / YouTube Music (`youtube.txt`) — [`extractors/youtube.js`](extractors/youtube.js)
Open your Liked playlist on YouTube (`youtube.com/playlist?list=LL`) or YouTube Music (`music.youtube.com/playlist?list=LM`), open `F12` → **Console**, and paste [`extractors/youtube.js`](extractors/youtube.js) — it auto-scrolls and downloads `youtube.txt`:
```javascript
(async () => {
  const seen = new Set();
  const collect = () => {
    document.querySelectorAll('ytd-playlist-video-renderer').forEach(row => {
      const title = row.querySelector('#video-title')?.textContent?.trim();
      let channel = row.querySelector('#channel-name #text, .ytd-channel-name a')?.textContent?.trim() || '';
      channel = channel.replace(/\s*-\s*Topic$/i, '').trim();
      if (title && !/^\[(Deleted|Private) video\]$/i.test(title)) {
        seen.add(title.includes(' - ') ? title : (channel ? `${channel} - ${title}` : title));
      }
    });
    document.querySelectorAll('ytmusic-responsive-list-item-renderer').forEach(row => {
      const title = row.querySelector('.title-column yt-formatted-string, .title')?.textContent?.trim();
      const artist = row.querySelector('.secondary-flex-columns yt-formatted-string')?.textContent?.split('•')[0]?.trim() || '';
      if (title) seen.add(artist && !title.includes(' - ') ? `${artist} - ${title}` : title);
    });
  };
  let prevSize = -1, stuck = 0;
  while (stuck < 5) {
    collect();
    console.log(`Collected from YouTube: ${seen.size}`);
    window.scrollBy(0, 1500);
    document.scrollingElement?.scrollBy(0, 1500);
    await new Promise(r => setTimeout(r, 1000));
    if (seen.size === prevSize) stuck++;
    else stuck = 0;
    prevSize = seen.size;
  }
  const list = [...seen];
  if (list.length > 0) {
    const blob = new Blob([list.join('\n')], { type: 'text/plain;charset=utf-8' });
    Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'youtube.txt' }).click();
  }
  console.log(`Done! Exported to youtube.txt: ${list.length}`);
})();
```

---

## 🧹 Step 2: Merge, Clean & Deduplicate (`merge.py`)

```bash
python merge.py
```

What `merge.py` does:
- Strips visual garbage (`[Official Video]`, `(Lyrics)`, `(Remastered 2021)`, `(Radio Edit)`, `#hashtags`, symbols `░♬★`, non-breaking spaces `\xa0`, duplicate artist tags).
- Preserves meaningful version tags (`Remix`, `Instrumental`, `Acoustic`, `Live`, `VIP`).
- Deduplicates across all 4 platforms regardless of diacritics, case, or `feat.` formatting.
- Outputs:
  - `tracks.txt` — clean `Artist - Title` list
  - `tracks.json` — structured list with album metadata and source platforms
  - `tracks_without_youtube.txt` — delta list (**all tracks minus YouTube tracks**)

> **Tip:** If you manually edit `tracks.txt` and want to recalculate only `tracks_without_youtube.txt` without overwriting `tracks.txt`, run:
> ```bash
> python merge.py --delta
> ```

---

## 🎧 Step 3: Download in Maximum Quality (`download.py`)

```bash
python download.py
```

- Downloads audio via `yt-dlp` + `FFmpeg` in **4 parallel threads** (configurable via `--workers` or `.env`).
- Converts to **MP3 320 kbps CBR** (or native `opus` / `m4a` / `flac` via `--format`).
- Embeds cover art thumbnail and writes ID3 tags (`Artist`, `Title`, `Album`).
- Automatically retries with fallback search queries and alternative YouTube clients (`android_vr`, `mweb`, `tv`) if YouTube returns `HTTP 403 Forbidden`.
- Skips already downloaded files and logs any unavailable/age-restricted tracks with exact error reasons to `failed_tracks.txt`.

---

## ▶️ Step 4: Create a YouTube Music Playlist (`upload_ytm.py`)

Want to review and listen to your old Spotify / Yandex / VK tracks in YouTube Music?

```bash
python upload_ytm.py --title "From Old Stash (Spotify + Yandex + VK)"
```

1. Searches all tracks from `tracks_without_youtube.txt` in the official **YouTube Music** catalog in 8 threads (preferring official `Songs`, falling back to `Videos`) — **no authentication required for search**.
2. Generates a ready-to-run `create_playlist_console.js` file containing all resolved `videoId`s.
3. Open `https://music.youtube.com`, press `F12` → **Console**, paste the contents of `create_playlist_console.js`, and press **Enter** — the script will create the private playlist, add all tracks in batches of 50, and open the finished playlist in a new tab!

---

## 🤝 Credits & Third-Party Licenses

All code in this repository (`merge.py`, `download.py`, `upload_ytm.py`, and `extractors/*.js`) was written from scratch and is released under the [MIT License](LICENSE).

This project relies on (without bundling) the following open-source packages and tools:
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — *The Unlicense* (audio search & extraction)
- **[ytmusicapi](https://github.com/sigma67/ytmusicapi)** — *MIT License* (YouTube Music catalog search & API helpers)
- **[python-dotenv](https://github.com/theskumar/python-dotenv)** — *BSD-3-Clause License* (`.env` configuration loader)
- **[FFmpeg](https://ffmpeg.org/)** — *LGPL v2.1+ / GPL v2+* (external system binary invoked via CLI for audio transcoding and metadata/thumbnail embedding)
- Initial inspiration for a local Spotify + YouTube downloader workflow: **[4ngel2769/spotitube](https://github.com/4ngel2769/spotitube)** (*MIT License*).

---

## 📄 License
MIT License — see [LICENSE](LICENSE).

