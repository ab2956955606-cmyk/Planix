/* ============ 规划与完成情况模块 ============ */

// DOM refs
const planList = $('planList');
const planInput = $('planInput');
const planCount = $('planCount');

// ─── 选中日期 ───
function selectDate(dateStr) {
  selectedDate = dateStr;
  renderCalendar(viewYear, viewMonth);
  renderDay(dateStr);
  updateNavDate(dateStr);
  updateSelectedLabel(dateStr);
}

// ─── 自动撑高 textarea ───
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = el.scrollHeight + 'px';
}

// ─── 渲染规划列表 ───
function renderDay(dateStr) {
  const data = getDayData(dateStr);
  const plans = data.plans || [];

  if (plans.length === 0) {
    planList.innerHTML = `<div class="empty-state">${t('emptyPlans')}<br>${t('emptyAddHint')}</div>`;
    planCount.textContent = tf('items', { n: 0 });
    return;
  }

  planList.innerHTML = plans.map((p, idx) => {
    const doneClass = p.done ? 'done' : '';
    const checkedClass = p.done ? 'checked' : '';
    return `
      <div class="plan-item ${doneClass}" data-id="${p.id}">
        <div class="plan-top">
          <span class="plan-num">${idx + 1}</span>
          <button class="plan-check ${checkedClass}" data-id="${p.id}">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2.5 6l2.5 2.5L9.5 3" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <div class="plan-body">
            <div class="plan-meta">
              ${p.time ? `<span class="plan-time">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="#007aff" stroke-width="1.6" opacity=".6"/>
                  <path d="M12 7.5v4.5l3 3" stroke="#007aff" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" opacity=".8"/>
                </svg>
                <span class="pt-part">${p.time.split(':')[0] || '00'}</span>
                <span class="pt-sep"></span>
                <span class="pt-part">${p.time.split(':')[1] || '00'}</span>
              </span>` : ''}
              <span class="plan-text">${escapeHtml(p.text)}</span>
              <button class="plan-delete" data-id="${p.id}">✕</button>
            </div>
            <div class="plan-completion">
              <span class="plan-completion-label">${t('completionLabel')}</span>
              <textarea placeholder="${t('completionPlaceholder')}" data-id="${p.id}">${escapeHtml(p.completion || '')}</textarea>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');

  planCount.textContent = tf('items', { n: plans.length });

  // 事件绑定
  planList.querySelectorAll('.plan-check').forEach(btn => {
    btn.addEventListener('click', () => togglePlan(dateStr, btn.dataset.id));
  });
  planList.querySelectorAll('.plan-delete').forEach(btn => {
    btn.addEventListener('click', (e) => { e.stopPropagation(); deletePlan(dateStr, btn.dataset.id); });
  });
  planList.querySelectorAll('.plan-completion textarea').forEach(inp => {
    autoResize(inp);
    inp.addEventListener('input', () => {
      autoResize(inp);
      updateCompletion(dateStr, inp.dataset.id, inp.value);
    });
  });
}

// ─── 添加规划 ───
function addPlan() {
  const text = planInput.value.trim();
  if (!text) return;
  const data = getDayData(selectedDate);
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 4);
  data.plans.push({ id, time: getTimeStr(), text, done: false, completion: '' });
  putDayData(selectedDate, data);
  planInput.value = '';
  planInput.style.height = 'auto';
  renderDay(selectedDate);
  renderCalendar(viewYear, viewMonth);
}

// ─── 勾选切换 ───
function togglePlan(dateStr, id) {
  const data = getDayData(dateStr);
  const plan = data.plans.find(p => p.id === id);
  if (!plan) return;
  plan.done = !plan.done;
  putDayData(dateStr, data);
  renderDay(dateStr);
  renderCalendar(viewYear, viewMonth);
}

// ─── 删除 ───
function deletePlan(dateStr, id) {
  const data = getDayData(dateStr);
  data.plans = data.plans.filter(p => p.id !== id);
  putDayData(dateStr, data);
  renderDay(dateStr);
  renderCalendar(viewYear, viewMonth);
}

// ─── 更新完成情况 ───
const completionTimers = {};
function updateCompletion(dateStr, id, value) {
  clearTimeout(completionTimers[id]);
  completionTimers[id] = setTimeout(() => {
    const data = getDayData(dateStr);
    const plan = data.plans.find(p => p.id === id);
    if (plan) { plan.completion = value.trim(); putDayData(dateStr, data); }
    renderCalendar(viewYear, viewMonth);
  }, 400);
}

// ─── 初始化规划模块 ───
function initPlans() {
  // Enter 提交，Shift+Enter/Ctrl+Enter 换行
  planInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      addPlan();
    }
  });
  // 自动撑高
  planInput.addEventListener('input', () => autoResize(planInput));
  $('addPlanBtn').addEventListener('click', addPlan);
}
