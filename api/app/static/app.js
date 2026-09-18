const appId = location.pathname.split('/').filter(Boolean).pop()?.startsWith('display-app-')
  ? location.pathname.split('/').filter(Boolean).pop() : 'display-app-1';
let signals = [];
let ranges = [];

const isoMinute = value => new Date(value).toISOString().replace(':00.000Z','Z');

async function json(url, options={}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

function draw(canvas, points, digital) {
  const ctx = canvas.getContext('2d');
  const width = canvas.width = canvas.clientWidth * devicePixelRatio;
  const height = canvas.height = canvas.clientHeight * devicePixelRatio;
  ctx.scale(devicePixelRatio, devicePixelRatio);
  const w = canvas.clientWidth, h = canvas.clientHeight, pad = 12;
  ctx.strokeStyle = '#27404f'; ctx.beginPath(); ctx.moveTo(pad,h-pad); ctx.lineTo(w-pad,h-pad); ctx.stroke();
  if (!points.length) return;
  const values = points.map(p => Number(p.value));
  const min = digital ? 0 : Math.min(...values), max = digital ? 1 : Math.max(...values);
  ctx.strokeStyle = '#54d1b2'; ctx.lineWidth = 1.5; ctx.beginPath();
  points.forEach((point,index) => {
    const x = pad + index / Math.max(1,points.length-1) * (w-pad*2);
    const y = h-pad-(Number(point.value)-min)/Math.max(.0001,max-min)*(h-pad*2);
    if(index===0) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  });
  ctx.stroke();
}

async function loadData() {
  const selected = ranges[Number(document.querySelector('#range-select').value || 0)];
  if (!selected) return;
  const start = new Date(selected.start_time), end = new Date(selected.end_time);
  const cappedEnd = new Date(Math.min(end.getTime(), start.getTime()+7*24*3600*1000));
  document.querySelector('#selected-range').textContent = `${start.toLocaleDateString()} – ${cappedEnd.toLocaleDateString()}`;
  document.querySelector('#message').textContent = 'データ取得中…';
  const data = await json('/api/v1/data/query', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_ids:signals.map(s=>s.signal_id),start_time:start.toISOString(),end_time:cappedEnd.toISOString(),max_points_per_signal:2000})});
  const charts = document.querySelector('#charts'); charts.innerHTML='';
  data.series.forEach(series => {
    const signal = signals.find(s=>s.signal_id===series.signal_id);
    const article=document.createElement('article'); article.className='chart';
    article.innerHTML=`<h3>${series.signal_id} · ${series.points.length} points</h3><canvas></canvas>`;
    charts.append(article); draw(article.querySelector('canvas'),series.points,['DI','DO'].includes(signal?.signal_type));
  });
  document.querySelector('#message').textContent = `${data.series.length}信号を表示しました。選択区間の先頭から最大7日を描画します。`;
}

async function init() {
  document.querySelector('#app-title').textContent = `表示アプリ ${appId.slice(-1)}`;
  const app = await json(`/api/v1/applications/${appId}/signals`); signals=app.items;
  document.querySelector('#signal-count').textContent=signals.length;
  const available = await json('/api/v1/available-range',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({signal_ids:signals.map(s=>s.signal_id)})});
  ranges=available.common_valid_periods; document.querySelector('#range-count').textContent=ranges.length;
  const select=document.querySelector('#range-select');
  select.innerHTML=ranges.map((r,i)=>`<option value="${i}">${isoMinute(r.start_time)} ～ ${isoMinute(r.end_time)}</option>`).join('');
  document.querySelector('#message').textContent=ranges.length?'範囲を選んでデータを表示してください。':'10信号に共通する有効区間はありません。';
  document.querySelector('#load-button').disabled=!ranges.length;
}

document.querySelector('#load-button').addEventListener('click',()=>loadData().catch(e=>document.querySelector('#message').textContent=e.message));
init().catch(e=>document.querySelector('#message').textContent=e.message);

