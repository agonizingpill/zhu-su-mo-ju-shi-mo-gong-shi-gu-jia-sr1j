"""Machine-hour rates are versioned per scope; a price change replaces the current row, history is not kept."""
from sqlalchemy import String,Float,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
class MachineRateVersion(Base):
    __tablename__='machine_rate_versions'
    __table_args__=(CheckConstraint('rate > 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    label:Mapped[str]=mapped_column(String(60),unique=True)
    machine:Mapped[str]=mapped_column(String(40),unique=True)
    rate:Mapped[float]=mapped_column(Float)
    note:Mapped[str]=mapped_column(String(300),default='')
    created_by:Mapped[str]=mapped_column(String(120))
    created_at:Mapped[str]=mapped_column(String(40))
