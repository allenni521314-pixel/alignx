import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.ad_data import Ad_data
from models.products import Products
from schemas.opc_os import CapitalDecisionInput, EvidenceInput, KnowledgeEvolutionInput, ListingActionCandidate
from services.ad_data import Ad_dataService
from services.opc_os_persistence import OPCOSPersistenceService
from services.opc_os_v5 import OPCOSV5ExecutionService
from dependencies.auth import get_current_user, get_user_scope_ids
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/ad_data", tags=["ad_data"])


# ---------- Pydantic Schemas ----------
class Ad_dataData(BaseModel):
    """Entity data schema (for create/update)"""
    product_id: int
    hypothesis_id: Optional[str] = None
    keyword_group_id: Optional[str] = None
    optimization_round: Optional[int] = 1
    ad_group_name: str
    keyword: str
    match_type: str = None
    impressions: int = None
    clicks: int = None
    spend: float = None
    orders: int = None
    sales: float = None
    date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Ad_dataUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    product_id: Optional[int] = None
    hypothesis_id: Optional[str] = None
    keyword_group_id: Optional[str] = None
    optimization_round: Optional[int] = None
    ad_group_name: Optional[str] = None
    keyword: Optional[str] = None
    match_type: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    spend: Optional[float] = None
    orders: Optional[int] = None
    sales: Optional[float] = None
    date: Optional[datetime] = None
    created_at: Optional[datetime] = None


class Ad_dataResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    product_id: int
    hypothesis_id: Optional[str] = None
    keyword_group_id: Optional[str] = None
    optimization_round: Optional[int] = None
    ad_group_name: str
    keyword: str
    match_type: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    spend: Optional[float] = None
    orders: Optional[int] = None
    sales: Optional[float] = None
    date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Ad_dataListResponse(BaseModel):
    """List response schema"""
    items: List[Ad_dataResponse]
    total: int
    skip: int
    limit: int


class Ad_dataBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Ad_dataData]


class Ad_dataBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Ad_dataUpdateData


class Ad_dataBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Ad_dataBatchUpdateItem]


class Ad_dataBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


class Ad_dataBindHypothesisRequest(BaseModel):
    """Bind ad records to a validation hypothesis."""
    product_id: int
    hypothesis_id: str
    ids: Optional[List[int]] = None
    keyword_group_id: Optional[str] = None
    optimization_round: Optional[int] = None
    only_unassigned: bool = True


class Ad_dataBindHypothesisResponse(BaseModel):
    updated_count: int
    hypothesis_id: str
    product_id: int
    updated_ids: List[int]
    skipped_count: int
    evidence: Optional[dict] = None
    capital_decision: Optional[dict] = None
    listing_actions: Optional[List[dict]] = None
    knowledge_evolution: Optional[dict] = None


def _listing_actions_from_ad_evidence(
    *,
    opportunity_id: str,
    evidence_id: str,
    impressions: int,
    clicks: int,
    orders: int,
    spend: float,
    roi: float,
) -> list[ListingActionCandidate]:
    actions: list[ListingActionCandidate] = []
    ctr = clicks / impressions * 100 if impressions else 0
    cvr = orders / clicks * 100 if clicks else 0
    if impressions > 0 and ctr < 1:
        actions.append(
            ListingActionCandidate(
                opportunity_id=opportunity_id,
                source_evidence_id=evidence_id,
                field="标题/主图",
                priority=1,
            )
        )
    if clicks > 0 and cvr < 5:
        actions.append(
            ListingActionCandidate(
                opportunity_id=opportunity_id,
                source_evidence_id=evidence_id,
                field="五点/A+",
                priority=2,
            )
        )
    if spend > 0 and roi <= 0:
        actions.append(
            ListingActionCandidate(
                opportunity_id=opportunity_id,
                source_evidence_id=evidence_id,
                field="广告验证",
                priority=3,
            )
        )
    return actions


# ---------- Routes ----------
@router.get("", response_model=Ad_dataListResponse)
async def query_ad_datas(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query ad_datas with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying ad_datas: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Ad_dataService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")
        
        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.get_list(
            skip=skip, 
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=scope_user_ids,
        )
        logger.debug(f"Found {result['total']} ad_datas")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying ad_datas: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Ad_dataListResponse)
