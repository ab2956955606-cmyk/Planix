/* ============ 应用入口：协调各模块 ============ */

(function init() {
  // ── 语言系统 ──
  initLang(function onLang() {
    // 语言切换时刷新所有动态渲染的内容
    applyStaticI18n();
    renderCalendar(viewYear, viewMonth);
    renderDay(selectedDate);
    updateNavDate(selectedDate);
    updateSelectedLabel(selectedDate);
    // 更新"今天"按钮文字
    $('btnToday').textContent = t('btnToday');
  });

  // ── Language 点击切换 ──
  document.querySelectorAll('.lang-opt').forEach(el => {
    el.addEventListener('click', () => setLang(el.dataset.lang));
  });

  // ── 注册日历日期点击回调 ──
  setOnDateSelect(selectDate);

  // ── 初始化各模块 ──
  initNotes();
  initCalendar();
  initPlans();
  initTimePicker();

  // ── 初始化状态：默认今天 ──
  const d = new Date();
  const s = todayStr();
  selectedDate = s;
  renderCalendar(d.getFullYear(), d.getMonth());
  renderDay(s);
  updateNavDate(s);
  updateSelectedLabel(s);

  // 日历展开
  document.getElementById('calArrow').classList.add('open');
  calOpen = true;

  // ── 「今天」按钮 ──
  $('btnToday').addEventListener('click', () => {
    const d2 = new Date();
    const y = d2.getFullYear(), m = d2.getMonth();
    const t = todayStr();
    selectedDate = t;
    renderCalendar(y, m);
    renderDay(t);
    updateNavDate(t);
    updateSelectedLabel(t);
  });
})();
