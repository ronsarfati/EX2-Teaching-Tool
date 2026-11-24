// Polls the attendance JSON every 2.5 s (D4) and redraws the live table.
// Nicknames go through textContent, never innerHTML: they are typed by students.
const POLL_MS = 2500;
const rowsEl = document.getElementById("attendance-rows");
const nEl = document.getElementById("n");
const dEl = document.getElementById("d");
const statusEl = document.getElementById("status");
const errorEl = document.getElementById("attendance-error");

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  td.dir = "auto"; // Hebrew and English nicknames each align correctly
  return td;
}

function emptyRow() {
  const tr = document.createElement("tr");
  const td = cell("Nobody has checked in yet. Show the projector and ask students to scan.");
  td.colSpan = 2;
  tr.append(td);
  return tr;
}

function show(data) {
  nEl.textContent = data.n;
  dEl.textContent = data.head_count === null ? "—" : data.head_count; // "—" when no photo
  statusEl.textContent = data.consistency === null ? "—" : data.consistency;
  statusEl.dataset.state = data.consistency === null ? "none" : data.consistency; // drives the chip colour in CSS
  if (data.check_ins.length === 0) {
    rowsEl.replaceChildren(emptyRow());
    return;
  }
  rowsEl.replaceChildren(...data.check_ins.map((c) => {
    const tr = document.createElement("tr");
    tr.append(cell(c.nickname), cell(new Date(c.checked_in_at * 1000).toLocaleTimeString("en-GB", { timeZone: "Asia/Jerusalem" })));
    return tr;
  }));
}

async function poll() {
  try {
    const response = await fetch(document.body.dataset.api, { cache: "no-store" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    show(await response.json());
    errorEl.hidden = true;
  } catch (error) {
    errorEl.hidden = false; // keep the last table, tell the lecturer
  }
}

poll();
setInterval(poll, POLL_MS);
