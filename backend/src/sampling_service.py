import hashlib,random
from datetime import datetime,timezone,date
from fastapi import HTTPException
from sqlalchemy import select
from .models import Claim
from .sampling_models import InspectionPlan,InspectionSlot
from .claim_service import audit
RISK_CUTOFF=.5
def now():return datetime.now(timezone.utc).isoformat()
def locked(s,cls,id):
    x=s.scalar(select(cls).where(cls.id==id).with_for_update().execution_options(populate_existing=True))
    if not x:raise HTTPException(404,'抽检计划或派单记录不存在')
    return x
def draw_seed_for(plan_date,actor):
    raw=f'sampling:{plan_date.isoformat()}:{actor}:gengchuan-v1'
    return int.from_bytes(hashlib.sha256(raw.encode()).digest()[:8],'big') & 0x7fffffff
def slot_view(s,x):
    c=s.get(Claim,x.claim_id)
    return {col.name:getattr(x,col.name) for col in x.__table__.columns}|{
        'claim_code':c.code,'machine_id':c.machine_id,'part':c.part,'active':x.state!='withdrawn'}
def plan_view(s,p):
    slots=s.scalars(select(InspectionSlot).where(InspectionSlot.plan_id==p.id).order_by(InspectionSlot.id)).all()
    held=sum(1 for x in slots if x.state!='withdrawn')
    started=sum(1 for x in slots if x.state=='started')
    withdrawn=sum(1 for x in slots if x.state=='withdrawn')
    return {col.name:(getattr(p,col.name).isoformat() if isinstance(getattr(p,col.name),date) else getattr(p,col.name)) for col in p.__table__.columns}|{
        'slots':[slot_view(s,x) for x in slots],
        'held_quota':held,'returned_quota':withdrawn,'started_count':started,
        'available_quota':p.total_quota-held}
def eligible(s,for_update=False):
    q=select(Claim).where(Claim.historical==False,Claim.status=='assessed',Claim.risk.isnot(None))
    if for_update:q=q.with_for_update()
    return s.scalars(q.order_by(Claim.id)).all()
def occupied_ids(s,for_update=False):
    q=select(InspectionSlot.claim_id).where(InspectionSlot.state!='withdrawn')
    if for_update:q=q.with_for_update()
    return set(s.scalars(q).all())
def _build_slots(s,p,claims):
    rng=random.Random(p.draw_seed)
    occupied=occupied_ids(s,for_update=True)
    pool=[c for c in claims if c.id not in occupied]
    lows=[c for c in pool if c.risk<RISK_CUTOFF]
    highs=[c for c in pool if c.risk>=RISK_CUTOFF]
    made=[]
    low_pick=min(p.low_risk_reserve,len(lows))
    shuffled=lows.copy();rng.shuffle(shuffled)
    for c in shuffled[:low_pick]:
        draw=rng.random()
        made.append(InspectionSlot(plan_id=p.id,claim_id=c.id,selection='random_low',state='selected',
            risk_snapshot=c.risk,draw_value=draw,active_claim_id=c.id,created_at=now(),
            draw_basis=f'低风险随机抽检保留名额：种子{p.draw_seed}，候选{len(lows)}份，随机数{draw:.6f}，按随机数排序抽前{low_pick}份'))
    chosen={c.id for c in shuffled[:low_pick]}
    remaining=[c for c in pool if c.id not in chosen]
    remaining.sort(key=lambda c:(-c.risk,c.id))
    risk_slots=p.total_quota-len(made)
    for c in remaining[:risk_slots]:
        made.append(InspectionSlot(plan_id=p.id,claim_id=c.id,selection='risk_priority',state='selected',
            risk_snapshot=c.risk,draw_value=float(c.risk),active_claim_id=c.id,created_at=now(),
            draw_basis=f'风险优先名额：按分流争议概率{c.risk:.6f}由高到低（同概率按索赔编号）排序占满剩余名额'))
    return made,pool,len(lows),len(highs)
