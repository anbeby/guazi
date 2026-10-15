# -*- coding: utf-8 -*-
"""智慧园区接口：园区、区域、档口、入驻合同、档口入驻/退租。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_lookups
from app.api.serializers import Lookups
from app.core.database import get_db
from app.core.deps import require
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.response import ApiResponse, PageData, normalize_page, ok, paginate
from app.core.scope import is_unrestricted, park_scope_ids
from app.core.timeutil import now
from app.models.enterprise import Enterprise, Park, ParkContract, ParkZone, Stall
from app.models.org import User
from app.schemas.park import (
    ParkContractIn,
    ParkContractOut,
    ParkContractUpdate,
    ParkIn,
    ParkOut,
    ParkUpdate,
    StallAssignIn,
    StallIn,
    StallOut,
    StallUpdate,
    ZoneIn,
    ZoneOut,
)
from app.services import integration
from app.services.numbering import next_no

router = APIRouter(tags=["智慧园区"])


def _park_out(db: Session, lk: Lookups, park: Park) -> dict:
    zone_count = db.query(ParkZone).filter(ParkZone.park_id == park.id).count()
    stall_count = db.query(Stall).filter(Stall.park_id == park.id).count()
    stall_rented = (
        db.query(Stall).filter(Stall.park_id == park.id, Stall.status == "rented").count()
    )
    enterprise_count = db.query(Enterprise).filter(Enterprise.park_id == park.id).count()
    return {
        "id": park.id,
        "code": park.code,
        "name": park.name,
        "region": park.region,
        "address": park.address,
        "area_total": float(park.area_total or 0),
        "contact_name": park.contact_name,
        "contact_phone": park.contact_phone,
        "status": park.status,
        "description": park.description,
        "zone_count": zone_count,
        "stall_count": stall_count,
        "stall_rented": stall_rented,
        "enterprise_count": enterprise_count,
        "created_at": park.created_at,
    }


def _stall_out(db: Session, lk: Lookups, stall: Stall) -> dict:
    return {
        "id": stall.id,
        "park_id": stall.park_id,
        "park_name": lk.park_name(stall.park_id),
        "zone_id": stall.zone_id,
        "zone_name": _zone_name(db, stall.zone_id),
        "code": stall.code,
        "name": stall.name,
        "area": float(stall.area or 0),
        "monthly_fee": float(stall.monthly_fee or 0),
        "status": stall.status,
        "enterprise_id": stall.enterprise_id,
        "enterprise_name": lk.enterprise_name(stall.enterprise_id),
        "remark": stall.remark,
    }


_zone_cache: dict = {}


def _zone_name(db: Session, zone_id: Optional[int]) -> Optional[str]:
    if not zone_id:
        return None
    row = db.get(ParkZone, zone_id)
    return row.name if row else None


def _park_contract_out(db: Session, lk: Lookups, row: ParkContract) -> dict:
    return {
        "id": row.id,
        "contract_no": row.contract_no,
        "park_id": row.park_id,
        "park_name": lk.park_name(row.park_id),
        "stall_id": row.stall_id,
        "stall_code": lk.stall_code(row.stall_id),
        "enterprise_id": row.enterprise_id,
        "enterprise_name": lk.enterprise_name(row.enterprise_id),
        "start_date": row.start_date,
        "end_date": row.end_date,
        "rent_amount": float(row.rent_amount or 0),
        "deposit_amount": float(row.deposit_amount or 0),
        "fee_cycle": row.fee_cycle,
        "status": row.status,
        "signed_at": row.signed_at,
        "file_url": row.file_url,
        "remark": row.remark,
        "created_at": row.created_at,
    }


# --------------------------------------------------------------------------- 园区


@router.get("/parks", response_model=ApiResponse[PageData[ParkOut]], summary="园区列表")
def list_parks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("park:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Park)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Park.name.like(like), Park.code.like(like)))
    if status:
        query = query.filter(Park.status == status)
    if not is_unrestricted(user):
        scope = park_scope_ids(db, user)
        if scope:
            query = query.filter(Park.id.in_(scope))
    total = query.count()
    rows = query.order_by(Park.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok(paginate([_park_out(db, lk, row) for row in rows], total, page, page_size))


@router.post("/parks", response_model=ApiResponse[ParkOut], summary="创建园区")
def create_park(
    payload: ParkIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    if db.query(Park).filter(Park.code == payload.code).first():
        raise Conflict(f"园区编码已存在：{payload.code}")
    park = Park(**payload.model_dump())
    db.add(park)
    db.flush()
    return ok(_park_out(db, lk, park))


@router.get("/parks/{park_id}", response_model=ApiResponse[ParkOut], summary="园区详情")
def get_park(
    park_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:read")),
) -> dict:
    park = db.get(Park, park_id)
    if park is None:
        raise NotFound("园区不存在")
    return ok(_park_out(db, lk, park))


@router.put("/parks/{park_id}", response_model=ApiResponse[dict], summary="更新园区")
def update_park(
    park_id: int,
    payload: ParkUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:write")),
) -> dict:
    park = db.get(Park, park_id)
    if park is None:
        raise NotFound("园区不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(park, field, value)
    db.flush()
    return ok({"id": park.id, "name": park.name, "updated": True})


@router.delete("/parks/{park_id}", response_model=ApiResponse[dict], summary="删除园区")
def delete_park(
    park_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:write")),
) -> dict:
    park = db.get(Park, park_id)
    if park is None:
        raise NotFound("园区不存在")
    if db.query(Stall).filter(Stall.park_id == park_id).count():
        raise Conflict("园区下存在档口，无法删除")
    if db.query(Enterprise).filter(Enterprise.park_id == park_id).count():
        raise Conflict("园区下存在入驻企业，无法删除")
    db.query(ParkZone).filter(ParkZone.park_id == park_id).delete()
    db.delete(park)
    db.flush()
    return ok({"deleted": True})


# --------------------------------------------------------------------------- 区域


@router.get("/parks/{park_id}/zones", response_model=ApiResponse[List[ZoneOut]], summary="区域列表")
def list_zones(
    park_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:read")),
) -> dict:
    if db.get(Park, park_id) is None:
        raise NotFound("园区不存在")
    rows = (
        db.query(ParkZone)
        .filter(ParkZone.park_id == park_id)
        .order_by(ParkZone.sort.asc(), ParkZone.id.asc())
        .all()
    )
    counts = dict(
        db.query(Stall.zone_id, func.count(Stall.id)).group_by(Stall.zone_id).all()
    )
    return ok(
        [
            {
                "id": row.id,
                "park_id": row.park_id,
                "code": row.code,
                "name": row.name,
                "zone_type": row.zone_type,
                "area": float(row.area or 0),
                "sort": row.sort,
                "status": row.status,
                "stall_count": int(counts.get(row.id, 0)),
            }
            for row in rows
        ]
    )


@router.post("/parks/{park_id}/zones", response_model=ApiResponse[ZoneOut], summary="创建区域")
def create_zone(
    park_id: int,
    payload: ZoneIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:write")),
) -> dict:
    if db.get(Park, park_id) is None:
        raise NotFound("园区不存在")
    exists = (
        db.query(ParkZone)
        .filter(ParkZone.park_id == park_id, ParkZone.code == payload.code)
        .first()
    )
    if exists:
        raise Conflict(f"区域编码已存在：{payload.code}")
    zone = ParkZone(park_id=park_id, **payload.model_dump())
    db.add(zone)
    db.flush()
    return ok(
        {
            "id": zone.id,
            "park_id": zone.park_id,
            "code": zone.code,
            "name": zone.name,
            "zone_type": zone.zone_type,
            "area": float(zone.area or 0),
            "sort": zone.sort,
            "status": zone.status,
            "stall_count": 0,
        }
    )


@router.put("/zones/{zone_id}", response_model=ApiResponse[dict], summary="更新区域")
def update_zone(
    zone_id: int,
    payload: ZoneIn,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:write")),
) -> dict:
    zone = db.get(ParkZone, zone_id)
    if zone is None:
        raise NotFound("区域不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.flush()
    return ok({"id": zone.id, "name": zone.name, "updated": True})


@router.delete("/zones/{zone_id}", response_model=ApiResponse[dict], summary="删除区域")
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:write")),
) -> dict:
    zone = db.get(ParkZone, zone_id)
    if zone is None:
        raise NotFound("区域不存在")
    if db.query(Stall).filter(Stall.zone_id == zone_id).count():
        raise Conflict("该区域下存在档口，无法删除")
    db.delete(zone)
    db.flush()
    return ok({"deleted": True})


# --------------------------------------------------------------------------- 档口


@router.get("/stalls", response_model=ApiResponse[PageData[StallOut]], summary="档口列表")
def list_stalls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: Optional[int] = None,
    zone_id: Optional[int] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("park:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(Stall)
    if park_id:
        query = query.filter(Stall.park_id == park_id)
    if zone_id:
        query = query.filter(Stall.zone_id == zone_id)
    if status:
        query = query.filter(Stall.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(or_(Stall.name.like(like), Stall.code.like(like)))
    if not is_unrestricted(user):
        scope = park_scope_ids(db, user)
        if scope:
            query = query.filter(Stall.park_id.in_(scope))
    total = query.count()
    rows = query.order_by(Stall.code.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return ok(paginate([_stall_out(db, lk, row) for row in rows], total, page, page_size))


@router.post("/stalls", response_model=ApiResponse[StallOut], summary="创建档口")
def create_stall(
    payload: StallIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    if db.get(Park, payload.park_id) is None:
        raise NotFound("园区不存在")
    if db.query(Stall).filter(Stall.code == payload.code).first():
        raise Conflict(f"档口编码已存在：{payload.code}")
    if payload.zone_id:
        zone = db.get(ParkZone, payload.zone_id)
        if zone is None or zone.park_id != payload.park_id:
            raise BadRequest("区域不存在或不属于该园区")
    stall = Stall(**payload.model_dump())
    db.add(stall)
    db.flush()
    return ok(_stall_out(db, lk, stall))


@router.get("/stalls/{stall_id}", response_model=ApiResponse[StallOut], summary="档口详情")
def get_stall(
    stall_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:read")),
) -> dict:
    stall = db.get(Stall, stall_id)
    if stall is None:
        raise NotFound("档口不存在")
    return ok(_stall_out(db, lk, stall))


@router.put("/stalls/{stall_id}", response_model=ApiResponse[StallOut], summary="更新档口")
def update_stall(
    stall_id: int,
    payload: StallUpdate,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    stall = db.get(Stall, stall_id)
    if stall is None:
        raise NotFound("档口不存在")
    data = payload.model_dump(exclude_unset=True)
    if data.get("zone_id"):
        zone = db.get(ParkZone, data["zone_id"])
        if zone is None or zone.park_id != stall.park_id:
            raise BadRequest("区域不存在或不属于该园区")
    for field, value in data.items():
        setattr(stall, field, value)
    db.flush()
    return ok(_stall_out(db, lk, stall))


@router.delete("/stalls/{stall_id}", response_model=ApiResponse[dict], summary="删除档口")
def delete_stall(
    stall_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require("park:write")),
) -> dict:
    stall = db.get(Stall, stall_id)
    if stall is None:
        raise NotFound("档口不存在")
    if stall.status == "rented":
        raise Conflict("档口处于出租状态，请先退租")
    if db.query(ParkContract).filter(ParkContract.stall_id == stall_id).count():
        raise Conflict("该档口存在入驻合同记录，无法删除")
    db.delete(stall)
    db.flush()
    return ok({"deleted": True})


@router.post("/stalls/{stall_id}/assign", response_model=ApiResponse[StallOut], summary="档口入驻/退租")
def assign_stall(
    stall_id: int,
    payload: StallAssignIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    stall = db.get(Stall, stall_id)
    if stall is None:
        raise NotFound("档口不存在")
    if payload.enterprise_id is None:
        if stall.enterprise_id:
            enterprise = db.get(Enterprise, stall.enterprise_id)
            if enterprise is not None and enterprise.stall_id == stall.id:
                enterprise.stall_id = None
        stall.enterprise_id = None
        stall.status = "free"
    else:
        enterprise = db.get(Enterprise, payload.enterprise_id)
        if enterprise is None:
            raise NotFound("企业不存在")
        if stall.enterprise_id and stall.enterprise_id != enterprise.id:
            raise Conflict("档口已被其他企业占用")
        if enterprise.stall_id and enterprise.stall_id != stall.id:
            raise Conflict("该企业已占用其他档口，请先退租")
        stall.enterprise_id = enterprise.id
        stall.status = "rented"
        enterprise.stall_id = stall.id
        if not enterprise.park_id:
            enterprise.park_id = stall.park_id
    stall.remark = payload.remark or stall.remark
    db.flush()
    return ok(_stall_out(db, lk, stall))


# --------------------------------------------------------------------------- 园区合同


@router.get("/park-contracts", response_model=ApiResponse[PageData[ParkContractOut]], summary="园区合同列表")
def list_park_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    park_id: Optional[int] = None,
    enterprise_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    user: User = Depends(require("park:read")),
) -> dict:
    page, page_size = normalize_page(page, page_size)
    query = db.query(ParkContract)
    if park_id:
        query = query.filter(ParkContract.park_id == park_id)
    if enterprise_id:
        query = query.filter(ParkContract.enterprise_id == enterprise_id)
    if status:
        query = query.filter(ParkContract.status == status)
    if not is_unrestricted(user):
        scope = park_scope_ids(db, user)
        if scope:
            query = query.filter(ParkContract.park_id.in_(scope))
    total = query.count()
    rows = (
        query.order_by(ParkContract.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    )
    return ok(paginate([_park_contract_out(db, lk, row) for row in rows], total, page, page_size))


@router.post("/park-contracts", response_model=ApiResponse[ParkContractOut], summary="创建入驻合同")
def create_park_contract(
    payload: ParkContractIn,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    if db.get(Park, payload.park_id) is None:
        raise NotFound("园区不存在")
    if db.get(Enterprise, payload.enterprise_id) is None:
        raise NotFound("企业不存在")
    if payload.end_date <= payload.start_date:
        raise BadRequest("合同结束日期必须晚于开始日期")
    if payload.stall_id:
        stall = db.get(Stall, payload.stall_id)
        if stall is None:
            raise NotFound("档口不存在")
        if stall.park_id != payload.park_id:
            raise BadRequest("档口不属于所选园区")
    contract = ParkContract(
        contract_no=next_no(db, "park_contract", "GZ-PC"),
        **payload.model_dump(),
    )
    db.add(contract)
    db.flush()
    integration.enqueue(
        db,
        event_type="park_contract.created",
        aggregate_type="park_contract",
        aggregate_id=contract.contract_no,
        payload={
            "contract_no": contract.contract_no,
            "enterprise_id": contract.enterprise_id,
            "park_id": contract.park_id,
            "stall_id": contract.stall_id,
            "rent_amount": float(contract.rent_amount or 0),
            "start_date": contract.start_date.isoformat(),
            "end_date": contract.end_date.isoformat(),
        },
    )
    return ok(_park_contract_out(db, lk, contract))


@router.get("/park-contracts/{contract_id}", response_model=ApiResponse[ParkContractOut], summary="园区合同详情")
def get_park_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:read")),
) -> dict:
    contract = db.get(ParkContract, contract_id)
    if contract is None:
        raise NotFound("合同不存在")
    return ok(_park_contract_out(db, lk, contract))


@router.put("/park-contracts/{contract_id}", response_model=ApiResponse[ParkContractOut], summary="更新园区合同")
def update_park_contract(
    contract_id: int,
    payload: ParkContractUpdate,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    contract = db.get(ParkContract, contract_id)
    if contract is None:
        raise NotFound("合同不存在")
    if contract.status in ("terminated", "expired"):
        raise BadRequest("已终止或过期的合同不可修改")
    data = payload.model_dump(exclude_unset=True)
    start = data.get("start_date", contract.start_date)
    end = data.get("end_date", contract.end_date)
    if start and end and end <= start:
        raise BadRequest("合同结束日期必须晚于开始日期")
    for field, value in data.items():
        setattr(contract, field, value)
    db.flush()
    return ok(_park_contract_out(db, lk, contract))


@router.post("/park-contracts/{contract_id}/effect", response_model=ApiResponse[ParkContractOut], summary="合同生效并占用档口")
def effect_park_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    lk: Lookups = Depends(get_lookups),
    _: User = Depends(require("park:write")),
) -> dict:
    contract = db.get(ParkContract, contract_id)
    if contract is None:
        raise NotFound("合同不存在")
    if contract.status == "effective":
        raise Conflict("合同已生效")
    if contract.stall_id:
        stall = db.get(Stall, contract.stall_id)
        if stall is None:
            raise NotFound("档口不存在")
        if stall.enterprise_id and stall.enterprise_id != contract.enterprise_id:
            raise Conflict("档口已被其他企业占用")
        stall.enterprise_id = contract.enterprise_id
        stall.status = "rented"
        enterprise = db.get(Enterprise, contract.enterprise_id)
        if enterprise is not None:
            enterprise.stall_id = stall.id
            enterprise.park_id = contract.park_id
    contract.status = "effective"
    contract.signed_at = now()
    db.flush()
    integration.enqueue(
        db,
        event_type="park_contract.effective",
        aggregate_type="park_contract",
        aggregate_id=contract.contract_no,
        payload={"contract_no": contract.contract_no, "status": contract.status},
    )
    return ok(_park_contract_out(db, lk, contract))
