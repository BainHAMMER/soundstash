# SoundStash — Сборка медиатеки (Spotify + Яндекс + ВК + YouTube), скачивание в 320 kbps и перенос в YouTube Music

**[🇬🇧 English version (README.md)](README.md)**

Набор лёгких и быстрых Python-скриптов для полного наведения порядка в музыке со всех площадок:
1. **Сборка и очистка (`merge.py`)** — объединяет треки из **Spotify**, **Яндекс Музыки**, **ВК** и **YouTube Music**, чистит мусорные приписки (`[Official Video]`, `Remastered`, `\xa0`, дубли артистов) и удаляет межлистовые дубликаты.
2. **Расчёт дельты (`tracks_without_youtube.txt`)** — автоматически собирает список треков, которые были у вас в Spotify / Яндексе / ВК, но ещё отсутствуют в лайках YouTube Music.
3. **Скачивание в максимальном качестве (`download.py`)** — качает всю базу в **MP3 320 kbps** (или исходный `opus` / `m4a` / `flac`) в несколько потоков через `yt-dlp` + `FFmpeg`, вшивает обложку и прописывает чистые ID3-теги (`Artist`, `Title`, `Album`). Автоматически обходит `HTTP 403` через резервные клиенты YouTube.
4. **Импорт плейлиста в YouTube Music (`upload_ytm.py`)** — в 8 потоков находит официальные `videoId` треков в каталоге YouTube Music (без авторизации) и генерирует готовый скрипт `create_playlist_console.js`. Достаточно вставить его в консоль браузера на вкладке `music.youtube.com` — и приватный плейлист на сотни треков соберётся за 10 секунд без возни с OAuth и заблокированными куками.

---

## 🚀 Быстрый старт

### 1. Требования
- **Python 3.10+**
- **FFmpeg** (скрипт находит его в PATH или в пакетах WinGet автоматически):
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

## 📥 Шаг 1: Выгрузка списков со своих площадок

Готовые скрипты для консоли браузера, которые **сами прокручивают страницу до конца и скачивают готовые `.txt`-файлы**, лежат в папке [`extractors/`](extractors/). Сложите полученные файлы в рабочую папку (корень проекта или папку из `DATA_DIR` в `.env`):

> **Подсказка для Chrome / Edge:** Если при первой вставке в `F12 → Console` браузер напишет `Warning: Don’t paste code into the DevTools Console...`, просто напечатайте с клавиатуры `allow pasting`, нажмите **Enter**, и вставка разблокируется.

### 1. Spotify (`spotify.txt` или `*spotify*.csv`) — [`extractors/spotify.js`](extractors/spotify.js)
- **Вариант А (Скрипт для консоли):** Откройте «Любимые треки» (`open.spotify.com/collection/tracks`) или любой плейлист в веб-плеере Spotify, нажмите `F12` → **Console** и вставьте [`extractors/spotify.js`](extractors/spotify.js) — он сам плавно пролистает виртуальный список и скачает `spotify.txt`:
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
    console.log(`Собрано со Spotify: ${seen.size}...`);
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
  console.log(`Готово! Всего выгружено в spotify.txt: ${list.length}`);
})();
```
- **Вариант Б (CSV через Exportify с названиями альбомов):** Выгрузите **Liked Songs** в один клик через **[Exportify](https://exportify.net/)** и положите CSV-файл в папку проекта (`Liked_Songs_Spotify.csv`).

### 2. Яндекс Музыка (`yandex.txt`) — [`extractors/yandex.js`](extractors/yandex.js)
Откройте «Коллекция → Мне нравится» на `music.yandex.ru`, перемотайте в самый верх, нажмите `F12` → **Console** и вставьте [`extractors/yandex.js`](extractors/yandex.js) — скрипт сам плавно пролистает виртуальный список и скачает готовый `yandex.txt`:
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
    console.log(`Собрано треков: ${seen.size}...`);
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
  console.log(`Готово! Всего выгружено в yandex.txt: ${list.length}`);
})();
```

