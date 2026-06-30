/* ============ 语言包 ============ */

const langStrings = {
  zh: {
    navTitle: '我的笔记',
    navToggle: '日历',
    btnToday: '今天',
    panelTitle: '📋 规划与完成情况',
    notesLabel: '📝 备注',
    notesPlaceholder: '这个月的备注…',
    completionLabel: '完成情况',
    completionPlaceholder: '写下完成情况…',
    addPlaceholder: '添加事项…',
    tpConfirm: '完成',
    emptyPlans: '暂无规划',
    emptyAddHint: '在下方添加今日事项',
    todayLabel: '📌 今天',
    items: '{n} 项',
    monthFormat: '{y}年{m}月',
    dateFormat: '{y}年{m}月{d}日',
    weekdayShort: ['一','二','三','四','五','六','日'],
    weekdayNames: ['日','一','二','三','四','五','六'],
    dateLabel: '{m}月{d}日 星期{w}',
  },
  en: {
    navTitle: 'My Notes',
    navToggle: 'Calendar',
    btnToday: 'Today',
    panelTitle: '📋 Plans & Completion',
    notesLabel: '📝 Notes',
    notesPlaceholder: 'Notes for this month…',
    completionLabel: 'Completion',
    completionPlaceholder: 'Write completion notes…',
    addPlaceholder: 'Add a task…',
    tpConfirm: 'Done',
    emptyPlans: 'No plans yet',
    emptyAddHint: 'Add a task below',
    todayLabel: '📌 Today',
    items: '{n} items',
    monthFormat: '{m}/{y}',
    dateFormat: '{y}-{m}-{d}',
    weekdayShort: ['Mo','Tu','We','Th','Fr','Sa','Su'],
    weekdayNames: ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'],
    dateLabel: '{w}, {m}/{d}',
  }
};

let currentLang = 'zh';
let onLangChange = null;

function t(key) {
  return langStrings[currentLang][key] || key;
}

function tf(key, vars) {
  let s = t(key);
  for (const k in vars) {
    s = s.replace(`{${k}}`, vars[k]);
  }
  return s;
}

function padMonth(m) {
  return String(m).padStart(2, '0');
}
function padDay(d) {
  return String(d).padStart(2, '0');
}

/** 对各语言不同的日期格式做统一输出 */
function formatDateStr(y, m, d) {
  return tf('dateFormat', { y, m: padMonth(m), d: padDay(d) });
}

function setLang(l) {
  if (l === currentLang) return;
  currentLang = l;
  localStorage.setItem('my_notes_lang', l);
  // 更新 Language 切换按钮高亮
  document.querySelectorAll('.lang-opt').forEach(el => {
    el.classList.toggle('active', el.dataset.lang === l);
  });
  if (onLangChange) onLangChange(l);
}

function applyStaticI18n() {
  // 更新 data-i18n 静态元素
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
  // 更新 placeholder
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
}

function initLang(onChange) {
  onLangChange = onChange;
  const saved = localStorage.getItem('my_notes_lang');
  if (saved === 'zh' || saved === 'en') currentLang = saved;
  // 初始化高亮
  document.querySelectorAll('.lang-opt').forEach(el => {
    el.classList.toggle('active', el.dataset.lang === currentLang);
  });
  // 首次应用静态文本
  applyStaticI18n();

  // ── 键盘快捷键：Ctrl+L / ⌘L 切换中英文 ──
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
      e.preventDefault();
      const next = currentLang === 'zh' ? 'en' : 'zh';
      setLang(next);
    }
  });
}
