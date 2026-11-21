from decimal import Decimal
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from .models import Estimate, Mould, MachineSlot, Audit
from .rate_models import MachineRateVersion
from .constants import ESTIMATE_STATES

def record(s,u,action): s.add(Audit(actor=u.email,action=action,stamp=datetime.now(timezone.utc).isoformat()))
def item(s,model,id):
    v=s.get(model,id)
    if v is None: raise HTTPException(404,'记录不存在')
    return v
def serialize(v): return {c.name:float(getattr(v,c.name)) if isinstance(getattr(v,c.name),Decimal) else getattr(v,c.name) for c in v.__table__.columns}
def require_edit(e):
    if e.status in ('committed','calculating'): raise HTTPException(409,'已承诺或计算中的估价不能修改')
def current_rate(s,machine):
    # Exact machine scope wins; otherwise fall back to the ALL baseline version.
    v=s.scalar(select(MachineRateVersion).where(MachineRateVersion.machine==machine))
    return v or s.scalar(select(MachineRateVersion).where(MachineRateVersion.machine=='ALL'))
def request_capacity(s,e,slot_id):
    if e.status!='estimated': raise HTTPException(409,'请先完成工时估算')
    slot=item(s,MachineSlot,slot_id)
    if e.predicted_hours>slot.capacity_hours-slot.reserved_hours+1e-6: raise HTTPException(409,'机时余量不足，请选择其他时段')
    v=current_rate(s,slot.machine)
    if not v: raise HTTPException(409,f'机台 {slot.machine} 尚未设置适用费率版本，请负责人先维护费率')
    # Freeze the applicable rate version onto the application; commitment revalidates it.
    e.rate=v.rate;e.rate_version=v.label;e.rate_invalid_reason=None
    e.slot_id=slot.id; e.status='requested'
def commit_capacity(s,eid,u):
    e=s.query(Estimate).filter_by(id=eid).with_for_update().one_or_none()
    if not e: raise HTTPException(404,'估价不存在')
    if e.status!='requested':
        if e.rate_invalid_reason: raise HTTPException(409,e.rate_invalid_reason+'；本次承诺未锁定机时，估单保留旧版费率')
        raise HTTPException(409,'只有已申请机时的估价可承诺')
    slot=s.query(MachineSlot).filter_by(id=e.slot_id).with_for_update().one()
    v=current_rate(s,slot.machine)
    if not v or v.label!=e.rate_version:
        # Price change collided with this application: expire it without locking hours, keep the old frozen rate.
        reason=(f'费率版本 {e.rate_version or "未冻结"} 已被 {v.label}（{v.rate:g} 元/h）取代' if v else '适用费率版本已撤销')+'，机时申请失效，请按当前费率重新申请'
        e.status='estimated';e.slot_id=None;e.rate_invalid_reason=reason
        record(s,u,'费率版本失效，承诺拒绝 '+e.code);s.commit()
        raise HTTPException(409,reason+f'；本次承诺未锁定机时，估单保留旧版费率 {e.rate:g} 元/h')
    floor=round(e.predicted_hours*e.rate*1.15,2)
    if e.quote_amount<floor: raise HTTPException(409,f'报价低于成本底线 {floor:.2f} 元，请修订报价后重新申请')
    if e.predicted_hours>slot.capacity_hours-slot.reserved_hours+1e-6: raise HTTPException(409,'机时已被其他承诺占用，不能超售')
    slot.reserved_hours=round(slot.reserved_hours+e.predicted_hours,2)
    e.status='committed'
    return e