def preview(s,p):
    if p.state=='confirmed':raise HTTPException(409,'名单已确认固化，请直接查看派单明细')
    seed=draw_seed_for(p.plan_date,p.created_by)
    rng=random.Random(seed)
    claims=eligible(s)
    occupied=occupied_ids(s)
    pool=[c for c in claims if c.id not in occupied]
    lows=sorted((c for c in pool if c.risk<RISK_CUTOFF),key=lambda c:c.id)
    highs=sorted((c for c in pool if c.risk>=RISK_CUTOFF),key=lambda c:c.id)
    trial=rng.random()
    low_pick=min(p.low_risk_reserve,len(lows))
    ranked=sorted(pool,key=lambda c:(-c.risk,c.id))
    return {'plan_id':p.id,'plan_date':p.plan_date.isoformat(),'total_quota':p.total_quota,
        'low_risk_reserve':p.low_risk_reserve,'draw_seed':seed,'eligible_total':len(pool),
        'low_risk_candidates':len(lows),'high_risk_candidates':len(highs),
        'planned_random_low':low_pick,'planned_risk_priority':min(p.total_quota-low_pick,len(pool)-low_pick),
        'sample_draw_value':round(trial,6),
        'candidates':[{'claim_id':c.id,'claim_code':c.code,'risk':c.risk,
                       'tier':'low_risk' if c.risk<RISK_CUTOFF else 'high_risk'} for c in ranked]}
def create_plan(s,d,u):
    if s.scalar(select(InspectionPlan.id).where(InspectionPlan.plan_date==d.plan_date).with_for_update()):
        raise HTTPException(409,'该日期已存在抽检派单计划，每日仅允许一份')
    p=InspectionPlan(code=f'PLAN-{d.plan_date.strftime("%Y%m%d")}',plan_date=d.plan_date,
        total_quota=d.total_quota,low_risk_reserve=d.low_risk_reserve,state='draft',
        draw_seed=draw_seed_for(d.plan_date,u['email']),created_by=u['email'])
    s.add(p);s.flush()
    audit(s,u,'sampling_plan_created',f'{p.code}:总名额{d.total_quota}:低风险保留{d.low_risk_reserve}')
    return plan_view(s,p)
def confirm(s,id,u):
    p=locked(s,InspectionPlan,id)
    if p.state=='confirmed':
        audit(s,u,'sampling_confirm_replayed',f'{p.code}:重试返回已固化名单，不重复占额')
        return plan_view(s,p)
    claims=eligible(s,for_update=True)
    made,pool,n_low,n_high=_build_slots(s,p,claims)
    if not pool:raise HTTPException(409,'当前没有可派单的待裁决索赔（需已完成风险分流且未在其他名单中占用）')
    for x in made:s.add(x)
    p.state='confirmed';p.confirmed_at=now();s.flush()
    audit(s,u,'sampling_plan_confirmed',f'{p.code}:候选{len(pool)}（低风险{n_low}/高风险{n_high}），固化{len(made)}个名额，抽签种子{p.draw_seed}')
    return plan_view(s,p)
def _slot(s,id):
    preview=s.get(InspectionSlot,id)
    if not preview:raise HTTPException(404,'派单名额不存在')
    locked(s,InspectionPlan,preview.plan_id)
    return locked(s,InspectionSlot,id)
def start(s,id,u):
    x=_slot(s,id)
    if x.state=='started':raise HTTPException(409,'该名额已开检，不能重复开检')
    if x.state=='withdrawn':raise HTTPException(409,'名额已撤回归还，不能再开检；撤回与开检同时发生时只接受先达成的一种')
    x.state='started';x.started_at=now()
    c=s.get(Claim,x.claim_id)
    audit(s,u,'sampling_slot_started',f'名额#{x.id}:{c.code}开检，名额继续占用')
    return slot_view(s,x)
def withdraw(s,id,u):
    x=_slot(s,id)
    if x.state=='withdrawn':raise HTTPException(409,'名额已撤回，不能重复撤回')
    if x.state=='started':raise HTTPException(409,'已开检名额不可撤回，名额不予归还；撤回与开检同时发生时只接受先达成的一种')
    x.state='withdrawn';x.withdrawn_at=now();x.active_claim_id=None
    c=s.get(Claim,x.claim_id)
    audit(s,u,'sampling_slot_withdrawn',f'名额#{x.id}:{c.code}撤回，名额已归还候选池')
    return slot_view(s,x)
def sampled_active(s,claim_id):
    return s.scalar(select(InspectionSlot.id).where(InspectionSlot.claim_id==claim_id,
        InspectionSlot.state!='withdrawn').with_for_update())
