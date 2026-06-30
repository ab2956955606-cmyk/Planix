/* ============ 时间选择器组件 ============ */

let tpHour = 9;
let tpMin = 0;

function getTimeStr() {
  return `${pad2(tpHour)}:${pad2(tpMin)}`;
}

function makeCol(container, range, val, onChange) {
  const H = 36;
  const VISIBLE = 5;
  const HALF = Math.floor(VISIBLE / 2);
  const R = 99;
  container.innerHTML = '';
  container.style.cssText = 'height:180px;overflow-y:scroll;scrollbar-width:none;';

  const inner = document.createElement('div');
  inner.style.cssText = `padding:${HALF * H}px 0;`;

  for (let r = 0; r < R; r++) {
    for (let i = 0; i < range; i++) {
      const el = document.createElement('div');
      el.className = 'tp-item';
      el.dataset.val = i;
      el.textContent = pad2(i);
      if (r === Math.floor(R / 2) && i === val) el.classList.add('active');
      inner.appendChild(el);
    }
  }
  container.appendChild(inner);

  let ticking = false;
  container.addEventListener('scroll', () => {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        ticking = false;
        const st = container.scrollTop;
        const max = container.scrollHeight - container.clientHeight;
        const block = range * H;
        const threshold = block * 1.5;

        if (st < threshold) container.scrollTop = st + block * (R - 3);
        else if (st > max - threshold) container.scrollTop = st - block * (R - 3);

        const centerIdx = Math.round((container.scrollTop + 90 - HALF * H) / H);
        const items = container.querySelectorAll('.tp-item');
        items.forEach(el => el.classList.remove('active'));
        const item = items[centerIdx];
        if (!item) return;
        item.classList.add('active');
        onChange(+item.dataset.val);
      });
      ticking = true;
    }
  }, { passive: true });

  container.addEventListener('click', (e) => {
    const el = e.target.closest('.tp-item');
    if (!el) return;
    const items = container.querySelectorAll('.tp-item');
    const idx = Array.from(items).indexOf(el);
    container.scrollTop = idx * H;
    items.forEach(e => e.classList.remove('active'));
    el.classList.add('active');
    onChange(+el.dataset.val);
  });
}

function scrollToCenter(container, val) {
  const H = 36;
  const range = container === tpColHour ? 24 : 60;
  const R = 99;
  const mid = Math.floor(R / 2);
  container.scrollTop = (mid * range + val) * H;
}

function buildTimeOptions() {
  makeCol(tpColHour, 24, tpHour, (v) => {
    tpHour = v;
    tpHourEl.textContent = pad2(tpHour);
    tpMinEl.textContent = pad2(tpMin);
  });
  makeCol(tpColMin, 60, tpMin, (v) => {
    tpMin = v;
    tpHourEl.textContent = pad2(tpHour);
    tpMinEl.textContent = pad2(tpMin);
  });
}

// DOM refs
const tpHourEl = $('tpHour');
const tpMinEl = $('tpMin');
const tpTrigger = $('tpTrigger');
const tpDropdown = $('tpDropdown');
const tpColHour = $('tpColHour');
const tpColMin = $('tpColMin');

function initTimePicker() {
  tpTrigger.addEventListener('click', (e) => {
    e.stopPropagation();
    const wasOpen = tpDropdown.classList.contains('open');
    document.querySelectorAll('.tp-dropdown.open').forEach(d => d.classList.remove('open'));
    if (!wasOpen) {
      buildTimeOptions();
      tpDropdown.classList.add('open');
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          scrollToCenter(tpColHour, tpHour);
          scrollToCenter(tpColMin, tpMin);
        });
      });
    }
  });

  $('tpConfirm').addEventListener('click', () => {
    tpHourEl.textContent = pad2(tpHour);
    tpMinEl.textContent = pad2(tpMin);
    tpDropdown.classList.remove('open');
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.time-wrap')) {
      tpDropdown.classList.remove('open');
    }
  });
}
