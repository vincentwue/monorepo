from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from pymongo import MongoClient
from typing import List

router = APIRouter(prefix="/mongo", tags=["mongo"])

class ConnectionBody(BaseModel):
    uri: str

@router.get("/databases")
def list_databases(uri: str = Query(..., description="MongoDB URI")) -> List[str]:
    """Return all databases for the given connection URI"""
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        dbs = client.list_database_names()
        client.close()
        return dbs
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/collections")
def list_collections(
    uri: str = Query(...),
    db: str = Query(...),
) -> List[str]:
    """Return all collections in the given database"""
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=2000)
        collections = client[db].list_collection_names()
        client.close()
        return collections
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
