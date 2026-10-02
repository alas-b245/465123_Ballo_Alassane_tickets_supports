const state = { token: localStorage.getItem('support-token') || 'alice-token', selected: null };
const list = document.querySelector('#ticket-list');
const details = document.querySelector('#details');
const notice = document.querySelector('#notice');
const identity = document.querySelector('#identity');
identity.value = state.token;

const headers = (extra = {}) => ({ Authorization: `Bearer ${state.token}`, ...extra });

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: headers(options.headers) });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try { message += `\n${(await response.json()).detail}`; } catch (_) {}
    throw new Error(message);
  }
  return response.json();
}

function showError(error) {
  notice.textContent = error.message;
  notice.classList.remove('hidden');
}

function clearError() { notice.classList.add('hidden'); }

async function loadTickets() {
  clearError();
  list.innerHTML = '<p class="hint">Загрузка…</p>';
  try {
    const tickets = await api('/api/v1/tickets');
    list.innerHTML = tickets.length ? tickets.map(ticket => `
      <article class="ticket" data-id="${ticket.id}">
        <h3>${escapeHtml(ticket.title)}</h3>
        <div class="meta"><span class="badge ${ticket.status}">${ticket.status}</span><span>${ticket.priority}</span><span>${ticket.category || 'без категории'}</span></div>
      </article>`).join('') : '<p class="hint">Обращений пока нет.</p>';
    document.querySelectorAll('.ticket').forEach(node => node.addEventListener('click', () => openTicket(node.dataset.id)));
  } catch (error) { list.innerHTML = ''; showError(error); }
}

async function openTicket(id) {
  state.selected = id;
  details.classList.remove('empty');
  details.innerHTML = '<p class="hint">Загрузка…</p>';
  try {
    const [ticket, history] = await Promise.all([
      api(`/api/v1/tickets/${id}`),
      api(`/api/v1/tickets/${id}/history`),
    ]);
    details.innerHTML = `
      <div class="details-head"><div><h2>${escapeHtml(ticket.title)}</h2><div class="detail-meta"><span class="badge ${ticket.status}">${ticket.status}</span><span>${ticket.priority}</span><span>${ticket.category || 'без категории'}</span><span>автор: ${ticket.author_id}</span></div></div></div>
      <p class="description">${escapeHtml(ticket.description)}</p>
      <form id="status-form" class="status-form"><select name="status"><option>NEW</option><option>IN_PROGRESS</option><option>CLOSED</option></select><button>Изменить статус</button></form>
      <div class="timeline"><h3>История</h3>${renderTimeline(history.items)}</div>`;
    details.querySelector('[name=status]').value = ticket.status;
    details.querySelector('#status-form').addEventListener('submit', changeStatus);
  } catch (error) { details.innerHTML = `<div class="notice">${escapeHtml(error.message)}</div>`; }
}

function renderTimeline(items) {
  if (!items.length) return '<p class="hint">Событий пока нет.</p>';
  return items.slice().reverse().map(event => `<div class="timeline-item"><strong>${eventLabel(event)}</strong><span>${new Date(event.occurred_at).toLocaleString('ru-RU')}</span></div>`).join('');
}

function eventLabel(event) {
  const data = event.data || {};
  if (event.event_type === 'ticket.created') return 'Обращение создано';
  if (event.event_type === 'ticket.status_changed') return `Статус: ${data.from} → ${data.to}`;
  if (event.event_type === 'ticket.priority_changed') return `Приоритет: ${data.from} → ${data.to}`;
  if (event.event_type === 'ticket.classified') return `Категория определена: ${data.category}`;
  return event.event_type;
}

async function changeStatus(event) {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  try {
    await api(`/api/v1/tickets/${state.selected}/status`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: new FormData(event.currentTarget).get('status') }) });
    await Promise.all([loadTickets(), openTicket(state.selected)]);
  } catch (error) { showError(error); } finally { button.disabled = false; }
}

document.querySelector('#create-form').addEventListener('submit', async event => {
  event.preventDefault(); clearError();
  const button = event.currentTarget.querySelector('button');
  button.disabled = true; button.textContent = 'Создаём…';
  const data = Object.fromEntries(new FormData(event.currentTarget));
  try {
    const ticket = await api('/api/v1/tickets', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(data) });
    event.currentTarget.reset(); await loadTickets(); await openTicket(ticket.id);
  } catch (error) { showError(error); } finally { button.disabled = false; button.textContent = 'Создать'; }
});

identity.addEventListener('change', () => { state.token = identity.value; localStorage.setItem('support-token', state.token); state.selected = null; details.innerHTML = '<div class="empty-state">Выберите обращение слева, чтобы увидеть детали и историю.</div>'; loadTickets(); });
document.querySelector('#refresh').addEventListener('click', loadTickets);

function escapeHtml(value) { const node = document.createElement('span'); node.textContent = String(value); return node.innerHTML; }
loadTickets();

