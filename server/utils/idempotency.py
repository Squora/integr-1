import json
from models import IdempotencyKey

def check_idempotency(db, key, resource_type):
    if not key:
        return None
    record = db.query(IdempotencyKey).filter(
        IdempotencyKey.key == key,
        IdempotencyKey.resource_type == resource_type
    ).first()
    if record:
        return json.loads(record.response_data)
    return None

def store_idempotency(db, key, resource_type, response):
    if not key:
        return
    record = IdempotencyKey(
        key=key,
        resource_type=resource_type,
        response_data=json.dumps(response)
    )
    db.add(record)
    db.commit()