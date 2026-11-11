// YouTube & YouTube Music Extractor (auto-scrolls playlist & downloads youtube.txt)
// Run in DevTools Console (F12 -> Console) on:
//   - https://www.youtube.com/playlist?list=LL (Liked videos)
//   - https://music.youtube.com/playlist?list=LM (Liked music)
(async () => {
  const seen = new Set();

  const collect = () => {
    // 1. Standard YouTube playlist (youtube.com/playlist?list=LL)
    document.querySelectorAll('ytd-playlist-video-renderer').forEach(row => {
      const title = row.querySelector('#video-title')?.textContent?.trim();
      let channel = row.querySelector('#channel-name #text, .ytd-channel-name a')?.textContent?.trim() || '';
      channel = channel.replace(/\s*-\s*Topic$/i, '').trim();
      if (title && !/^\[(Deleted|Private) video\]$/i.test(title)) {
        seen.add(title.includes(' - ') ? title : (channel ? `${channel} - ${title}` : title));
      }
    });

    // 2. YouTube Music playlist (music.youtube.com/playlist?list=LM)
    document.querySelectorAll('ytmusic-responsive-list-item-renderer').forEach(row => {
      const title = row.querySelector('.title-column yt-formatted-string, .title')?.textContent?.trim();
      const artist = row.querySelector('.secondary-flex-columns yt-formatted-string')?.textContent?.split('•')[0]?.trim() || '';
      if (title) {
        seen.add(artist && !title.includes(' - ') ? `${artist} - ${title}` : title);
      }
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

