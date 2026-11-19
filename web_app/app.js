const $ = (selector, scope=document) => scope.querySelector(selector);
const $$ = (selector, scope=document) => [...scope.querySelectorAll(selector)];

const API_BASE = window.BILLOMADFX_API_URL || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'billomadfx.access_token';
let currentUser = null;

function showPage(pageId) {
  if (pageId === 'admin' && currentUser?.role !== 'admin') return;
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
  const adminNav = $('.nav-item[data-page="admin"]');
  if (adminNav) adminNav.hidden = true;
}

function showApp(user) {
  currentUser = user;
  $('.app-shell')?.classList.remove('authenticated-hidden');
  $('#authOverlay')?.classList.remove('show');
  const greeting = $('#greetingName');
  if (greeting) greeting.textContent = `Welcome, ${user.display_name}`;
  const profileName = $('#profileName');
  if (profileName) profileName.textContent = user.display_name;
  const profileRole = $('#profileRole');
  if (profileRole) profileRole.textContent = user.role === 'admin' ? 'Administrator' : 'User';
  const adminNav = $('.nav-item[data-page="admin"]');
  if (adminNav) adminNav.hidden = user.role !== 'admin';
  const initials = user.display_name.split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase();
  const avatar = $('.profile .avatar');
  if (avatar) avatar.textContent = initials;
}

async function loadAuthenticatedData() {
  try {
    const user = await apiRequest('/api/v1/auth/me');
    const [dashboard, risk, signal, mt5Status, mt5Account, mt5Positions, mt5Bars, adminAudit] = await Promise.all([
      apiRequest('/api/v1/dashboard'),
      apiRequest('/api/v1/risk'),
      apiRequest('/api/v1/market/signal'),
      apiRequest('/api/v1/mt5/status').catch(() => null),
      apiRequest('/api/v1/mt5/account').catch(() => null),
      apiRequest('/api/v1/mt5/positions').catch(() => null),
      apiRequest('/api/v1/mt5/bars?timeframe=H1&count=100').catch(() => null),
      user.role === 'admin'
        ? apiRequest('/api/v1/admin/audit?limit=50').then(data => ({ data, error: null })).catch(error => ({ data: null, error }))
        : Promise.resolve({ data: null, error: null })
    ]);
    showApp(user);
    applyDashboard(dashboard, risk, signal);
    applyMt5Status(mt5Status, mt5Account, mt5Positions, mt5Bars);
    applyAdminAudit(user, adminAudit);
    return true;
  } catch (error) {
    toast('Dashboard unavailable', error.message, 'error');
    return false;
  }
}

function setText(selector, value) {
  const element = $(selector);
  if (element) element.textContent = value;
}

function applyDashboard(dashboard, risk, signal) {
  setText('#accountBalance', dashboard.account.balance == null ? 'Not connected' : `$${Number(dashboard.account.balance).toLocaleString()}`);
  setText('#todayProfit', dashboard.trading.today_profit == null ? 'No data' : `$${Number(dashboard.trading.today_profit).toLocaleString()}`);
  setText('#aiSignal', signal.action);
  setText('#aiConfidence', signal.confidence == null ? 'Awaiting validated model' : `${signal.confidence}% confidence`);
  setText('#aiReason', signal.reason);
  setText('#riskHaltStatus', risk.is_halted ? 'Emergency halt flag set' : 'Halt flag not set');
  setText('#dailyLossLimit', `${risk.daily_loss_limit_pct}%`);
  setText('#weeklyLossLimit', `${risk.weekly_loss_limit_pct}%`);
  setText('#maxDrawdownLimit', `${risk.max_drawdown_pct}%`);
  setText('#maxSpreadLimit', `${risk.max_spread_points} points`);
}

