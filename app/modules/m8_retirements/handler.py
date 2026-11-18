from flask import Blueprint,request,jsonify
from app.errors import DomainError
from app import retirements
bp=Blueprint("retirements",__name__)
@bp.route("/api/retirements",methods=["GET","POST"])
def collection():
    if request.method=="GET": return jsonify({"migrations":retirements.list_migrations()})
    payload=request.get_json(silent=True)
    if not isinstance(payload,dict): raise DomainError("BAD_BODY","请求需要对象")
    return jsonify(retirements.retire(payload.get("alias"),payload.get("retired_at")))
@bp.route("/api/retirements/<migration_id>")
def detail(migration_id): return jsonify(retirements.get(migration_id))
