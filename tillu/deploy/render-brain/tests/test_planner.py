from app.planner import PlanRequest,make_plan

def test_plan_respects_daily_minutes():
    plan=make_plan(PlanRequest(subjects=['Physics','Math'],minutes_per_day=120,days=3,weak_subjects=['Physics']))
    assert len(plan['days'])==3
    assert all(day['total_minutes']==120 for day in plan['days'])
