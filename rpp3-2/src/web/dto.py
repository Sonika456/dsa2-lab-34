"""
Сериализация доменных объектов в JSON-ответы.
Преобразует агрегаты и события в словари для HTTP-ответов.
"""
from datetime import datetime
from decimal import Decimal
from uuid import UUID


def serialize_trip(trip) -> dict:
    """Сериализовать агрегат Trip в JSON-совместимый словарь."""
    return {
        "trip_id": str(trip.trip_id),
        "scooter_id": str(trip.scooter_id),
        "user_id": str(trip.user_id),
        "status": trip.status,
        "allowed_events": list(trip.allowed_events),
        "created_at": trip.created_at.isoformat(),
        "start_time": trip.start_time.isoformat() if trip.start_time else None,
        "end_time": trip.end_time.isoformat() if trip.end_time else None,
        "photo_ref": trip.photo_ref,
        "lock_released": trip.lock_released,
        "billing_started": trip.billing_started,
        "total_pause_seconds": trip.total_pause_seconds,
        "operator_notified": trip.operator_notified,
        "operator_contacted": trip.operator_contacted,
        "events": [serialize_event(e) for e in trip.events]
    }


def serialize_event(event) -> dict:
    """Сериализовать доменное событие в JSON-совместимый словарь."""
    result = {
        "type": event.__class__.__name__,
        "occurred_at": event.occurred_at.isoformat()
    }
    
    # Добавляем поля события
    for field in event.__dataclass_fields__:
        if field == "occurred_at":
            continue
        value = getattr(event, field)
        if isinstance(value, UUID):
            result[field] = str(value)
        elif isinstance(value, Decimal):
            result[field] = str(value)
        elif isinstance(value, datetime):
            result[field] = value.isoformat()
        else:
            result[field] = value
    
    return result


def serialize_scooter(scooter) -> dict:
    """Сериализовать агрегат Scooter в JSON-совместимый словарь."""
    return {
        "scooter_id": str(scooter.scooter_id),
        "battery_level": scooter.battery_level,
        "status": scooter.status.value,
        "is_available_for_rent": scooter.is_available_for_rent
    }


def serialize_user(user) -> dict:
    """Сериализовать агрегат User в JSON-совместимый словарь."""
    return {
        "user_id": str(user.user_id),
        "debt": str(user.debt),
        "blocked": user.blocked,
        "has_debt": user.has_debt
    }