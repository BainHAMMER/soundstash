// VK Music Extractor (class-agnostic, works with hashed React UI & downloads vk.txt)
// Run in DevTools Console (F12 -> Console) on https://vk.com/audios... or https://vk.ru/audios...
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
      const all = doc.querySelectorAll('span, div, time');
      for (const el of all) {
        if (el.children.length === 0 && /^\d{1,2}:\d{2}$/.test(el.textContent.trim())) {
          if (!scroller) scroller = getScrollParent(el);
          let row = el.parentElement;
          while (row && row.parentElement && row.parentElement.offsetHeight < 140) {
            row = row.parentElement;
          }
          if (!row) continue;
          const parts = row.innerText
            .split('\n')
            .map(s => s.trim())
            .filter(s => s && !/^\d{1,2}:\d{2}$/.test(s) && !/^(E|Explicit|·|-)$/i.test(s));
          if (parts.length >= 2) {
            // In VK UI: first line is Title, second line is Artist -> save as "Artist - Title"
            seen.add(`${parts[1]} - ${parts[0]}`);
          }
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
  console.log('Примеры первых 5 треков:', list.slice(0, 5));
  if (list.length > 0) {
    const blob = new Blob([list.join('\n')], { type: 'text/plain;charset=utf-8' });
    Object.assign(document.createElement('a'), { href: URL.createObjectURL(blob), download: 'vk.txt' }).click();
  }
  console.log(`Готово! Всего выгружено в vk.txt: ${list.length}`);
})();

