from datetime import date
from sqlalchemy import String,Integer,Float,Date,ForeignKey,CheckConstraint,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class InspectionPlan(Base):
    __tablename__='inspection_plans'
    __table_args__=(
        CheckConstraint('total_quota > 0'),
        CheckConstraint('low_risk_reserve >= 0 AND low_risk_reserve <= total_quota'),
        CheckConstraint("state in ('draft','confirmed')"),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    plan_date:Mapped[date]=mapped_column(Date,unique=True)
    total_quota:Mapped[int]=mapped_column(Integer)
    low_risk_reserve:Mapped[int]=mapped_column(Integer)
    state:Mapped[str]=mapped_column(String(20),default='draft')
    draw_seed:Mapped[int]=mapped_column(Integer)
    created_by:Mapped[str]=mapped_column(String(120))
    confirmed_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
class InspectionSlot(Base):
    __tablename__='inspection_slots'
    __table_args__=(
        CheckConstraint("state in ('selected','withdrawn','started')"),
        CheckConstraint("selection in ('random_low','risk_priority')"),
        CheckConstraint('draw_value >= 0 AND draw_value <= 1'),
        UniqueConstraint('plan_id','claim_id',name='uq_slot_plan_claim'),
        UniqueConstraint('active_claim_id',name='uq_slot_active_claim'),
    )
    id:Mapped[int]=mapped_column(primary_key=True)
    plan_id:Mapped[int]=mapped_column(ForeignKey('inspection_plans.id'))
    claim_id:Mapped[int]=mapped_column(ForeignKey('claims.id'))
    selection:Mapped[str]=mapped_column(String(20))
    state:Mapped[str]=mapped_column(String(20),default='selected')
    risk_snapshot:Mapped[float]=mapped_column(Float)
    draw_value:Mapped[float]=mapped_column(Float)
    draw_basis:Mapped[str]=mapped_column(String(500))
    active_claim_id:Mapped[int|None]=mapped_column(ForeignKey('claims.id'),nullable=True)
    created_at:Mapped[str]=mapped_column(String(40))
    started_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    withdrawn_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
