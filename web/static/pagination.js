// Client-side paging for the small, auditable source catalogue. API responses stay complete.
function paginateTable(table, label, renderRows) {
  let items = [], page = 1, size = 10;
  const nav = document.createElement("nav");
  nav.className = "table-pagination";
  nav.setAttribute("aria-label", "Paginacja: " + label);
  const sizeLabel = document.createElement("label");
  sizeLabel.textContent = "Na stronie: ";
  const select = document.createElement("select");
  select.setAttribute("aria-controls", table.id);
  for (const n of [10, 25, 50]) select.add(new Option(String(n), String(n)));
  sizeLabel.append(select);
  const status = document.createElement("span");
  status.className = "small muted";
  status.setAttribute("role", "status");
  status.setAttribute("aria-atomic", "true");
  const controls = document.createElement("div");
  controls.className = "pagination-controls";
  function button(text, title, target) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "secondary";
    b.textContent = text;
    b.setAttribute("aria-label", title);
    b.setAttribute("aria-controls", table.id);
    b.onclick = () => { page = target(); render(); };
    controls.append(b);
    return b;
  }
  const first = button("«", "Pierwsza strona", () => 1);
  const prev = button("Poprzednia", "Poprzednia strona", () => page - 1);
  const next = button("Następna", "Następna strona", () => page + 1);
  const last = button("»", "Ostatnia strona", () => Math.ceil(items.length / size));
  nav.append(sizeLabel, status, controls);
  // Keep controls outside the horizontally scrolling table, including on phones.
  table.parentElement.after(nav);
  function render() {
    const pages = Math.max(1, Math.ceil(items.length / size));
    page = Math.max(1, Math.min(page, pages));
    const start = (page - 1) * size;
    renderRows(items.slice(start, start + size));
    if (!items.length) {
      const cell = table.tBodies[0].insertRow().insertCell();
      cell.colSpan = table.tHead.rows[0].cells.length;
      cell.className = "muted";
      cell.textContent = "Brak pozycji.";
    }
    status.textContent = items.length
      ? `${start + 1}–${Math.min(start + size, items.length)} z ${items.length} · Strona ${page} z ${pages}`
      : "0 pozycji · Strona 1 z 1";
    first.disabled = prev.disabled = page === 1;
    next.disabled = last.disabled = page === pages;
  }
  select.onchange = () => { size = Number(select.value); page = 1; render(); };
  return {setItems(rows) { items = rows; render(); }};
}
