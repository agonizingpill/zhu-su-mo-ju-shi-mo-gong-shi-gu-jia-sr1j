from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select
from .models import Estimate,MachineSlot
from .rate_models import MachineRateVersion
from .services import item,record,current_rate

def create_version(s,machine,rate,note,actor):
    # Superseded versions are deleted: rate history lives only in estimate freezes and trial snapshots.
    # Labels increase monotonically per scope so a deleted version's label can never be reused.
    old=s.scalar(select(MachineRateVersion).where(MachineRateVersion.machine==machine).with_for_update())
    if old:
        seq=int(old.label.rsplit('-',1)[1])+1
        s.delete(old);s.flush()
    else:
        # Fresh read: also catches a version committed by a concurrent change after the lock wait.
        seq=max([int(l.rsplit('-',1)[1]) for l in s.scalars(select(MachineRateVersion.label).where(MachineRateVersion.machine==machine))]+[0])+1
    v=MachineRateVersion(label=f'RV-{machine}-{seq:04d}',machine=machine,rate=rate,note=note.strip(),created_by=actor,created_at=datetime.now(timezone.utc).isoformat())
    s.add(v);s.flush()
    return v,old
def expire_stale(s,u):
    # Requested estimates whose frozen version no longer matches the applicable one lose their application.
    expired=[]
    for e in s.scalars(select(Estimate).where(Estimate.status=='requested').with_for_update()):
        slot=item(s,MachineSlot,e.slot_id);cur=current_rate(s,slot.machine)
        if not cur or cur.label!=e.rate_version:
            reason=(f'费率版本 {e.rate_version or "未冻结"} 已被 {cur.label}（{cur.rate:g} 元/h）取代' if cur else '适用费率版本已撤销')+'，机时申请失效，请按当前费率重新申请'
            e.status='estimated';e.slot_id=None;e.rate_invalid_reason=reason;expired.append(e.code)
    return expired
def change_rate(s,p,u):
    machine=p.machine
    if machine!='ALL' and not s.scalar(select(MachineSlot.id).where(MachineSlot.machine==machine).limit(1)):
        raise HTTPException(409,'适用范围须为 ALL 或已开放机时的机台')
    old=s.scalar(select(MachineRateVersion).where(MachineRateVersion.machine==machine))
    if old and abs(old.rate-p.rate)<1e-9:raise HTTPException(409,'新费率与当前版本相同，无需调整')
    v,_=create_version(s,machine,p.rate,p.note,u.email)
    expired=expire_stale(s,u)
    record(s,u,f'{"调整" if old else "设置"}机时费率 {machine} → {p.rate:g} 元/h（{v.label}）'+(f'，{len(expired)} 份待承诺申请失效' if expired else ''))
    return v,expired
