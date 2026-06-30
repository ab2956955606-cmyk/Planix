/* ============ 日历模块 ============ */

// 由 app.js 注入的日期点击回调
let onDateSelect = null;
function setOnDateSelect(fn) { onDateSelect = fn; }

// DOM refs
const calGrid = $('calGrid');
const calMonth = $('calMonth');
const calWrap = $('calendarWrap');
const calArrow = $('calArrow');
const selectedDateLabel = $('selectedDateLabel');
const navDate = $('navDate');

function renderCalendar(year, month) {
  viewYear = year;
  viewMonth = month;
  calMonth.textContent = tf('monthFormat', { y: year, m: month + 1 });

  loadMonthNote(year, month);

  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  const daysInMonth = last.getDate();
  let startOffset = (first.getDay() + 6) % 7;
  const prevLast = new Date(year, month, 0);
  const prevDays = prevLast.getDate();
  const today = todayStr();
  // 星期行
  const wds = t('weekdayShort').map(w => `<span>${w}</span>`).join('');
  $('calGrid').previousElementSibling.innerHTML = wds;
  let html = '';
  const totalCells = Math.ceil((startOffset + daysInMonth) / 7) * 7;

  for (let i = 0; i < totalCells; i++) {
    let day, dateStr, cls = 'cal-cell';
    if (i < startOffset) {
      day = prevDays - startOffset + 1 + i;
      const m = month === 0 ? 11 : month - 1;
      const y = month === 0 ? year - 1 : year;
      dateStr = fmtDate(y, m, day);
      cls += ' other';
    } else if (i >= startOffset + daysInMonth) {
      day = i - startOffset - daysInMonth + 1;
      const m = month === 11 ? 0 : month + 1;
      const y = month === 11 ? year + 1 : year;
      dateStr = fmtDate(y, m, day);
      cls += ' other';
    } else {
      day = i - startOffset + 1;
      dateStr = fmtDate(year, month, day);
      if (dateStr === today) cls += ' today';
    }
    if (dateStr === selectedDate) cls += ' selected';

    const status = getDayStatus(dateStr);
    if (status === 'has-plan') cls += ' has-plan';
    else if (status === 'done-all') cls += ' done-all';

    html += `<div class="${cls}" data-date="${dateStr}">${day}</div>`;
  }
  calGrid.innerHTML = html;

  calGrid.querySelectorAll('.cal-cell').forEach(el => {
    el.addEventListener('click', () => {
      if (onDateSelect) onDateSelect(el.dataset.date);
    });
  });
}

function updateNavDate(dateStr) {
  const d = parseDate(dateStr);
  navDate.textContent = formatDateStr(d.getFullYear(), d.getMonth() + 1, d.getDate());
}

function updateSelectedLabel(dateStr) {
  const d = parseDate(dateStr);
  const ts = todayStr();
  if (dateStr === ts) { selectedDateLabel.textContent = t('todayLabel'); return; }
  selectedDateLabel.textContent = tf('dateLabel', { m: d.getMonth() + 1, d: d.getDate(), w: t('weekdayNames')[d.getDay()] });
}

function collapseCalendar() {
  calOpen = false;
  calWrap.classList.add('collapsed');
  calArrow.classList.remove('open');
}

function initCalendar() {
  // 日历折叠切换
  $('calToggle').addEventListener('click', () => {
    calOpen = !calOpen;
    calWrap.classList.toggle('collapsed', !calOpen);
    calArrow.classList.toggle('open', calOpen);
  });

  // 上一月 / 下一月
  $('calPrev').addEventListener('click', () => {
    const m = viewMonth - 1;
    renderCalendar(m < 0 ? viewYear - 1 : viewYear, m < 0 ? 11 : m);
  });
  $('calNext').addEventListener('click', () => {
    const m = viewMonth + 1;
    renderCalendar(m > 11 ? viewYear + 1 : viewYear, m > 11 ? 0 : m);
  });
}
