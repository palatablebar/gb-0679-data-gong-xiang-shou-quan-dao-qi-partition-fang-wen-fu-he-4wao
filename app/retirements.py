import json
from datetime import datetime,timezone
from app import store
from app.errors import DomainError
from app.values import instant
def retire(alias,retired_at_text):
    from app.modules.m8_retirements import rules
    alias,resource,retired_at=rules.validate(alias,retired_at_text)
    runs=[store.get(r["run_id"]) for r in store.history()]
    return commit(rules.build_migration(alias,resource,retired_at,runs))
def commit(migration):
    "原子切换归属：停用同别名旧迁移并写入本次结果；失败回滚，旧迁移结果保留。"
    payload=json.dumps(migration,ensure_ascii=False)
    now=datetime.now(timezone.utc).isoformat()
    with store.connect() as db:
        db.execute("UPDATE retirements SET active=0 WHERE alias=?",(migration["alias"],))
        row=db.execute("SELECT 1 FROM retirements WHERE migration_id=?",(migration["migration_id"],)).fetchone()
        if row: db.execute("UPDATE retirements SET payload=?,retired_at=?,active=1 WHERE migration_id=?",(payload,migration["retired_at"],migration["migration_id"]))
        else: db.execute("INSERT INTO retirements(migration_id,alias,resource,retired_at,payload,active,created_at) VALUES (?,?,?,?,?,1,?)",(migration["migration_id"],migration["alias"],migration["resource"],migration["retired_at"],payload,now))
    return {**migration,"active":True}
def list_migrations():
    with store.connect() as db: rows=db.execute("SELECT payload,active FROM retirements ORDER BY created_at,migration_id").fetchall()
    return [{**json.loads(payload),"active":bool(active)} for payload,active in rows]
def get(migration_id):
    with store.connect() as db: row=db.execute("SELECT payload,active FROM retirements WHERE migration_id=?",(migration_id,)).fetchone()
    if not row: raise DomainError("NOT_FOUND","迁移结果不存在",404)
    return {**json.loads(row[0]),"active":bool(row[1])}
def active():
    "当前生效的归属切换：{别名: 退役时刻}。"
    with store.connect() as db: rows=db.execute("SELECT alias,retired_at FROM retirements WHERE active=1").fetchall()
    return {alias:instant(retired_at) for alias,retired_at in rows}
def snapshot(context):
    "M2 用的归属快照；预览可用 context['retirements'] 覆盖，否则读当前生效切换。"
    raw=context.get("retirements") if isinstance(context,dict) and "retirements" in context else active()
    return {alias:(instant(at) if isinstance(at,str) else at) for alias,at in (raw or {}).items()}
def coverage():
    "当前生效迁移已说明归属差异的批次：{别名: {run_id}}。"
    with store.connect() as db: rows=db.execute("SELECT alias,payload FROM retirements WHERE active=1").fetchall()
    return {alias:{b["run_id"] for b in json.loads(payload)["affected_batches"]} for alias,payload in rows}
def seal_hold(run_id,rows,quarantine):
    "批次引用了已退役别名但迁移结果未说明其归属差异时，返回封存阻断清单。"
    if not run_id: return []
    retired=active()
    if not retired: return []
    referenced=set()
    for row in rows:
        if row.get("alias") in retired: referenced.add(row["alias"])
    for row in quarantine:
        if row.get("reason")=="ALIAS_RETIRED" and row.get("resource") in retired: referenced.add(row["resource"])
    covered=coverage()
    return [{"alias":alias,"run_id":run_id,"reason":"SEAL_OWNERSHIP_UNEXPLAINED","detail":"批次未说明归属差异，不能封存"} for alias in sorted(referenced) if run_id not in covered.get(alias,set())]
def seal_hold_for_run(run):
    stage=run["stages"][-1]
    return seal_hold(run["run_id"],stage["rows"],stage.get("cumulative_quarantine",[]))
