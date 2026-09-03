const payload = document.querySelector('#payload');
const inputType = document.querySelector('#inputType');
const tokenizer = document.querySelector('#tokenizer');
const analyzeButton = document.querySelector('#analyzeButton');
const byteCount = document.querySelector('#byteCount');
const errorBox = document.querySelector('#error');
const status = document.querySelector('#status');
const summary = document.querySelector('#summary');
const results = document.querySelector('#results');
const cards = document.querySelector('#cards');
const compression = document.querySelector('#compression');
const notes = document.querySelector('#notes');

const examples = {
  json: JSON.stringify({tool:'search',results:Array.from({length:14},(_,i)=>({id:i,title:`Result ${i}`,score:0.98-i/100,metadata:{source:'demo',tags:['agent','context','transport']}}))}, null, 2),
  logs: Array.from({length:28},(_,i)=>`2026-09-04T03:${String(i).padStart(2,'0')}:14Z INFO worker=${i%4} request_id=req_${1000+i} completed latency_ms=${34+i} status=200`).join('\n'),
  code: `def fetch_records(client, ids):\n    records = []\n    for record_id in ids:\n        item = client.get(record_id)\n        if item is not None:\n            records.append({"id": record_id, "payload": item})\n    return records\n`,
  repeat: 'agent-context-tool-output-'.repeat(600),
};

function countBytes() {
  if (inputType.value === 'text') byteCount.textContent = `${new TextEncoder().encode(payload.value).length.toLocaleString()} bytes`;
  else byteCount.textContent = 'Base64 input';
}
payload.addEventListener('input', countBytes);
inputType.addEventListener('change', countBytes);
document.querySelectorAll('[data-example]').forEach(btn => btn.addEventListener('click', () => { inputType.value='text'; payload.value=examples[btn.dataset.example]; countBytes(); }));

function fmt(v, suffix='') { return v == null ? '—' : `${Number(v).toLocaleString()}${suffix}`; }
function esc(value) { const d=document.createElement('div'); d.textContent=String(value); return d.innerHTML; }

function render(data) {
  const reps = data.representations;
  const textReps = reps.filter(r => r.kind !== 'local token-ID representation');
  const bestText = [...textReps].sort((a,b)=>a.tokens-b.tokens)[0];
  const direct = reps.find(r => r.id === 'direct_id');
  summary.className = '';
  summary.innerHTML = `<div class="summary-grid">
    <div class="summary-cell"><strong>${fmt(data.input.bytes)}</strong><span>input bytes</span></div>
    <div class="summary-cell"><strong>${fmt(reps[0].tokens)}</strong><span>Base64 tokens</span></div>
    <div class="summary-cell"><strong>${esc(bestText.label)}</strong><span>best text transport</span></div>
    <div class="summary-cell"><strong>${direct ? fmt(direct.tokens) : '—'}</strong><span>Direct-ID local IDs</span></div>
  </div>`;
  cards.innerHTML = reps.map(r => `<article class="card ${r.id===bestText.id?'best':''}">
    <div class="card-kicker">${esc(r.kind)}</div><h3>${esc(r.label)}</h3>
    <div class="metric">${fmt(r.tokens)}</div><div class="metric-label">${r.id === 'direct_id' ? 'local token IDs' : 'tokens'}</div>
    <div class="saving ${r.savings_vs_base64_pct>0?'positive':''}">${r.savings_vs_base64_pct==null?'No baseline':`${r.savings_vs_base64_pct>0?'-':'+'}${Math.abs(r.savings_vs_base64_pct)}% count vs Base64 tokens`}</div>
    <div class="metric-label">encode ${fmt(r.encode_ms)} ms ${r.bit_width?` · ${r.bit_width}-bit`:''}</div>
    ${r.warning?`<p class="metric-label">${esc(r.warning)}</p>`:''}
    <div class="preview">${esc(Array.isArray(r.preview)?JSON.stringify(r.preview):r.preview)}</div>
  </article>`).join('');
  const c = data.compression;
  compression.innerHTML = `<table class="compression-table"><tbody>
    <tr><td>Original bytes</td><td>${fmt(data.input.bytes)}</td></tr>
    <tr><td>LZMA bytes</td><td>${fmt(c.compressed_bytes)}</td></tr>
    <tr><td>Byte reduction</td><td>${fmt(c.byte_reduction_pct,'%')}</td></tr>
    <tr><td>LZMA + Base64 tokens</td><td>${fmt(c.base64.tokens)}</td></tr>
    <tr><td>LZMA + ByteToken 15 tokens</td><td>${fmt(c.bytetoken_standard.tokens)}</td></tr>
    <tr><td>Compression time</td><td>${fmt(c.compression_ms)} ms</td></tr>
  </tbody></table>`;
  notes.innerHTML = data.notes.map(n=>`<li>${esc(n)}</li>`).join('');
  results.classList.remove('hidden');
}

analyzeButton.addEventListener('click', async () => {
  errorBox.textContent=''; status.textContent='Measuring…'; analyzeButton.disabled=true;
  try {
    const response = await fetch('/api/analyze', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({input_type:inputType.value,payload:payload.value,tokenizer:tokenizer.value})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Analysis failed');
    render(data); status.textContent='Measured';
  } catch (error) { errorBox.textContent=error.message; status.textContent='Error'; }
  finally { analyzeButton.disabled=false; }
});

payload.value = examples.json;
countBytes();
