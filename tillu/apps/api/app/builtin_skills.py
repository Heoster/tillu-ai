"""Versioned, reviewed built-in Agent Skills shipped with TILLU."""
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
from .learning import parse_skill_md
from .repository import list_skills,save_skill

SKILLS_ROOT=Path(__file__).resolve().parents[1]/'skills'
def install_builtin_skills(user_id):
    existing={(x['name'],x['version']) for x in list_skills(user_id)};installed=[];stamp=datetime.now(timezone.utc).isoformat()
    for path in sorted(SKILLS_ROOT.glob('*/SKILL.md')):
        parsed=parse_skill_md(path.read_text())
        if (parsed['name'],1) in existing:continue
        row={'id':str(uuid4()),'user_id':user_id,**parsed,'version':1,'status':'active','source_plan_id':None,'parent_skill_id':None,'package_manifest':{'builtin':True,'path':str(path.relative_to(SKILLS_ROOT))},'metrics':{'runs':0,'successes':0,'failures':0},'created_at':stamp,'updated_at':stamp};save_skill(row);installed.append(row)
    return installed