function renderPositions(items, emptyMessage) {
  const tableBody = $('#positionsTableBody');
  if (!tableBody) return;
  tableBody.replaceChildren();

  if (!items.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'empty-table';
    cell.textContent = emptyMessage;
    row.append(cell);
    tableBody.append(row);
    return;
  }

  for (const position of items) {
    const row = document.createElement('tr');
    const values = [
      position.symbol,
      position.type,
      position.volume,
      position.entry,
      position.current,
      position.profit
    ];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      if (index === 0) {
        const icon = document.createElement('span');
        icon.className = 'symbol-icon';
        icon.textContent = 'AU';
        const symbol = document.createElement('strong');
        symbol.textContent = value ?? '—';
        cell.append(icon, symbol);
      } else {
        cell.textContent = value ?? '—';
      }
      row.append(cell);
    });
    tableBody.append(row);
  }
}

function renderCandles(bars) {
  const chart = $('#mt5Candles');
  const message = $('#marketChartMessage');
  if (!chart || !message) return;
  chart.replaceChildren();

  const validBars = (bars || []).filter(bar =>
    Number.isFinite(Number(bar.open)) &&
    Number.isFinite(Number(bar.high)) &&
    Number.isFinite(Number(bar.low)) &&
    Number.isFinite(Number(bar.close)) &&
    Number(bar.high) >= Number(bar.low)
  ).slice(-60);
  if (!validBars.length) {
    chart.setAttribute('aria-label', 'No demo market data');
    message.hidden = false;
    return;
  }

  message.hidden = true;
  const low = Math.min(...validBars.map(bar => Number(bar.low)));
  const high = Math.max(...validBars.map(bar => Number(bar.high)));
  const range = high - low || 1;
  const y = price => ((high - price) / range) * 100;

  for (const bar of validBars) {
    const open = Number(bar.open);
    const close = Number(bar.close);
    const barHigh = Number(bar.high);
    const barLow = Number(bar.low);
    const candle = document.createElement('i');
    candle.className = close >= open ? 'up' : 'down';
    candle.style.setProperty('--wick-top', `${y(barHigh)}%`);
    candle.style.setProperty('--wick-height', `${Math.max(0, y(barLow) - y(barHigh))}%`);
    candle.style.setProperty('--body-top', `${y(Math.max(open, close))}%`);
    candle.style.setProperty('--body-height', `${Math.abs(y(open) - y(close))}%`);
    chart.append(candle);
  }
  chart.setAttribute('aria-label', `Last ${validBars.length} XAUUSD H1 demo candles`);
}

function applyAdminAudit(user, result) {
  const message = $('#adminAuditMessage');
  const container = $('#adminAuditLog');
  if (!message || !container) return;
  container.replaceChildren();
  if (user.role !== 'admin') {
    message.textContent = 'Administrator access is required.';
    return;
  }
  if (result.error) {
    message.textContent = `Could not load the audit log: ${result.error.message}`;
    return;
  }

  const items = result.data?.items || [];
  message.textContent = items.length ? `${items.length} most recent audit events` : 'No audit events recorded.';
  for (const item of items) {
    const row = document.createElement('div');
    row.className = 'audit-row';
    const icon = document.createElement('span');
    icon.textContent = '•';
    const details = document.createElement('div');
    const eventType = document.createElement('strong');
    eventType.textContent = String(item.event_type || 'event').replaceAll('.', ' ');
    const detail = document.createElement('p');
    detail.textContent = item.detail || 'No additional details';
    details.append(eventType, detail);
    const time = document.createElement('time');
    const createdAt = item.created_at ? new Date(item.created_at) : null;
    time.textContent = createdAt && !Number.isNaN(createdAt.getTime()) ? createdAt.toLocaleString() : 'Time unavailable';
    row.append(icon, details, time);
    container.append(row);
  }
}

