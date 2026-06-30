/* ============ 工具函数 ============ */

function $(id) { return document.getElementById(id); }

function pad2(n) {
  return String(n).padStart(2, '0');
}

function fmtDate(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}

function todayStr() {
  const d = new Date();
  return fmtDate(d.getFullYear(), d.getMonth(), d.getDate());
}

function parseDate(str) {
  const [y, m, d] = str.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}
