from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import db_session
from .auth import current,admin
from .services import serialize
from .rate_models import MachineRateVersion
from .rate_schemas import RateVersionInput
from . import rate_service as svc
router=APIRouter()
@router.get('/rate-versions')
def versions(s=Depends(db_session),u=Depends(current)):return [serialize(x) for x in s.scalars(select(MachineRateVersion).order_by(MachineRateVersion.machine))]
@router.post('/rate-versions')
def change(p:RateVersionInput,s=Depends(db_session),u=Depends(admin)):
    v,expired=svc.change_rate(s,p,u);s.commit();return {'version':serialize(v),'expired_estimates':expired}
