from pymongo import MongoClient
from typing import Dict
from .config import settings

_connections: Dict[str, MongoClient] = {}

def get_client(alias: str = "default") -> MongoClient:
    if alias not in _connections:
        if alias in settings.mongo_connections:
            uri = settings.mongo_connections[alias]
        elif "default" in settings.mongo_connections:
            uri = settings.mongo_connections["default"]
        else:
            raise ValueError(f"No URI configured for alias '{alias}'")
        _connections[alias] = MongoClient(uri)
    return _connections[alias]

def list_aliases():
    return list(settings.mongo_connections.keys())

def list_databases(alias: str):
    return get_client(alias).list_database_names()

def list_collections(db_name: str, alias: str):
    return get_client(alias)[db_name].list_collection_names()

def get_collection(db_name: str, coll_name: str, alias: str):
    return get_client(alias)[db_name][coll_name]
