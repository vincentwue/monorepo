from bson import ObjectId

def serialize_doc(doc):
    doc = dict(doc)
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

def serialize_docs(docs):
    return [serialize_doc(d) for d in docs]
