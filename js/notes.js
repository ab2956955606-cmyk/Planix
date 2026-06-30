/* ============ 月备注功能 ============ */

function monthNoteKey(year, month) {
  return `note_${year}_${month}`;
}

function saveMonthNote() {
  const el = $('calNoteInput');
  if (!el) return;
  localStorage.setItem(monthNoteKey(viewYear, viewMonth), el.value);
}

function loadMonthNote(year, month) {
  const el = $('calNoteInput');
  if (!el) return;
  el.value = localStorage.getItem(monthNoteKey(year, month)) || '';
}

function initNotes() {
  const el = $('calNoteInput');
  if (!el) return;
  let timer = null;
  el.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(saveMonthNote, 400);
  });
}
