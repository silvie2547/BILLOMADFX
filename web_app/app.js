const $ = (selector, scope=document) => scope.querySelector(selector);
const $$ = (selector, scope=document) => [...scope.querySelectorAll(selector)];

// config.js sets window.BILLOMADFX_API_URL ('' means the API serves this UI
// from the same origin; a full URL is used when they are hosted apart).
const API_BASE = typeof window.BILLOMADFX_API_URL === 'string' ? window.BILLOMADFX_API_URL : '';
const TOKEN_KEY = 'billomadfx.access_token';
let currentUser = null;
let deferredInstallPrompt = null;

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
    // A rejected session token means the user must sign in again. Endpoints
    // that legitimately answer 401 (wrong 2FA code, wrong disable password)
    // pass allow401 and handle the error inline instead.
    if (response.status === 401 && token && !options.allow401) {
      localStorage.removeItem(TOKEN_KEY);
      showAuth();
    }
    const detail = body?.detail;
    let message;
    let code = null;
    if (typeof detail === 'string') message = detail;
    else if (Array.isArray(detail)) message = detail.map(item => item.msg).join(', ');
    else if (detail && typeof detail === 'object') { message = detail.message || 'Request failed'; code = detail.code || null; }
    else message = `Request failed (${response.status})`;
    const error = new Error(message);
    error.code = code;
    error.status = response.status;
    throw error;
  }
  return body;
}

const AUTH_VIEWS = ['login', 'register', 'otp', 'forgot', 'reset', 'twofa'];
let pendingEmail = null;      // address awaiting sign-up verification
let pendingChallenge = null;  // 2FA challenge token during sign-in
let resetEmail = null;        // address awaiting password reset

function showAuthView(name) {
  if (!AUTH_VIEWS.includes(name)) return;
  AUTH_VIEWS.forEach(view => {
    const element = $(`#${view}Form`);
    if (element) element.classList.toggle('active', view === name);
  });
  $('#authTabs')?.toggleAttribute('hidden', name !== 'login' && name !== 'register');
  $$('.auth-tabs button').forEach(item => item.classList.toggle('active', item.dataset.authTab === (name === 'register' ? 'register' : 'login')));
  if (name !== 'otp') {
    window.clearInterval(window.otpCountdownTimer);
    window.otpCountdownTimer = null;
  }
}

function showAuth() {
  const app = $('.app-shell');
  if (!app) return;
  app.classList.add('authenticated-hidden');
  $('#authOverlay')?.classList.add('show');
  const adminNav = $('.nav-item[data-page="admin"]');
  if (adminNav) adminNav.hidden = true;
  pendingChallenge = null;
  AUTH_VIEWS.forEach(view => setAuthStatus(`#${view}Status`, null));
  showAuthView('login');
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
  renderTwoFactorPanel();
}

// --- Two-step authentication (Account page) ----------------------------------

function renderTwoFactorPanel() {
  const enabled = Boolean(currentUser?.two_factor_enabled);
  const pill = $('#twofaStatusPill');
  if (pill) {
    pill.classList.toggle('positive', enabled);
    pill.classList.toggle('unavailable', !enabled);
  }
  setText('#twofaStatusLine', enabled ? 'Enabled — sign-in needs your authenticator code' : 'Not enabled');
  const toggle = (selector, show) => { const el = $(selector); if (el) el.hidden = !show; };
  toggle('#twofaEnableBlock', !enabled);
  toggle('#twofaDisableBlock', enabled);
  // Reset any in-progress setup UI when the state changes.
  toggle('#twofaSetupBlock', false);
  toggle('#twofaBackupBlock', false);
  setAuthStatus('#twofaSetupStatus', null);
}