function applyMt5Status(status, account, mt5Positions, mt5Bars) {
  const connected = Boolean(status?.connected && status?.demo);
  const blockedRealAccount = Boolean(status?.connected && !status?.demo);
  const statusText = connected ? 'Connected' : blockedRealAccount ? 'Non-demo account blocked' : status?.error || 'Not connected';
  setText('#mt5AccountTitle', connected ? 'MT5 Demo Account' : 'MT5 demo account');
  setText('#mt5AccountLogin', connected ? `Account •••• ${status.login_last4 || '—'}` : 'Not connected');
  setText('#mt5Server', connected ? account?.server || status?.server || 'Unavailable' : 'Unavailable');
  setText('#mt5Balance', !connected || account?.balance == null ? 'No data' : `${account.currency || ''} ${Number(account.balance).toLocaleString()}`.trim());
  setText('#mt5Mode', connected ? 'DEMO' : blockedRealAccount ? 'Blocked' : status?.account_mode || 'Unavailable');
  setText('#mt5Algo', connected ? (status.trade_allowed && !status.tradeapi_disabled ? 'Enabled' : 'Disabled') : 'Unavailable');
  setText('#mt5ConnectionStatus', statusText);
  setText('#marketDataStatus', connected && mt5Bars?.items?.length ? 'Demo market data connected' : 'Market data unavailable');
  setText('#analysisStatus', 'No validated strategy');
  const latestBar = connected && mt5Bars?.items?.length ? mt5Bars.items[mt5Bars.items.length - 1] : null;
  const latestClose = Number(latestBar?.close);
  setText('#latestBarClose', Number.isFinite(latestClose) ? latestClose.toFixed(2) : 'Unavailable');
  const latestDate = latestBar?.time ? new Date(latestBar.time) : null;
  setText('#latestBarTime', latestDate && !Number.isNaN(latestDate.getTime()) ? latestDate.toLocaleString() : 'No market data');
  renderCandles(connected ? mt5Bars?.items : []);

  const statusElement = $('#mt5ConnectionStatus');
  if (statusElement) {
    statusElement.classList.toggle('positive', connected);
    statusElement.classList.toggle('unavailable', !connected);
  }
  const analysisStatus = $('#analysisStatus')?.closest('.status-pill');
  if (analysisStatus) analysisStatus.classList.add('unavailable');

  if (connected && account?.balance != null) {
    setText('#accountBalance', `${account.currency || ''} ${Number(account.balance).toLocaleString()}`.trim());
  }

  if (connected && mt5Positions?.items) {
    setText('#openPositions', String(mt5Positions.count));
    setText('#positionExposure', mt5Positions.count ? `${mt5Positions.count} demo position${mt5Positions.count === 1 ? '' : 's'}` : 'No broker exposure');
    renderPositions(mt5Positions.items, 'No open demo positions');
  } else {
    setText('#openPositions', '—');
    setText('#positionExposure', blockedRealAccount ? 'Non-demo account blocked' : 'Broker data unavailable');
    renderPositions([], blockedRealAccount ? 'Positions blocked for non-demo accounts' : 'Broker data unavailable');
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const submit = $('#loginSubmit');
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: $('#loginEmail').value, password: $('#loginPassword').value })
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    showApp(data.user);
    const refreshed = await loadAuthenticatedData();
    if (refreshed) toast('Welcome back', `Signed in as ${data.user.display_name}`);
  } catch (error) {
    toast('Sign-in failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function handleRegister(event) {
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
    const refreshed = await loadAuthenticatedData();
    if (refreshed) toast('Account created', `Welcome, ${data.user.display_name}`);
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
  const refreshed = await loadAuthenticatedData();
  if (refreshed) {
    toast('Dashboard refreshed', 'API data is up to date.');
  }
});

$('#notificationButton')?.addEventListener('click', () => toast('Notifications', 'No validated trading alerts are available.'));
$('#emergencyButton')?.addEventListener('click', async () => {
  if (!window.confirm('Record the emergency halt flag for this account? It cannot manage broker orders in this release.')) return;
  try {
    const response = await apiRequest('/api/v1/risk/emergency-stop', { method: 'POST', body: '{}' });
    setText('#riskHaltStatus', 'Emergency halt flag set');
    toast('Emergency halt flag recorded', response.message);
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
  if (localStorage.getItem(TOKEN_KEY)) void loadAuthenticatedData();
  else showAuth();
});
