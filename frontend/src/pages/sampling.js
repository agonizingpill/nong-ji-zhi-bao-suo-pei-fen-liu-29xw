import{heading,empty}from'../components/common.js';import{esc,pct,formData}from'../utils/format.js';import{api}from'../utils/api.js';import{PLAN_STATES,SLOT_STATES,SELECTION_KINDS}from'../constants.js';
export function render(s,u){
  let admin=u.role==='admin',writer=u.role!=='viewer';
  let p=s.plans.find(x=>x.id===Number(sessionStorage.getItem('plan-selected')))||s.plans[0];
  return heading('10 / DAILY SAMPLING','每天的拆检名额，先配额再抽签。','主管设当日总名额与低风险随机抽检保留额，其余按风险优先；确认后候选、概率与抽签依据全部固化，重试不重复占额。')+
  `<div class="split"><section class="plate"><h2>按日抽检派单计划</h2>${admin?`<form id="plan-create"><div class="form-grid"><div><label>派单日期</label><input name="plan_date" type="date" value="2026-11-19" required></div><div><label>当日总名额</label><input name="total_quota" type="number" min="1" max="1000" value="6" required></div><div><label>低风险随机保留额</label><input name="low_risk_reserve" type="number" min="0" max="1000" value="2" required></div></div><button>建立当日计划（草稿）</button><p class="legend">保留额仅用于概率 &lt; 50% 的低风险索赔随机抽签；其余名额按争议概率从高到低派给原分流候选。</p></form>`:''}
  <h2 style="margin-top:30px">计划簿</h2>${s.plans.map(x=>`<article class="sheet"><button class="ghost" data-plan="${x.id}">${esc(x.code)} / ${x.plan_date}</button><p><span class="badge ${x.state==='draft'?'mid':''}">${PLAN_STATES[x.state]}</span> 总名额 ${x.total_quota} · 低风险保留 ${x.low_risk_reserve} · 占用 ${x.held_quota} · 已开检 ${x.started_count} · 已归还 ${x.returned_quota}</p></article>`).join('')||empty('尚无抽检计划，主管可先建立当日草稿。')}</section>
  <aside class="rail">${p?planPanel(p,admin,writer):empty('选择左侧计划查看候选池、抽签依据与占额去向。')}</aside></div>`;
}
function planPanel(p,admin,writer){
  return `<h2>${esc(p.code)} / ${p.plan_date}</h2><p><span class="badge ${p.state==='draft'?'mid':''}">${PLAN_STATES[p.state]}</span> 抽签种子 <b class="mono">${p.draw_seed}</b></p>
  <div class="sheet"><p>总名额 <b>${p.total_quota}</b>　低风险随机保留 <b>${p.low_risk_reserve}</b><br>当前占用 <b>${p.held_quota}</b>　剩余可派 <b>${p.available_quota}</b>　已开检 <b>${p.started_count}</b><br>已撤回归还 <b>${p.returned_quota}</b>（归还名额不自动换人，留待后续计划）</p></div>
  ${p.state==='draft'?`<form id="plan-confirm" data-id="${p.id}"><button ${admin?'':'disabled'}>确认并固化今日名单</button><p class="legend">确认时一次性锁定候选池、风险概率与随机抽签依据；重复确认只返回同一名单，不重复占额、不换人。</p></form><div id="candidate-box" data-id="${p.id}"><p class="legend">候选池加载中…</p></div>`:`
  <h2 style="margin-top:20px">派单与占额去向</h2>${p.slots.map(slot=>`<article class="sheet"><p><b>${esc(slot.claim_code)}</b> <span class="badge ${slot.state==='withdrawn'?'bad':slot.state==='started'?'mid':''}">${SLOT_STATES[slot.state]}</span><br>${SELECTION_KINDS[slot.selection]} · 概率 ${pct(slot.risk_snapshot)} · 抽签值 ${slot.draw_value.toFixed(6)}</p><p class="legend">${esc(slot.draw_basis)}</p><div class="actions"><button data-start="${slot.id}" ${!writer||slot.state!=='selected'?'disabled':''}>开检</button><button class="danger" data-withdraw="${slot.id}" ${!writer||slot.state!=='selected'?'disabled':''}>撤回归还名额</button></div></article>`).join('')||empty('当日候选池为空，没有可派单的待裁决索赔。')}
  <p class="legend">未开检可撤回，名额立即归还；已开检不可归还。撤回与开检同时发生时只接受先达成的一种。<br>抽中的低风险索赔也须补齐拆检证据才能赔付；未抽中的高风险索赔仍执行原 50% 阈值证据要求，旧结案不变。</p>`}
  `;
}
export function bind(refresh,rerender){
  let f=document.querySelector('#plan-create');
  if(f)f.onsubmit=e=>{e.preventDefault();let d=formData(f);d.total_quota=Number(d.total_quota);d.low_risk_reserve=Number(d.low_risk_reserve);refresh(async()=>{let x=await api('/inspection-plans','POST',d);sessionStorage.setItem('plan-selected',x.id)},'当日抽检计划已建立为草稿')};
  document.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>{sessionStorage.setItem('plan-selected',b.dataset.plan);rerender()});
  let cf=document.querySelector('#plan-confirm');
  if(cf)cf.onsubmit=e=>{e.preventDefault();refresh(async()=>{let x=await api('/inspection-plans/'+cf.dataset.id+'/confirm','POST');sessionStorage.setItem('plan-selected',x.id)},'名单已确认固化：候选、概率与抽签依据已封存')};
  let box=document.querySelector('#candidate-box');
  let canPreview=document.querySelector('#plan-confirm button:not([disabled])');
  if(box&&canPreview)api('/inspection-plans/'+box.dataset.id+'/candidates').then(d=>{box.innerHTML=`<h2 style="margin-top:20px">确认前候选池预览</h2><div class="sheet"><p>可派候选 ${d.eligible_total} 份：低风险 ${d.low_risk_candidates} / 高风险 ${d.high_risk_candidates}<br>拟随机抽低风险 ${d.planned_random_low} 份，拟风险优先 ${d.planned_risk_priority} 份；示例随机数 ${d.sample_draw_value}</p></div>${d.candidates.map(c=>`<div class="sheet"><p><b>${esc(c.claim_code)}</b> · ${c.tier==='low_risk'?'低风险':'高风险'} · 概率 ${pct(c.risk)}</p></div>`).join('')||empty('暂无可派单候选（需已完成风险分流且未被其他名单占用）。')}`}).catch(e=>{box.innerHTML=`<p class="legend">${esc(e.message)}</p>`});
  else if(box)box.innerHTML='<p class="legend">候选池与抽签预览仅主管可查看。</p>';
  document.querySelectorAll('[data-start]').forEach(b=>b.onclick=()=>refresh(()=>api('/inspection-slots/'+b.dataset.start+'/start','POST'),'已开检，名额继续占用不可归还'));
  document.querySelectorAll('[data-withdraw]').forEach(b=>b.onclick=()=>refresh(()=>api('/inspection-slots/'+b.dataset.withdraw+'/withdraw','POST'),'名额已撤回归还候选池'));
}
