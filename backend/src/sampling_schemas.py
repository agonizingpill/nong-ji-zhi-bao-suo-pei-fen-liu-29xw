from datetime import date
from pydantic import BaseModel,Field,model_validator
class PlanIn(BaseModel):
    plan_date:date
    total_quota:int=Field(gt=0,le=1000)
    low_risk_reserve:int=Field(ge=0,le=1000)
    @model_validator(mode='after')
    def reserve_within_quota(self):
        if self.low_risk_reserve>self.total_quota:raise ValueError('低风险随机抽检保留额不能超过当日总名额')
        return self
