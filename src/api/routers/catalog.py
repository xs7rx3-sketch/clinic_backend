from fastapi import APIRouter, Query
from src.database.queries import fetch_catalog_data
from tests.test_helpers import get_live_test_entities

router = APIRouter(prefix="/api", tags=["Catalog & Entities"])


@router.get("/entities")
async def get_entities():
    """Returns real default test entities (Normal Patient, VIP Patient, Doctors, Hospital)."""
    entities = get_live_test_entities()
    return {"status": "success", "data": entities or {}}


@router.get("/catalog")
async def get_catalog(
    doctor_limit: int = Query(30, ge=1, le=100, description="Max doctors to return"),
):
    """Returns list of hospital departments and active doctors."""
    catalog = fetch_catalog_data(doc_limit=doctor_limit)
    return {
        "status": "success",
        "departments": catalog.get("departments", []),
        "doctors": catalog.get("doctors", []),
    }
