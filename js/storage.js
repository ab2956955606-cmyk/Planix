/* ============ 数据持久化层 ============ */

const STORAGE_KEY = 'my_notes_data';

function loadAll() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}; } catch { return {}; }
}

function saveAll(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
}

function getDayData(dateStr) {
  const all = loadAll();
  if (!all[dateStr]) all[dateStr] = { plans: [] };
  return all[dateStr];
}

function putDayData(dateStr, data) {
  const all = loadAll();
  all[dateStr] = data;
  saveAll(all);
}

function getDayStatus(dateStr) {
  const all = loadAll();
  const d = all[dateStr];
  if (!d || !d.plans || !d.plans.length) return 'none';
  return d.plans.some(p => !p.done) ? 'has-plan' : 'done-all';
}
