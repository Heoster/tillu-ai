from datetime import date,timedelta
from pydantic import BaseModel,Field
class PlanRequest(BaseModel):
    subjects:list[str]=["Physics","Chemistry","Mathematics"]
    minutes_per_day:int=Field(default=180,ge=30,le=720)
    days:int=Field(default=7,ge=1,le=30)
    weak_subjects:list[str]=[]

def make_plan(r:PlanRequest):
    blocks=[];today=date.today();subjects=r.subjects or ["Physics"]
    weights={s:(2 if s in r.weak_subjects else 1) for s in subjects}
    rotation=[s for s in subjects for _ in range(weights[s])]
    for day in range(r.days):
        count=min(3,len(subjects));base=r.minutes_per_day//count
        sessions=[]
        for j in range(count):
            subject=rotation[(day*count+j)%len(rotation)]
            sessions.append({"subject":subject,"minutes":base,"type":"concept" if j==0 else "practice" if j==1 else "revision"})
        blocks.append({"date":str(today+timedelta(days=day)),"sessions":sessions,"total_minutes":sum(x["minutes"] for x in sessions)})
    return {"days":blocks,"strategy":"Weak subjects receive extra rotation; every day balances concepts, practice and revision."}
