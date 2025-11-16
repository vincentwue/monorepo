#!/usr/bin/env python3
"""
Search for a string across ALL databases and collections
for multiple MongoDB connection URIs.

Requirements:
    pip install pymongo
"""

from typing import Any, List, Dict
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# -------------------------------------------------------------------
# CONFIG: adjust these
# -------------------------------------------------------------------

SEARCH_TERM = "sdfff"  # <-- your search term here

CONNECTION_STRINGS = [
    # "mongodb://localhost:27017",
    "mongodb://localhost:27025",
    "mongodb://localhost:27017",
    # "mongodb://user:password@host:27017/?authSource=admin",
    # add more here...
]

MAX_DOCS_PER_COLLECTION = None  # Optional doc limit per collection


# -------------------------------------------------------------------
# SEARCH UTILS
# -------------------------------------------------------------------

def search_value(value: Any, needle_lower: str, path: str, matches: List[Dict[str, Any]]):
    """Recursively search any MongoDB value."""
    # scalar types
    if isinstance(value, (str, int, float, bool)):
        if needle_lower in str(value).lower():
            matches.append({"path": path, "value": value})
        return

    # arrays
    if isinstance(value, list):
        for idx, item in enumerate(value):
            child_path = f"{path}[{idx}]" if path else f"[{idx}]"
            search_value(item, needle_lower, child_path, matches)
        return

    # subdocuments
    if isinstance(value, dict):
        for key, val in value.items():
            child_path = f"{path}.{key}" if path else key
            search_value(val, needle_lower, child_path, matches)
        return

    # everything else → string conversion
    text = str(value)
    if needle_lower in text.lower():
        matches.append({"path": path, "value": text})


def search_document(doc: Dict[str, Any], needle: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    needle_lower = needle.lower()

    for key, value in doc.items():
        search_value(value, needle_lower, key, matches)

    return matches


# -------------------------------------------------------------------
# MAIN SEARCH ROUTINE
# -------------------------------------------------------------------

def search_connection(uri: str, search: str):
    print(f"\n==============================")
    print(f"Connecting to: {uri}")
    print(f"Search term  : {search}")
    print(f"==============================")

    try:
        client = MongoClient(uri)
        db_names = client.list_database_names()
    except PyMongoError as e:
        print(f"[ERROR] Could not connect to {uri}: {e}")
        return

    for db_name in db_names:
        db = client[db_name]

        try:
            coll_names = db.list_collection_names()
        except PyMongoError as e:
            print(f"[ERROR] Cannot list collections for {db_name}: {e}")
            continue

        printed_db_header = False

        for coll_name in coll_names:
            coll = db[coll_name]

            try:
                cursor = coll.find({})
            except PyMongoError:
                continue  # skip unreadable/invalid collections

            match_count = 0

            try:
                for idx, doc in enumerate(cursor):
                    if MAX_DOCS_PER_COLLECTION is not None and idx >= MAX_DOCS_PER_COLLECTION:
                        break

                    matches = search_document(doc, search)
                    if matches:
                        if not printed_db_header:
                            printed_db_header = True
                            print(f"\n--- Database: {db_name} ---")

                        if match_count == 0:
                            print(f"\nCollection: {coll_name}")

                        match_count += 1

                        print(f"\n>>> MATCH #{match_count}")
                        print(f"_id: {doc.get('_id')}")
                        for m in matches:
                            print(f"  {m['path']}: {m['value']}")
            finally:
                cursor.close()

        # if no match at all in this DB → nothing printed


def main():
    for uri in CONNECTION_STRINGS:
        search_connection(uri, SEARCH_TERM)

    print("\nSearch completed.")


if __name__ == "__main__":
    main()