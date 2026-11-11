// Spotify Web Player Extractor (auto-scrolls virtualized list & downloads spotify.txt)
// Run in DevTools Console (F12 -> Console) on https://open.spotify.com/collection/tracks (Liked Songs) or any playlist
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
      if (!scroller && row.getAttribute('data-testid') === 'tracklist-row') {
        scroller = getScrollParent(row);
      }
      const titleEl = row.querySelector('[data-testid="internal-track-link"] div, [data-testid="internal-track-link"], [aria-colindex="2"] div[dir="auto"]');
      const title = titleEl?.textContent?.trim();
      const artists = [...row.querySelectorAll('a[href*="/artist/"]')]
        .map(a => a.textContent.trim())
        .filter(Boolean);

      if (artists.length && title) {
        seen.add(`${artists.join(', ')} - ${title}`);
      }
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

