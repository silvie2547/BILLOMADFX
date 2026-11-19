const $ = (selector, scope=document) => scope.querySelector(selector);
const $$ = (selector, scope=document) => [...scope.querySelectorAll(selector)];

const API_BASE = window.BILLOMADFX_API_URL || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'billomadfx.access_token';
let currentUser = null;

function showPage(pageId) {
  $$('.page').forEach(page => page.classList.toggle('active', page.id === pageId));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.page === pageId));
  $('#sidebar')?.classList.remove('open');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

$$('.nav-item').forEach(item => item.addEventListener('click', () => showPage(item.dataset.page)));
$$('[data-page-link]').forEach(button => button.addEventListener('click', () => showPage(button.dataset.pageLink)));
$('#mobileMenu')?.addEventListener('click', () => $('#sidebar').classList.toggle('open'));

function toast(title, message, kind='success') {
  const toastElement = $('#toast');
  $('#toastTitle').textContent = title;
  $('#toastMessage').textContent = message;
  $('#toastIcon').textContent = kind === 'error' ? '!' : '✓';
  toastElement.classList.add('show');
  window.clearTimeout(window.toastTimer);
  window.toastTimer = window.setTimeout(() => toastElement.classList.remove('show'), 3200);
}

async function apiRequest(path, options={}) {
  const token = localStorage.getItem(TOKEN_KEY);
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  let body = null;
  try { body = await response.json(); } catch (_) {}
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem(TOKEN_KEY);
      showAuth();
    }
    const detail = body?.detail;
    throw new Error(Array.isArray(detail) ? detail.map(item => item.msg).join(', ') : detail || `Request failed (${response.status})`);
  }
  return body;
}

function showAuth() {
  const app = $('.app-shell');
  if (!app) return;
  app.classList.add('authenticated-hidden');
  $('#authOverlay')?.classList.add('show');
}

function showApp(user) {
  currentUser = user;
  $('.app-shell')?.classList.remove('authenticated-hidden');
  $('#authOverlay')?.classList.remove('show');
  const greeting = $('#greetingName');
  if (greeting) greeting.textContent = user.display_name;
  const profileName = $('#profileName');
  if (profileName) profileName.textContent = user.display_name;
  const initials = user.display_name.split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
  const avatar = $('.profile .avatar');
  if (avatar) avatar.textContent = initials;
}

async function loadAuthenticatedData() {
  try {
    const [user, dashboard, risk, positions, signal] = await Promise.all([
      apiRequest('/api/v1/auth/me'),
      apiRequest('/api/v1/dashboard'),
      apiRequest('/api/v1/risk'),
      apiRequest('/api/v1/trading/positions'),
      apiRequest('/api/v1/market/signal')
    ]);
    showApp(user);
    applyDashboard(dashboard, risk, positions, signal);
  } catch (error) {
    localStorage.removeItem(TOKEN_KEY);
    showAuth();
  }
}

function setText(selector, value) {
  const element = $(selector);
  if (element) element.textContent = value;
}