async function handleTwoFactorStart() {
  const button = $('#twofaStartButton');
  button.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/2fa/setup', { method: 'POST', body: '{}' });
    $('#twofaQr').src = data.qr_data_uri;
    $('#twofaSecret').textContent = `Manual setup key: ${data.secret}`;
    $('#twofaCode').value = '';
    $('#twofaSetupBlock').hidden = false;
    $('#twofaSetupStatus').hidden = true;
    $('#twofaCode').focus();
  } catch (error) {
    toast('Setup failed', error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function handleTwoFactorConfirm() {
  const button = $('#twofaConfirmButton');
  button.disabled = true;
  setAuthStatus('#twofaSetupStatus', null);
  try {
    const data = await apiRequest('/api/v1/auth/2fa/confirm', {
      method: 'POST',
      body: JSON.stringify({ code: $('#twofaCode').value })
    });
    currentUser.two_factor_enabled = true;
    $('#twofaSetupBlock').hidden = true;
    const list = $('#twofaBackupCodes');
    list.replaceChildren();
    for (const code of data.backup_codes) {
      const item = document.createElement('code');
      item.textContent = code;
      list.append(item);
    }
    $('#twofaBackupBlock').hidden = false;
    renderTwoFactorPanel();
    toast('Two-step authentication on', data.message);
  } catch (error) {
    setAuthStatus('#twofaSetupStatus', error.message, true);
    toast('Not confirmed', error.message, 'error');
  } finally {
    button.disabled = false;
  }
}

async function handleTwoFactorDisable() {
  if (!window.confirm('Turn off two-step authentication? Sign-in will only need your email and password.')) return;
  const password = window.prompt('Confirm your account password to disable two-step authentication:');
  if (!password) return;
  setAuthStatus('#twofaDisableStatus', null);
  try {
    const data = await apiRequest('/api/v1/auth/2fa/disable', {
      method: 'POST',
      allow401: true,
      body: JSON.stringify({ password })
    });
    currentUser.two_factor_enabled = false;
    renderTwoFactorPanel();
    toast('Two-step authentication off', data.message);
  } catch (error) {
    setAuthStatus('#twofaDisableStatus', error.message, true);
    toast('Still enabled', error.message, 'error');
  }
}

$('#twofaStartButton')?.addEventListener('click', handleTwoFactorStart);
$('#twofaConfirmButton')?.addEventListener('click', handleTwoFactorConfirm);
$('#twofaDisableButton')?.addEventListener('click', handleTwoFactorDisable);

function setAuthStatus(selector, message, isError = false) {
  const element = $(selector);
  if (!element) return;
  element.hidden = message == null;
  element.textContent = message ?? '';
  element.classList.toggle('error', Boolean(isError));
}

// --- Session persistence -----------------------------------------------------
// The access token lives 30 days. Whenever fewer than 5 days remain, the app
// silently exchanges it for a fresh one (sliding session), so an account in
// regular use never asks for the password again. Signing out revokes the
// token on the server, not just in this browser.

const TOKEN_RENEW_THRESHOLD_MS = 5 * 24 * 60 * 60 * 1000;
let lastRenewCheck = 0;

function tokenPayload() {
  const token = localStorage.getItem(TOKEN_KEY);
  if (!token) return null;
  try {
    const json = atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'));
    const payload = JSON.parse(json);
    return Number.isFinite(payload.exp) ? payload : null;
  } catch (_) {
    return null;
  }
}

async function maybeRenewToken() {
  const payload = tokenPayload();
  if (!payload) return;
  const remaining = payload.exp * 1000 - Date.now();
  if (remaining > TOKEN_RENEW_THRESHOLD_MS) return;
  try {
    const data = await apiRequest('/api/v1/auth/refresh', { method: 'POST', body: '{}' });
    localStorage.setItem(TOKEN_KEY, data.access_token);
  } catch (_) { /* keep the current token; the next check retries */ }
}

function scheduleRenewalChecks() {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible' || !currentUser) return;
    const now = Date.now();
    if (now - lastRenewCheck < 5 * 60 * 1000) return;
    lastRenewCheck = now;
    void maybeRenewToken();
  });
  window.setInterval(() => {
    if (currentUser) void maybeRenewToken();
  }, 30 * 60 * 1000);
}

