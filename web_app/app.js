const $ = (selector, scope=document) => scope.querySelector(selector);
const $$ = (selector, scope=document) => [...scope.querySelectorAll(selector)];

function showPage(pageId) {
  $$('.page').forEach(page => page.classList.toggle('active', page.id === pageId));
  $$('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.page === pageId));
  $('#sidebar').classList.remove('open');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

$$('.nav-item').forEach(item => item.addEventListener('click', () => showPage(item.dataset.page)));
$$('[data-page-link]').forEach(button => button.addEventListener('click', () => showPage(button.dataset.pageLink)));
$('#mobileMenu').addEventListener('click', () => $('#sidebar').classList.toggle('open'));

function toast(title, message) {
  $('#toastTitle').textContent = title;
  $('#toastMessage').textContent = message;
  $('#toast').classList.add('show');
  window.clearTimeout(window.toastTimer);
  window.toastTimer = window.setTimeout(() => $('#toast').classList.remove('show'), 3200);
}

$('#themeButton').addEventListener('click', () => {
  document.body.classList.toggle('light');
  toast('Appearance changed', document.body.classList.contains('light') ? 'Light theme enabled.' : 'Dark theme enabled.');
  drawChart(currentPeriod);
});

$('#refreshButton').addEventListener('click', () => {
  $('.last-update').textContent = 'Updated just now';
  toast('Dashboard refreshed', 'Demo market data is up to date.');
});
$('#notificationButton').addEventListener('click', () => toast('Notifications', '3 trading alerts are available.'));
$('#disconnectButton').addEventListener('click', () => toast('Connection protected', 'Account disconnection requires confirmation in the backend.'));
$('#emergencyButton').addEventListener('click', () => toast('Safety control', 'Emergency shutdown requires authentication and confirmation.'));

$$('.period-picker button').forEach(button => button.addEventListener('click', () => {
  $$('.period-picker button').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  drawChart(button.dataset.period);
}));

const chartCanvas = $('#performanceChart');
let currentPeriod = '1M';

function drawChart(period='1M') {
  currentPeriod = period;
  const rect = chartCanvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  chartCanvas.width = rect.width * dpr;
  chartCanvas.height = rect.height * dpr;
  const ctx = chartCanvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const width = rect.width;
  const height = rect.height;
  const datasets = {
    '7D':[22500,22740,22680,23020,22940,23320,23810,24020,23900,24420,24610,25840],
    '1M':[22300,22520,22410,23040,22880,23310,23160,23640,24020,23880,24520,24910,24740,25220,25480,25840],
    '3M':[20100,20820,20460,21240,21680,21420,22140,22810,22580,23240,23820,24120,24860,25240,25840],
    '1Y':[16800,17620,17240,18420,18160,19240,20120,19880,21340,22020,22680,23420,24010,25840]
  };
  const values = datasets[period] || datasets['1M'];
  ctx.clearRect(0,0,width,height);
  ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--line').trim() || '#202632';
  ctx.lineWidth = 1;
  for(let i=0;i<5;i++){
    const y=10+i*((height-30)/4);
    ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(width,y);ctx.stroke();
  }
  const min=Math.min(...values)*.98,max=Math.max(...values)*1.01;
  const points=values.map((value,index)=>({x:index/(values.length-1)*width,y:height-20-(value-min)/(max-min)*(height-40)}));
  const gradient=ctx.createLinearGradient(0,0,0,height);
  gradient.addColorStop(0,'rgba(217,178,95,.28)');gradient.addColorStop(1,'rgba(217,178,95,0)');
  ctx.beginPath();ctx.moveTo(points[0].x,height-20);points.forEach(point=>ctx.lineTo(point.x,point.y));ctx.lineTo(width,height-20);ctx.closePath();ctx.fillStyle=gradient;ctx.fill();
  ctx.beginPath();points.forEach((point,index)=>index?ctx.lineTo(point.x,point.y):ctx.moveTo(point.x,point.y));ctx.strokeStyle='#d9b25f';ctx.lineWidth=2;ctx.stroke();
  const last=points[points.length-1];ctx.beginPath();ctx.arc(last.x,last.y,4,0,Math.PI*2);ctx.fillStyle='#d9b25f';ctx.fill();
}

window.addEventListener('resize', () => drawChart(currentPeriod));
window.addEventListener('load', () => drawChart('1M'));
