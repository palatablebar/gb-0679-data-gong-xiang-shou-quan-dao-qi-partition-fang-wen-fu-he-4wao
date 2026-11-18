import pytest
from app import store,retirements
from app.pipeline import execute,load_sample
from app.modules.m2_resources.rules import evaluate as map_resources
from app.modules.m7_seals.rules import evaluate as seal
from app.modules.m8_retirements.rules import validate,build_migration,DECISION
from app.errors import DomainError
@pytest.fixture
def dirty_run(): return execute(load_sample("dirty.csv"))
def test_retire_forms_unique_migration(dirty_run):
    first=retirements.retire("订单","2026-11-18T00:00:00Z")
    again=retirements.retire("订单","2026-11-18T00:00:00Z")
    assert first["migration_id"]==again["migration_id"]
    assert len(retirements.list_migrations())==1
def test_migration_explains_ownership_batches_and_seal(dirty_run):
    m=retirements.retire("订单","2026-11-18T00:00:00Z")
    assert m["ownership_before"]!=m["ownership_after"] and m["resource"]=="orders"
    assert m["decision"]==DECISION and m["seal_policy"]
    batch={b["run_id"]:b for b in m["affected_batches"]}[dirty_run["run_id"]]
    assert batch["historical_rows"]>0 and batch["blocked_rows"]==0 and batch["seal_eligible"] is True
    assert "归属" in batch["explanation"]
def test_retired_alias_blocks_new_access_keeps_history():
    retirements.retire("订单","2026-11-18T00:00:00Z")
    rows=[{"resource":"订单","partition":"2026-01","principal":"a","access_time":"2026-11-17T23:59:59Z"},
        {"resource":"订单","partition":"2026-01","principal":"a","access_time":"2026-11-18T00:00:00Z"},
        {"resource":"orders","partition":"2026-01","principal":"a","access_time":"2026-11-18T00:00:00Z"}]
    out=map_resources(rows,{})
    assert [r["resource"] for r in out["rows"]]==["orders","orders"]
    assert out["rows"][0]["alias"]=="订单" and "alias" not in out["rows"][1]
    assert out["quarantine"][0]["reason"]=="ALIAS_RETIRED"
def test_unexplained_batch_cannot_seal(client):
    retirements.retire("订单","2026-11-18T00:00:00Z")
    p=client.post("/api/runs",json={"sample":"dirty.csv"}).get_json()
    assert p["stages"][6]["metrics"]["ready"] is False
    assert p["stages"][6]["metrics"]["seal_hold"][0]["reason"]=="SEAL_OWNERSHIP_UNEXPLAINED"
    r=client.get("/api/runs/"+p["run_id"]+"/archive")
    assert r.status_code==409 and r.get_json()["code"]=="SEAL_OWNERSHIP_UNEXPLAINED"
def test_explained_batch_keeps_seal_eligibility(client,dirty_run):
    retirements.retire("订单","2026-11-18T00:00:00Z")
    assert client.get("/api/runs/"+dirty_run["run_id"]+"/archive").status_code==200
def test_retry_covers_batch_without_new_result(client):
    retirements.retire("订单","2026-11-18T00:00:00Z")
    p=client.post("/api/runs",json={"sample":"dirty.csv"}).get_json()
    assert client.get("/api/runs/"+p["run_id"]+"/archive").status_code==409
    retirements.retire("订单","2026-11-18T00:00:00Z")
    assert len(retirements.list_migrations())==1
    assert client.get("/api/runs/"+p["run_id"]+"/archive").status_code==200
def test_failed_switch_preserves_old_migration(dirty_run,monkeypatch):
    first=retirements.retire("订单","2026-11-18T00:00:00Z")
    monkeypatch.setattr(retirements,"commit",lambda migration:(_ for _ in ()).throw(RuntimeError("db down")))
    with pytest.raises(RuntimeError): retirements.retire("订单","2026-11-19T00:00:00Z")
    migrations=retirements.list_migrations()
    assert len(migrations)==1 and migrations[0]["migration_id"]==first["migration_id"] and migrations[0]["active"] is True
def test_invalid_retire_input_preserves_state():
    retirements.retire("订单","2026-11-18T00:00:00Z")
    with pytest.raises(DomainError): retirements.retire("订单","没有时区")
    with pytest.raises(DomainError): retirements.retire("不存在的别名","2026-11-18T00:00:00Z")
    assert len(retirements.list_migrations())==1
def test_post_retirement_quarantine_counted(dirty_run):
    m=retirements.retire("订单","2026-11-15T00:00:00Z")
    batch={b["run_id"]:b for b in m["affected_batches"]}[dirty_run["run_id"]]
    assert batch["blocked_rows"]>0
def test_seal_hold_unit():
    retirements.retire("订单","2026-11-18T00:00:00Z")
    rows=[{"event_id":"1","alias":"订单","access_time":"2026-11-16T00:00:00Z"}]
    assert seal(rows,{"run_id":"r-x","quarantine":[]})["metrics"]["ready"] is False
    assert seal(rows,{"quarantine":[]})["metrics"]["ready"] is True
def test_retirements_entrances(client):
    assert client.get("/api/retirements").get_json()=={"migrations":[]}
    assert client.get("/retirements").status_code==200
    r=client.post("/api/retirements",json={"alias":"订单","retired_at":"2026-11-18T00:00:00Z"})
    assert r.status_code==200 and r.get_json()["active"] is True
    assert client.get("/api/retirements/"+r.get_json()["migration_id"]).status_code==200
    assert client.get("/api/retirements/missing").status_code==404
    assert client.post("/api/retirements",json={"alias":"订单"}).status_code==422
