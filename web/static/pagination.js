// Client-side paging for the small, auditable source catalogue. API responses stay complete.
function paginateTable(table, label, renderRows) {
  let items = [], page = 1, size = 10;

  function controls(position) {
    const nav = document.createElement("nav");
    nav.className = "table-pagination";
    nav.setAttribute("aria-label", "Paginacja: " + label + (position === "bottom" ? " (dół tabeli)" : ""));
    const sizeLabel = document.createElement("label");
    sizeLabel.textContent = "Na stronie: ";
    const select = document.createElement("select");
    select.setAttribute("aria-controls", table.id);
    for (const n of [10, 25, 50]) select.add(new Option(String(n), String(n)));
    sizeLabel.append(select);
    const status = document.createElement("span");
    status.className = "small muted";
    if (position === "top") {
      status.setAttribute("role", "status");
      status.setAttribute("aria-atomic", "true");
    }
    const actions = document.createElement("div");
    actions.className = "pagination-controls";
    function button(text, title, target) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "secondary";
      b.textContent = text;
      b.setAttribute("aria-label", title);
      b.setAttribute("aria-controls", table.id);
      b.onclick = () => { page = target(); render(); };
      return b;
    }
    const first = button("«", "Pierwsza strona", () => 1);
    const prev = button("Poprzednia", "Poprzednia strona", () => page - 1);
    const numbers = document.createElement("span");
    numbers.className = "pagination-pages";
    const next = button("Następna", "Następna strona", () => page + 1);
    const last = button("»", "Ostatnia strona", () => Math.ceil(items.length / size));
    actions.append(first, prev, numbers, next, last);
    nav.append(sizeLabel, status, actions);
    select.onchange = () => { size = Number(select.value); page = 1; render(); };
    return {nav, select, status, first, prev, next, last, numbers, button};
  }

  const top = controls("top"), bottom = controls("bottom");
  // Both controls stay outside the horizontally scrolling table on phones.
  table.parentElement.before(top.nav);
  table.parentElement.after(bottom.nav);

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
    for (const ui of [top, bottom]) {
      ui.select.value = String(size);
      ui.status.textContent = items.length
        ? `${start + 1}–${Math.min(start + size, items.length)} z ${items.length} · Strona ${page} z ${pages}`
        : "0 pozycji · Strona 1 z 1";
      ui.first.disabled = ui.prev.disabled = page === 1;
      ui.next.disabled = ui.last.disabled = page === pages;
      // Keep a bounded set of page buttons even for a much larger registry.
      const firstPage = Math.max(1, Math.min(page - 2, pages - 4));
      const lastPage = Math.min(pages, firstPage + 4);
      const currentFocus = document.activeElement;
      const focusedPage = ui.numbers.contains(currentFocus) ? currentFocus.dataset.page : null;
      ui.numbers.replaceChildren();
      for (let number = firstPage; number <= lastPage; number++) {
        const b = ui.button(String(number), "Strona " + number, () => number);
        b.dataset.page = String(number);
        if (number === page) b.setAttribute("aria-current", "page");
        b.disabled = !items.length;
        ui.numbers.append(b);
      }
      if (focusedPage) {
        const target = [...ui.numbers.children].find(b => b.dataset.page === focusedPage)
          || ui.numbers.querySelector('[aria-current="page"]');
        target.focus({preventScroll: true});
      }
    }
  }
  return {setItems(rows) { items = rows; render(); }};
}