function applyDashboard(dashboard, risk, positions, signal) {
  setText('#accountBalance', dashboard.account.balance == null ? 'Not connected' : `$${Number(dashboard.account.balance).toLocaleString()}`);
  setText('#todayProfit', dashboard.trading.today_profit == null ? 'No data' : `$${Number(dashboard.trading.today_profit).toLocaleString()}`);
  setText('#openPositions', String(positions.count));
  setText('#aiSignal', signal.action);
  setText('#aiConfidence', signal.confidence == null ? 'Awaiting validated model' : `${signal.confidence}% confidence`);
  setText('#aiReason', signal.reason);
  setText('#riskHaltStatus', risk.is_halted ? 'Trading halted' : 'Capital protection active');

  const tableBody = $('#positionsTableBody');
  if (tableBody) {
    tableBody.innerHTML = positions.items.length ? positions.items.map(position => `
      <tr><td><span class="symbol-icon">AU</span><strong>${position.symbol}</strong></td>
      <td>${position.type || '—'}</td><td>${position.volume || '—'}</td><td>${position.entry || '—'}</td>
      <td>${position.current || '—'}</td><td>${position.profit || '—'}</td></tr>`).join('') :
      '<tr><td colspan="6" class="empty-table">No open positions · Broker data unavailable</td></tr>';
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submit = $('#loginSubmit');
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: $('#loginEmail').value, password: $('#loginPassword').value })
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    showApp(data.user);
    await loadAuthenticatedData();
    toast('Welcome back', `Signed in as ${data.user.display_name}`);
  } catch (error) {
    toast('Sign-in failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function handleRegister(event) {
  event.preventEvent?.();
  event.preventDefault();
  const submit = $('#registerSubmit');
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#registerEmail').value,
        password: $('#registerPassword').value,
        display_name: $('#registerName').value
      })
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    showApp(data.user);
    await loadAuthenticatedData();
    toast('Account created', `Welcome, ${data.user.display_name}`);
  } catch (error) {
    toast('Registration failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

$('#loginForm')?.addEventListener('submit', handleLogin);
$('#registerForm')?.addEventListener('submit', handleRegister);

$$('[data-auth-tab]').forEach(button => button.addEventListener('click', () => {
  $$('[data-auth-tab]').forEach(item => item.classList.toggle('active', item === button));
  $('#loginForm')?.classList.toggle('active', button.dataset.authTab === 'login');
  $('#registerForm')?.classList.toggle('active', button.dataset.authTab === 'register');
}));

$('#logoutButton')?.addEventListener('click', () => {
  localStorage.removeItem(TOKEN_KEY);
  currentUser = null;
  showAuth();
  toast('Signed out', 'Your session has ended');
});

$('#themeButton')?.addEventListener('click', () => {
  document.body.classList.toggle('light');
  toast('Appearance changed', document.body.classList.contains('light') ? 'Light theme enabled.' : 'Dark theme enabled.');
  drawChart(currentPeriod);
});

$('#refreshButton')?.addEventListener('click', async () => {
  try {
    await loadAuthenticatedData();
    toast('Dashboard refreshed', 'API data is up to date.');
  } catch (error) {
    toast('Refresh failed', error.message, 'error');
  }
});

$('#notificationButton')?.addEventListener('click', () => toast('Notifications', 'No validated trading alerts are available.'));
$('#disconnectButton')?.addEventListener('click', () => toast('Account connection', 'MT5 broker integration is not configured.'));

$('#emergencyButton')?.addEventListener('click', async () => {
  if (!window.confirm('Activate the emergency trading halt for this account?')) return;
  try {
    const response = await apiRequest('/api/v1/risk/emergency-stop', { method: 'POST', body: '{}' });
    setText('#riskHaltStatus', 'Trading halted');
    toast('Emergency halt activated', response.message);
  } catch (error) {
    toast('Halt failed', error.message, 'error');
  }
});

$$('.period-picker button').forEach(button => button.addEventListener('click', () => {
  $$('.period-picker button').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  drawChart(button.dataset.period);
}));

const chartCanvas = $('#performanceChart');
let currentPeriod = '1M';

function drawChart(period='1M') {
  if (!chartCanvas) return;
  currentPeriod = period;
  const rect = chartCanvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = window.devicePixelRatio || 1;
  chartCanvas.width = rect.width * dpr;
  chartCanvas.height = rect.height * dpr;
  const ctx = chartCanvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--line').trim() || '#202632';
  ctx.lineWidth = 1;
  for (let i = 0; i < 5; i++) {
    const y = 10 + i * ((rect.height - 30) / 4);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(rect.width, y); ctx.stroke();
  }
}

window.addEventListener('resize', () => drawChart(currentPeriod));
window.addEventListener('load', () => {
  drawChart('1M');
  if (localStorage.getItem(TOKEN_KEY)) loadAuthenticatedData();
  else showAuth();
});
