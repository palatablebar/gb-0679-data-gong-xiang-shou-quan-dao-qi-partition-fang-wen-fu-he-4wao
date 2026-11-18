import hashlib
from app.errors import DomainError
from app.values import instant
from app.modules.m2_resources.rules import RESOURCES
DECISION="保留历史版本并让新访问失效：历史访问仍按退役前归属解释，退役时刻起新访问不得再借用同一别名"
SEAL_POLICY="受影响批次已说明归属差异，可封存；未说明归属差异的批次不能封存"
def validate(alias,retired_at_text):
    if not isinstance(alias,str) or not alias.strip(): raise DomainError("BAD_ALIAS","请提供要退役的别名")
    alias=alias.strip();resource=RESOURCES.get(alias)
    if not resource: raise DomainError("UNKNOWN_ALIAS","别名未登记")
    if retired_at_text is None: raise DomainError("BAD_RETIRED_AT","请提供退役时刻")
    return alias,resource,instant(retired_at_text)
def migration_id(alias,resource,retired_at):
    return hashlib.sha256(f"{alias}|{resource}|{retired_at.isoformat()}".encode()).hexdigest()[:20]
def build_migration(alias,resource,retired_at,runs):
    affected=[]
    for run in runs:
        stage=run["stages"][-1];historical=blocked=0
        for row in stage["rows"]:
            if row.get("alias")!=alias: continue
            try: at=instant(row["access_time"])
            except (DomainError,KeyError): continue
            if at<retired_at: historical+=1
            else: blocked+=1
        for q in stage.get("cumulative_quarantine",[]):
            if q.get("reason")=="ALIAS_RETIRED" and q.get("resource")==alias: blocked+=1
        if historical or blocked:
            affected.append({"run_id":run["run_id"],"historical_rows":historical,"blocked_rows":blocked,"explanation":f"批次含{historical+blocked}行借用别名{alias}：{historical}行早于退役时刻，保留{resource}归属；{blocked}行不早于退役时刻，按新归属不再受理","seal_eligible":True})
    return {"migration_id":migration_id(alias,resource,retired_at),"alias":alias,"resource":resource,"retired_at":retired_at.isoformat(),
        "ownership_before":f"{alias} 生效中，访问归属 {resource}",
        "ownership_after":f"{alias} 停用；{resource} 仅接受规范名登记，退役时刻起借用别名的访问隔离",
        "decision":DECISION,"seal_policy":SEAL_POLICY,"affected_batches":affected}