async def query_ad_datas_all(
    query: str = Query(None, description="Query conditions (JSON string)"),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Query ad_datas with filtering, sorting, and pagination current user only
    logger.debug(f"Querying ad_datas: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Ad_dataService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")

        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.get_list(
            skip=skip,
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=scope_user_ids
        )
        logger.debug(f"Found {result['total']} ad_datas")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying ad_datas: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Ad_dataResponse)
async def get_ad_data(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single ad_data by ID (user can only see their own records)"""
    logger.debug(f"Fetching ad_data with id: {id}, fields={fields}")
    
    service = Ad_dataService(db)
    try:
        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.get_by_id(id, user_id=scope_user_ids)
        if not result:
            logger.warning(f"Ad_data with id {id} not found")
            raise HTTPException(status_code=404, detail="Ad_data not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ad_data {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Ad_dataResponse, status_code=201)
async def create_ad_data(
    data: Ad_dataData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new ad_data"""
    logger.debug(f"Creating new ad_data with data: {data}")
    
    service = Ad_dataService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create ad_data")
        
        logger.info(f"Ad_data created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating ad_data: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating ad_data: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Ad_dataResponse], status_code=201)
async def create_ad_datas_batch(
    request: Ad_dataBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple ad_datas in a single request"""
    logger.debug(f"Batch creating {len(request.items)} ad_datas")
    
    service = Ad_dataService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} ad_datas successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Ad_dataResponse])
async def update_ad_datas_batch(
    request: Ad_dataBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple ad_datas in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} ad_datas")
    
    service = Ad_dataService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            scope_user_ids = await get_user_scope_ids(current_user, db)
            result = await service.update(item.id, update_dict, user_id=scope_user_ids)
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} ad_datas successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.post("/bind-hypothesis", response_model=Ad_dataBindHypothesisResponse)
async def bind_ad_data_hypothesis(
    request: Ad_dataBindHypothesisRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bind a product's ad records to a diagnosis validation hypothesis.

    Use this for the core AlignX loop: diagnosis hypothesis -> ad validation ->
    feedback learning. By default it only updates unattributed records so older
    verified attribution is not overwritten accidentally.
    """

    hypothesis_id = request.hypothesis_id.strip()
    if not hypothesis_id:
        raise HTTPException(status_code=400, detail="hypothesis_id is required")
    if not request.ids and not request.keyword_group_id:
        raise HTTPException(status_code=400, detail="ids or keyword_group_id is required")

    scope_user_ids = await get_user_scope_ids(current_user, db)
    product_result = await db.execute(
        select(Products).where(
            Products.id == request.product_id,
            Products.user_id.in_(scope_user_ids),
        )
    )
    product = product_result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in current email identity scope")

    stmt = select(Ad_data).where(
        Ad_data.user_id.in_(scope_user_ids),
        Ad_data.product_id == request.product_id,
    )
    if request.ids:
        stmt = stmt.where(Ad_data.id.in_(request.ids))
    if request.keyword_group_id:
        stmt = stmt.where(Ad_data.keyword_group_id == request.keyword_group_id)
    if request.optimization_round is not None:
        stmt = stmt.where(Ad_data.optimization_round == request.optimization_round)
    if request.only_unassigned:
        stmt = stmt.where((Ad_data.hypothesis_id.is_(None)) | (Ad_data.hypothesis_id == "") | (Ad_data.hypothesis_id == "unassigned"))

    try:
        result = await db.execute(stmt)
        records = list(result.scalars().all())
        updated_ids: List[int] = []
        for record in records:
            record.hypothesis_id = hypothesis_id
            updated_ids.append(record.id)
        await db.commit()
        skipped_count = max(0, len(request.ids or []) - len(updated_ids)) if request.ids else 0
        impressions = sum(int(item.impressions or 0) for item in records)
        clicks = sum(int(item.clicks or 0) for item in records)
        orders = sum(int(item.orders or 0) for item in records)
        spend = sum(float(item.spend or 0) for item in records)
        sales = sum(float(item.sales or 0) for item in records)
        ctr = round(clicks / impressions * 100, 2) if impressions else 0
        cvr = round(orders / clicks * 100, 2) if clicks else 0
        roi = round(sales / spend, 2) if spend else 0
        roi_score = max(0, min(100, roi * 20))
        opc_service = OPCOSV5ExecutionService(str(current_user.id))
        evidence = opc_service.score_evidence(
            EvidenceInput(
                proof_plan_id=hypothesis_id,
                metrics={
                    "CTR": ctr,
                    "CVR": cvr,
                    "订单": min(100, orders),
                    "转化": cvr,
                    "ROI": roi_score,
                },
                evidence_quality=100 if records else 0,
            )
        )
        capital_decision = opc_service.create_capital_decision(
            CapitalDecisionInput(
                opportunity_id=hypothesis_id,
                proof_score=evidence.proof_score,
                risk_score=max(0, 100 - evidence.proof_score),
                information_gain=100 if records else 0,
            )
        )
        listing_actions = _listing_actions_from_ad_evidence(
            opportunity_id=hypothesis_id,
            evidence_id=evidence.evidence_id,
            impressions=impressions,
            clicks=clicks,
            orders=orders,
            spend=spend,
            roi=roi,
        )
        knowledge_evolution = opc_service.evolve_knowledge_graph(
            KnowledgeEvolutionInput(
                opportunity_id=hypothesis_id,
                evidence_id=evidence.evidence_id,
            )
        )
        persistence = OPCOSPersistenceService(db)
        await persistence.save_object(
            user_id=str(current_user.id),
            object_type="evidence",
            payload=evidence,
            opportunity_id=hypothesis_id,
            source_module="ad_data",
            source_record_id=request.product_id,
            asin=product.asin or "",
            title=product.title or "",
        )
        await persistence.save_object(
            user_id=str(current_user.id),
            object_type="capital_decision",
            payload=capital_decision,
            opportunity_id=hypothesis_id,
            source_module="ad_data",
            source_record_id=request.product_id,
            asin=product.asin or "",
            title=product.title or "",
        )
        for action in listing_actions:
            await persistence.save_object(
                user_id=str(current_user.id),
                object_type="listing_action",
                payload=action,
                opportunity_id=hypothesis_id,
                source_module="ad_data",
                source_record_id=request.product_id,
                asin=product.asin or "",
                title=product.title or "",
            )
        await persistence.save_object(
            user_id=str(current_user.id),
            object_type="knowledge_evolution",
            payload=knowledge_evolution,
            opportunity_id=hypothesis_id,
            source_module="ad_data",
            source_record_id=request.product_id,
            asin=product.asin or "",
            title=product.title or "",
        )
        return Ad_dataBindHypothesisResponse(
            updated_count=len(updated_ids),
            hypothesis_id=hypothesis_id,
            product_id=request.product_id,
            updated_ids=updated_ids,
            skipped_count=skipped_count,
            evidence=evidence.model_dump(mode="json"),
            capital_decision=capital_decision.model_dump(mode="json"),
            listing_actions=[item.model_dump(mode="json") for item in listing_actions],
            knowledge_evolution=knowledge_evolution.model_dump(mode="json"),
        )
    except Exception as e:
        await db.rollback()
        logger.error(f"Error binding ad_data hypothesis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Bind hypothesis failed: {str(e)}")


@router.put("/{id}", response_model=Ad_dataResponse)
async def update_ad_data(
    id: int,
    data: Ad_dataUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing ad_data (requires ownership)"""
    logger.debug(f"Updating ad_data {id} with data: {data}")

    service = Ad_dataService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        scope_user_ids = await get_user_scope_ids(current_user, db)
        result = await service.update(id, update_dict, user_id=scope_user_ids)
        if not result:
            logger.warning(f"Ad_data with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Ad_data not found")
        
        logger.info(f"Ad_data {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating ad_data {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating ad_data {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_ad_datas_batch(
    request: Ad_dataBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple ad_datas by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} ad_datas")
    
    service = Ad_dataService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            scope_user_ids = await get_user_scope_ids(current_user, db)
            success = await service.delete(item_id, user_id=scope_user_ids)
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} ad_datas successfully")
        return {"message": f"Successfully deleted {deleted_count} ad_datas", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_ad_data(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single ad_data by ID (requires ownership)"""
    logger.debug(f"Deleting ad_data with id: {id}")
    
    service = Ad_dataService(db)
    try:
        scope_user_ids = await get_user_scope_ids(current_user, db)
        success = await service.delete(id, user_id=scope_user_ids)
        if not success:
            logger.warning(f"Ad_data with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Ad_data not found")
        
        logger.info(f"Ad_data {id} deleted successfully")
        return {"message": "Ad_data deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ad_data {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
