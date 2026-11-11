// Yandex Music Extractor (auto-scrolls virtual list & downloads yandex.txt)
// Run in DevTools Console (F12 -> Console) on https://music.yandex.ru (Collection -> Liked or any playlist)
(async () => {
  const seen = new Set();
  const scroller = document.querySelector('[data-virtuoso-scroller="true"]')
    || document.querySelector('[class*="CommonPage_content"]')
    || document.scrollingElement
    || document.documentElement;

  const collect = () => {
    // New Yandex Music UI
    document.querySelectorAll('[class*="HorizontalCardContainer_root"], [data-intersection-property-id]').forEach(row => {
      const title = row.querySelector('[class*="Meta_title"], [class*="Title_title"]')?.innerText?.trim();
      const artist = row.querySelector('[class*="Meta_artists"], [class*="Artists_artists"]')?.innerText?.trim();
      if (artist && title) seen.add(`${artist} - ${title}`);
    });
    // Classic Yandex Music UI
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