async function loadAuthenticatedData(knownUser = null) {
  try {
    const user = knownUser || await apiRequest('/api/v1/auth/me');
    showApp(user);
    const [dashboard, risk, mt5Status, mt5Account, mt5Positions, mt5Bars, marketCandles, adminAudit] = await Promise.all([
      apiRequest('/api/v1/dashboard'),
      apiRequest('/api/v1/risk'),
      apiRequest('/api/v1/mt5/status').catch(() => null),
      apiRequest('/api/v1/mt5/account').catch(() => null),
      apiRequest('/api/v1/mt5/positions').catch(() => null),
      apiRequest('/api/v1/mt5/status').then(status => status?.connected && status?.demo
        ? apiRequest('/api/v1/mt5/bars?timeframe=H1&count=100').catch(() => null)
        : null).catch(() => null),
      apiRequest('/api/v1/market/candles?timeframe=H1&count=100').catch(() => null),
      user.role === 'admin'
        ? apiRequest('/api/v1/admin/audit?limit=50').then(data => ({ data, error: null })).catch(error => ({ data: null, error }))
        : Promise.resolve({ data: null, error: null })
    ]);
    applyDashboard(dashboard, risk);
    applyMt5Status(mt5Status, mt5Account, mt5Positions, mt5Bars, marketCandles, dashboard.market || null);
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

function applyDashboard(dashboard, risk) {
  const quote = dashboard.market?.quote || {};
  const trend = dashboard.market?.trend || {};

  if (quote.available && quote.price != null) {
    const price = `$${Number(quote.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    setText('#spotPrice', price);
    setText('#spotQuote', price);
    setText('#spotSource', `Live · ${quote.source} · ${new Date(quote.updated_at).toLocaleTimeString()}`);
    setText('#marketDataStatus', 'Spot gold live');
    $('#marketDataStatus')?.closest('.market-status')?.classList.add('live');
  } else {
    setText('#spotPrice', '—');
    setText('#spotQuote', 'Unavailable');
    setText('#spotSource', quote.error || 'Live data unavailable');
    setText('#marketDataStatus', 'Live data unavailable');
  }

  const trendElement = $('#aiSignal');
  if (trend.available) {
    setText('#aiSignal', trend.trend);
    trendElement?.classList.remove('bearish', 'bullish', 'neutral');
    trendElement?.classList.add(String(trend.trend || 'neutral').toLowerCase());
    setText('#aiConfidence', `EMA/RSI · ${trend.timeframe || 'H1'}`);
    setText('#aiReason', trend.reason);
    setText('#ema20Value', trend.ema20 != null ? Number(trend.ema20).toFixed(2) : '—');
    setText('#ema50Value', trend.ema50 != null ? Number(trend.ema50).toFixed(2) : '—');
    setText('#rsi14Value', trend.rsi14 != null ? Number(trend.rsi14).toFixed(1) : '—');
    setText('#analysisStatus', trend.trend);
    const pill = $('#analysisStatus')?.closest('.status-pill');
    if (pill) {
      pill.classList.remove('unavailable');
      pill.classList.toggle('positive', trend.trend === 'BULLISH');
    }
  } else {
    setText('#aiSignal', '—');
    setText('#aiConfidence', 'Live indicators');
    setText('#aiReason', trend.reason || 'Live market data is unavailable right now.');
    setText('#ema20Value', '—');
    setText('#ema50Value', '—');
    setText('#rsi14Value', '—');
    setText('#analysisStatus', 'Unavailable');
    $('#analysisStatus')?.closest('.status-pill')?.classList.add('unavailable');
  }

  setText('#accountBalance', dashboard.account.balance == null ? 'Not connected' : `${dashboard.account.currency || ''} ${Number(dashboard.account.balance).toLocaleString()}`.trim());
  applyRiskSettings(risk);
}

function applyRiskSettings(risk) {
  setText('#riskHaltStatus', risk.is_halted ? 'Emergency halt flag set' : 'Halt flag not set');
  setText('#dailyLossLimit', `${risk.daily_loss_limit_pct}%`);
  setText('#weeklyLossLimit', `${risk.weekly_loss_limit_pct}%`);
  setText('#maxDrawdownLimit', `${risk.max_drawdown_pct}%`);
  setText('#maxSpreadLimit', `${risk.max_spread_points} points`);
  const values = {
    '#dailyLossInput': risk.daily_loss_limit_pct,
    '#weeklyLossInput': risk.weekly_loss_limit_pct,
    '#maxDrawdownInput': risk.max_drawdown_pct,
    '#maxSpreadInput': risk.max_spread_points
  };
  for (const [selector, value] of Object.entries(values)) {
    const input = $(selector);
    if (input) input.value = value;
  }
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
    chart.setAttribute('aria-label', 'No market data');
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
  chart.setAttribute('aria-label', `Last ${validBars.length} gold H1 candles`);
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

function applyMt5Status(status, account, mt5Positions, mt5Bars, marketCandles, market) {
  const connected = Boolean(status?.connected && status?.demo);
  const blockedRealAccount = Boolean(status?.connected && !status?.demo);
  const statusText = connected ? 'Connected' : blockedRealAccount ? 'Non-demo account blocked' : status?.error || 'Not connected';
  setText('#mt5AccountTitle', connected ? 'MT5 Demo Account' : 'MT5 terminal');
  setText('#mt5AccountLogin', connected ? `Account •••• ${status.login_last4 || '—'}` : 'Not connected');
  setText('#mt5Server', connected ? account?.server || status?.server || 'Unavailable' : 'Unavailable');
  setText('#mt5Balance', !connected || account?.balance == null ? 'No data' : `${account.currency || ''} ${Number(account.balance).toLocaleString()}`.trim());
  setText('#mt5Mode', connected ? 'DEMO' : blockedRealAccount ? 'Blocked' : status?.account_mode || 'Unavailable');
  setText('#mt5Algo', connected ? (status.trade_allowed && !status.tradeapi_disabled ? 'Enabled' : 'Disabled') : 'Unavailable');
  setText('#mt5ConnectionStatus', statusText);
  setText('#analysisStatus', market?.trend?.available ? market.trend.trend : 'Unavailable');

  // Candle source preference: the user's own MT5 terminal, else live Binance data.
  const candleSource = connected && mt5Bars?.items?.length ? 'mt5' : marketCandles?.available && marketCandles?.items?.length ? 'market' : 'none';
  const items = candleSource === 'mt5' ? mt5Bars.items : candleSource === 'market' ? marketCandles.items : [];
  setText('#marketDataStatus', candleSource === 'mt5' ? 'MT5 demo data connected' : candleSource === 'market' ? 'Live market data' : 'Live data unavailable');

  const latestBar = items.length ? items[items.length - 1] : null;
  const latestClose = Number(latestBar?.close);
  setText('#latestBarClose', Number.isFinite(latestClose) ? latestClose.toFixed(2) : 'Unavailable');
  const latestDate = latestBar?.time ? new Date(latestBar.time) : null;
  setText('#latestBarTime', latestDate && !Number.isNaN(latestDate.getTime()) ? latestDate.toLocaleString() : 'No market data');
  renderCandles(items);
  $('#marketChartMessage').textContent = candleSource === 'market'
    ? 'Live candles: PAXG/USDT (tokenized gold) from Binance.'
    : candleSource === 'mt5'
      ? 'Live candles from your connected MT5 terminal.'
      : (marketCandles?.error || 'Live market data is unavailable right now.');

  const statusElement = $('#mt5ConnectionStatus');
  if (statusElement) {
    statusElement.classList.toggle('positive', connected);
    statusElement.classList.toggle('unavailable', !connected);
  }

  if (connected && account?.balance != null) {
    setText('#accountBalance', `${account.currency || ''} ${Number(account.balance).toLocaleString()}`.trim());
  }

  if (connected && mt5Positions?.items) {
    setText('#openPositions', String(mt5Positions.count));
    setText('#positionExposure', mt5Positions.count ? `${mt5Positions.count} demo position${mt5Positions.count === 1 ? '' : 's'}` : 'No broker exposure');
    renderPositions(mt5Positions.items, 'No open demo positions');
  } else {
    setText('#openPositions', '—');
    setText('#positionExposure', blockedRealAccount ? 'Non-demo account blocked' : 'Connect an MT5 terminal for positions');
    renderPositions([], blockedRealAccount ? 'Positions blocked for non-demo accounts' : 'Connect an MT5 terminal for positions');
  }
}

function startOtpCountdown(minutes) {
  window.clearInterval(window.otpCountdownTimer);
  const deadline = Date.now() + minutes * 60 * 1000;
  const element = $('#otpCountdown');
  const tick = () => {
    const left = Math.max(0, Math.floor((deadline - Date.now()) / 1000));
    if (!element) return;
    if (left <= 0) {
      element.textContent = 'The code has expired — request a new one below.';
      window.clearInterval(window.otpCountdownTimer);
      window.otpCountdownTimer = null;
      return;
    }
    element.textContent = `Code expires in ${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
  };
  tick();
  window.otpCountdownTimer = window.setInterval(tick, 1000);
}

function showDeliveredCode(codeElementId, delivery, otp) {
  // Display mode: this deployment has no SMTP configured, so the API hands
  // the code to the client. Clearly labeled so nobody mistakes it for an email.
  const element = $(codeElementId);
  if (!element) return;
  if (delivery === 'display' && otp) {
    element.hidden = false;
    element.textContent = `Email delivery is not configured on this deployment — your one-time code is ${otp}`;
  } else {
    element.hidden = true;
    element.textContent = '';
  }
}

function enterOtpView(data) {
  pendingEmail = data.email || pendingEmail;
  $('#otpMessage').textContent = data.message || `We sent a verification code to ${pendingEmail}.`;
  showDeliveredCode('#otpDisplay', data.delivery, data.otp);
  $('#otpCode').value = data.delivery === 'display' && data.otp ? data.otp : '';
  $('#otpCode').focus();
  startOtpCountdown(data.expires_in_minutes || 20);
  setAuthStatus('#otpStatus', null);
  showAuthView('otp');
}

function enterResetView(email, data) {
  resetEmail = email;
  $('#resetMessage').textContent = data?.message || 'Enter the reset code and choose a new password.';
  showDeliveredCode('#resetDisplay', data?.delivery, data?.otp);
  $('#resetCode').value = data?.delivery === 'display' && data?.otp ? data.otp : '';
  $('#resetPassword').value = '';
  $('#resetPasswordConfirm').value = '';
  updatePasswordChecklist('#resetRequirements', '#resetPassword');
  setAuthStatus('#resetStatus', null);
  showAuthView('reset');
  $('#resetCode').focus();
}

async function handleLogin(event) {
  event.preventDefault();
  const submit = $('#loginSubmit');
  submit.disabled = true;
  setAuthStatus('#loginStatus', null);
  try {
    const data = await apiRequest('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: $('#loginEmail').value, password: $('#loginPassword').value })
    });
    if (data.totp_required) {
      // Two-step authentication: the password was accepted; ask for the code.
      pendingChallenge = data.challenge_token;
      $('#twofaEmail').textContent = $('#loginEmail').value;
      setAuthStatus('#twofaStatus', null);
      showAuthView('twofa');
      $('#twofaCode').focus();
      return;
    }
    localStorage.setItem(TOKEN_KEY, data.access_token);
    showApp(data.user);
    const refreshed = await loadAuthenticatedData(data.user);
    if (refreshed) toast('Welcome back', `Signed in as ${data.user.display_name}`);
  } catch (error) {
    if (error.code === 'email_not_verified') {
      // Right password, unverified address: continue the sign-up verification.
      setAuthStatus('#otpStatus', null);
      enterOtpView({ email: $('#loginEmail').value, message: error.message });
      return;
    }
    setAuthStatus('#loginStatus', error.message, true);
    toast('Sign-in failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

function updatePasswordChecklist(listSelector, inputSelector) {
  const value = $(inputSelector).value;
  const rules = {
    length: value.length >= 12,
    upper: /[A-Z]/.test(value),
    lower: /[a-z]/.test(value),
    digit: /\d/.test(value)
  };
  $$(`${listSelector} li`).forEach(item => item.classList.toggle('ok', Boolean(rules[item.dataset.rule])));
}

async function handleRegister(event) {
  event.preventDefault();
  const submit = $('#registerSubmit');
  const password = $('#registerPassword').value;
  setAuthStatus('#registerStatus', null);
  if (password !== $('#registerPasswordConfirm').value) {
    const message = 'Passwords do not match. Re-enter the same password in both fields.';
    setAuthStatus('#registerStatus', message, true);
    toast('Registration failed', message, 'error');
    return;
  }
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email: $('#registerEmail').value,
        password,
        display_name: $('#registerName').value
      })
    });
    // A one-time code is now on its way; the account activates after it is
    // confirmed (valid for 20 minutes).
    enterOtpView(data);
    toast('Almost there', 'Enter the verification code to activate your account.');
  } catch (error) {
    setAuthStatus('#registerStatus', error.message, true);
    toast('Registration failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function handleVerifyOtp(event) {
  event.preventDefault();
  const submit = $('#otpSubmit');
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/verify-otp', {
      method: 'POST',
      body: JSON.stringify({ email: pendingEmail, code: $('#otpCode').value })
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    pendingEmail = null;
    showApp(data.user);
    const refreshed = await loadAuthenticatedData(data.user);
    if (refreshed) toast('Email verified', `Welcome, ${data.user.display_name}`);
  } catch (error) {
    setAuthStatus('#otpStatus', error.message, true);
    toast('Verification failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

function startResendCooldown(seconds = 60) {
  const button = $('#otpResend');
  if (!button) return;
  button.disabled = true;
  window.clearInterval(window.resendCooldownTimer);
  let remaining = seconds;
  const tick = () => {
    if (remaining <= 0) {
      button.disabled = false;
      button.textContent = 'Resend code';
      window.clearInterval(window.resendCooldownTimer);
      return;
    }
    button.textContent = `Resend available in ${remaining}s`;
    remaining -= 1;
  };
  tick();
  window.resendCooldownTimer = window.setInterval(tick, 1000);
}

async function handleResendOtp() {
  if (!pendingEmail) return;
  try {
    const data = await apiRequest('/api/v1/auth/resend-otp', {
      method: 'POST',
      body: JSON.stringify({ email: pendingEmail })
    });
    if (data.resent === false) {
      setAuthStatus('#otpStatus', data.message, true);
      startResendCooldown();
      return;
    }
    enterOtpView(data);
    startResendCooldown();
    toast('Code re-sent', data.message);
  } catch (error) {
    setAuthStatus('#otpStatus', error.message, true);
    startResendCooldown();
    toast('Could not re-send', error.message, 'error');
  }
}

async function handleForgotPassword(event) {
  event.preventDefault();
  const submit = $('#forgotSubmit');
  submit.disabled = true;
  setAuthStatus('#forgotStatus', null);
  try {
    const email = $('#forgotEmail').value;
    const data = await apiRequest('/api/v1/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
    enterResetView(email, data);
  } catch (error) {
    setAuthStatus('#forgotStatus', error.message, true);
    toast('Reset failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function handleResetPassword(event) {
  event.preventDefault();
  const submit = $('#resetSubmit');
  const password = $('#resetPassword').value;
  setAuthStatus('#resetStatus', null);
  if (password !== $('#resetPasswordConfirm').value) {
    setAuthStatus('#resetStatus', 'Passwords do not match.', true);
    return;
  }
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ email: resetEmail, code: $('#resetCode').value, new_password: password })
    });
    toast('Password updated', data.message);
    showAuthView('login');
    setAuthStatus('#loginStatus', 'Your password is updated — sign in with the new one.');
    $('#loginEmail').value = resetEmail || '';
    $('#loginPassword').value = '';
    $('#loginPassword').focus();
  } catch (error) {
    setAuthStatus('#resetStatus', error.message, true);
    toast('Reset failed', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
}

async function handleTwoFactorChallenge(event) {
  event.preventDefault();
  const submit = $('#twofaSubmit');
  submit.disabled = true;
  setAuthStatus('#twofaStatus', null);
  try {
    const data = await apiRequest('/api/v1/auth/login/2fa', {
      method: 'POST',
      allow401: true,
      body: JSON.stringify({ challenge_token: pendingChallenge, code: $('#twofaCode').value })
    });
    localStorage.setItem(TOKEN_KEY, data.access_token);
    pendingChallenge = null;
    showApp(data.user);
    const refreshed = await loadAuthenticatedData(data.user);
    if (refreshed) toast('Welcome back', `Signed in as ${data.user.display_name}`);
  } catch (error) {
    setAuthStatus('#twofaStatus', error.message, true);
  } finally {
    submit.disabled = false;
  }
}

$('#loginForm')?.addEventListener('submit', handleLogin);
$('#registerForm')?.addEventListener('submit', handleRegister);
$('#registerPassword')?.addEventListener('input', () => updatePasswordChecklist('#passwordRequirements', '#registerPassword'));
$('#resetPassword')?.addEventListener('input', () => updatePasswordChecklist('#resetRequirements', '#resetPassword'));
$('#otpForm')?.addEventListener('submit', handleVerifyOtp);
$('#otpResend')?.addEventListener('click', handleResendOtp);
$('#forgotForm')?.addEventListener('submit', handleForgotPassword);
$('#resetForm')?.addEventListener('submit', handleResetPassword);
$('#twofaForm')?.addEventListener('submit', handleTwoFactorChallenge);

$$('[data-auth-view]').forEach(button => button.addEventListener('click', () => {
  if (button.dataset.authView === 'forgot' && !$('#forgotEmail').value) {
    $('#forgotEmail').value = $('#loginEmail').value || '';
  }
  if (button.dataset.authView === 'login') {
    pendingChallenge = null;
    pendingEmail = null;
  }
  showAuthView(button.dataset.authView);
}));

$('#riskSettingsForm')?.addEventListener('submit', async event => {
  event.preventDefault();
  const submit = $('#saveRiskSettings');
  submit.disabled = true;
  try {
    const data = await apiRequest('/api/v1/risk', {
      method: 'PUT',
      body: JSON.stringify({
        daily_loss_limit_pct: Number($('#dailyLossInput').value),
        weekly_loss_limit_pct: Number($('#weeklyLossInput').value),
        max_drawdown_pct: Number($('#maxDrawdownInput').value),
        max_spread_points: Number($('#maxSpreadInput').value)
      })
    });
    applyRiskSettings(data);
    setText('#riskSettingsStatus', 'Saved. These limits are not enforced against orders in this release.');
    toast('Risk limits saved', 'Settings are stored for this account; order execution remains disabled.');
  } catch (error) {
    setText('#riskSettingsStatus', error.message);
    toast('Risk settings not saved', error.message, 'error');
  } finally {
    submit.disabled = false;
  }
});

$$('[data-auth-tab]').forEach(button => button.addEventListener('click', () => {
  $$('[data-auth-tab]').forEach(item => item.classList.toggle('active', item === button));
  $('#loginForm')?.classList.toggle('active', button.dataset.authTab === 'login');
  $('#registerForm')?.classList.toggle('active', button.dataset.authTab === 'register');
}));

$('#logoutButton')?.addEventListener('click', async () => {
  // Revoke the session on the server first (invalidates the token on every
  // device), then always end the local session — even if the API is offline.
  try {
    await apiRequest('/api/v1/auth/logout', { method: 'POST', body: '{}' });
  } catch (_) { /* network failure must not trap the user in the app */ }
  localStorage.removeItem(TOKEN_KEY);
  currentUser = null;
  showAuth();
  toast('Signed out', 'Your session has ended on this device and on the server');
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

// Install prompt (Chromium: Android/desktop). On iOS, users install via
// Share -> "Add to Home Screen" (see README).
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault();
  deferredInstallPrompt = event;
  const installButton = $('#installButton');
  if (installButton) installButton.hidden = false;
});

$('#installButton')?.addEventListener('click', async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  const choice = await deferredInstallPrompt.userChoice;
  if (choice.outcome === 'accepted') toast('Installed', 'BILLOMADFX was added to this device.');
  deferredInstallPrompt = null;
  $('#installButton').hidden = true;
});

if ('serviceWorker' in navigator && /^https?:$/.test(location.protocol)) {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}

async function loadAppVersion() {
  try {
    const response = await fetch(`${API_BASE}/api/v1/meta`);
    if (!response.ok) return;
    const meta = await response.json();
    setText('#appVersion', `BILLOMADFX v${meta.version}`);
  } catch (_) { /* offline shell still works */ }
}

window.addEventListener('load', () => {
  drawChart('1M');
  void loadAppVersion();
  scheduleRenewalChecks();
  // The auth screen is visible by default; restore the session only when a
  // token is stored. Until /me answers, no app content is shown at all.
  if (localStorage.getItem(TOKEN_KEY)) {
    setAuthStatus('#loginStatus', 'Restoring your session…');
    void loadAuthenticatedData()
      .then(() => { if (currentUser) void maybeRenewToken(); })
      .catch(error => setAuthStatus('#loginStatus', error.message, true));
  }
});