### 3. Музыка ВКонтакте (`vk.txt`) — [`extractors/vk.js`](extractors/vk.js)
Откройте раздел «Моя музыка» в ВК (`vk.com/audios...` или `vk.ru/audios...`), нажмите `F12` → **Console** и вставьте [`extractors/vk.js`](extractors/vk.js) — скрипт не зависит от зашифрованных React-классов ВК, сам проскроллит страницу до конца и скачает `vk.txt`:
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
    console.log(`Собрано треков: ${seen.size}`);
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
  console.log(`Готово! Всего выгружено в vk.txt: ${list.length}`);
})();
```

### 4. YouTube и YouTube Music (`youtube.txt`) — [`extractors/youtube.js`](extractors/youtube.js)
Откройте плейлист понравившихся на обычном YouTube (`youtube.com/playlist?list=LL`) или в YouTube Music (`music.youtube.com/playlist?list=LM`), нажмите `F12` → **Console** и вставьте [`extractors/youtube.js`](extractors/youtube.js) — он сам прокрутит список и скачает `youtube.txt`:
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
    console.log(`Собрано с YouTube: ${seen.size}`);
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
  console.log(`Готово! Выгружено в youtube.txt: ${list.length}`);
})();
```

---

## 🧹 Шаг 2: Объединение, очистка и дедупликация (`merge.py`)

```bash
python merge.py
```

Что делает скрипт:
- Убирает визуальный и технический мусор (`[Official Video]`, `(Lyrics)`, `(Remastered 2021)`, `(Radio Edit)`, `#хэштеги`, символы `░♬★`, неразрывные пробелы `\xa0` с приписками Яндекса, дублирующихся артистов через запятую).
- Бережно сохраняет важные версии (`Remix`, `Instrumental`, `Acoustic`, `Live`, `VIP`).
- Схлопывает дубликаты между всеми 4 площадками (с учётом диакритики, регистра и `feat.`).
- Создаёт:
  - `tracks.txt` — единый чистый список `Artist - Title`
  - `tracks.json` — полный JSON с альбомами и источниками каждого трека
  - `tracks_without_youtube.txt` — дельта (**все треки минус лайки YouTube**)

> **Совет:** Если вы вручную отредактировали `tracks.txt` и хотите пересчитать только `tracks_without_youtube.txt` (не перезаписывая `tracks.txt`), запустите:
> ```bash
> python merge.py --delta
> ```

---

## 🎧 Шаг 3: Скачивание в максимальном качестве (`download.py`)

```bash
python download.py
```

- Качает треки в **4 потока** (настраивается флагом `--workers` или в `.env`).
- По умолчанию сохраняет в **MP3 320 kbps CBR** (можно выбрать `opus`, `m4a` или `flac` через `--format`).
- Вшивает обложку трека и прописывает теги (`Artist`, `Title`, `Album`).
- При ошибке `HTTP 403 Forbidden` автоматически переключается на резервные клиенты (`android_vr`, `mweb`, `tv`), а при пустой выдаче пробует упрощённый поисковый запрос.
- Уже скачанные файлы мгновенно пропускаются; проблемные треки (например, с возрастным ограничением 18+ или удалённые) записываются в `failed_tracks.txt` с точной причиной ошибки.

---

## ▶️ Шаг 4: Создание плейлиста в YouTube Music (`upload_ytm.py`)

Хотите отслушать старые запасы из Spotify / Яндекса / ВК прямо в YouTube Music?

```bash
python upload_ytm.py --title "Из старых запасов (Spotify + Яндекс + ВК)"
```

1. Скрипт в 8 потоков находит все треки из `tracks_without_youtube.txt` в официальном каталоге **YouTube Music** (сначала ищет официальные аудиозаписи `Songs`, затем клипы `Videos`) и сохраняет кэш найденных ID в `ytm_upload_state.json`.
2. Автоматически создаёт файл `create_playlist_console.js`.
3. Откройте `create_playlist_console.js`, скопируйте его (`Ctrl+A` → `Ctrl+C`), перейдите на вкладку `https://music.youtube.com`, откройте `F12` → **Console**, вставьте скрипт и нажмите **Enter** — он сам создаст приватный плейлист, зальёт все треки пачками по 50 штук и откроет готовый плейлист в новой вкладке.

---

## 📄 Лицензия
MIT License — см. [LICENSE](LICENSE).

