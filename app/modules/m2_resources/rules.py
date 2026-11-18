from app.reasons import reject
from app.values import instant
from app.errors import DomainError
from app.retirements import snapshot
RESOURCES={"订单":"orders","orders":"orders","客户":"customers","customers":"customers"}
def evaluate(rows,context):
    retired=snapshot(context);good=[];bad=[]
    for row in rows:
        name=row.get("resource")
        resource=RESOURCES.get(name)
        if not resource:bad.append(reject(row,"UNKNOWN_RESOURCE","资源未登记"));continue
        if name in retired:
            try: at=instant(row.get("access_time",""))
            except DomainError: at=None
            if at is not None and at>=retired[name]:bad.append(reject(row,"ALIAS_RETIRED",f"别名{name}已退役，退役时刻起访问须使用规范名{resource}"));continue
        part=row.get("partition","")
        if len(part)!=7 or part[4]!="-" or not part[:4].isdigit() or not part[5:].isdigit() or not 1<=int(part[5:])<=12:bad.append(reject(row,"BAD_PARTITION","分区必须为YYYY-MM"));continue
        if not row.get("principal"):bad.append(reject(row,"EMPTY_PRINCIPAL","访问主体为空"));continue
        mapped={**row,"resource":resource,"partition":part}
        if name!=resource: mapped["alias"]=name
        good.append(mapped)
    return {"rows":good,"quarantine":bad,"metrics":{"accepted":len(good),"resources":len(set(r["resource"] for r in good))}}
