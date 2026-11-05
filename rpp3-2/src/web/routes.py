"""
Маршруты бизнес-операций процесса аренды электросамоката.
Каждой задаче BPMN-схемы соответствует отдельный маршрут.
"""
from datetime import datetime
from uuid import UUID

from flask import Blueprint, request, jsonify

from domain.exceptions import EntityNotFound
from web.dto import serialize_trip, serialize_scooter, serialize_user


trips_bp = Blueprint("trips", __name__, url_prefix="/trips")
scooters_bp = Blueprint("scooters", __name__, url_prefix="/scooters")
users_bp = Blueprint("users", __name__, url_prefix="/users")
internal_bp = Blueprint("internal", __name__, url_prefix="/internal")


# =========================================================
# Маршруты для поездок (Trip)
# =========================================================

@trips_bp.route("/<trip_id>", methods=["GET"])
def get_trip(trip_id: str):
    """GET /trips/<id> — получить состояние поездки, допустимые события и журнал."""
    trip_service = trips_bp.trip_service
    trip = trip_service._trips.get_or_fail(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


@trips_bp.route("", methods=["POST"])
def request_booking():
    """POST /trips — забронировать самокат (начальный этап процесса)."""
    trip_service = trips_bp.trip_service
    data = request.get_json()
    
    scooter_id = UUID(data["scooter_id"])
    user_id = UUID(data["user_id"])
    
    trip_id = trip_service.request_booking(scooter_id, user_id)
    trip = trip_service._trips.get(trip_id)
    
    return jsonify(serialize_trip(trip)), 201


@trips_bp.route("/<trip_id>/check-debt", methods=["POST"])
def check_client_debt(trip_id: str):
    """POST /trips/<id>/check-debt — проверить задолженность клиента."""
    trip_service = trips_bp.trip_service
    trip_service.check_client_debt(UUID(trip_id))
    trip = trip_service._trips.get(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


@trips_bp.route("/<trip_id>/pause", methods=["POST"])
def pause_trip(trip_id: str):
    """POST /trips/<id>/pause — поставить поездку на паузу."""
    trip_service = trips_bp.trip_service
    trip_service.handle_client_request(UUID(trip_id), "pause")
    trip = trip_service._trips.get(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


@trips_bp.route("/<trip_id>/resume", methods=["POST"])
def resume_trip(trip_id: str):
    """POST /trips/<id>/resume — возобновить поездку после паузы."""
    trip_service = trips_bp.trip_service
    trip_service.resume_trip(UUID(trip_id))
    trip = trip_service._trips.get(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


@trips_bp.route("/<trip_id>/finish", methods=["POST"])
def finish_trip(trip_id: str):
    """POST /trips/<id>/finish — завершить поездку (с фото)."""
    trip_service = trips_bp.trip_service
    data = request.get_json()
    photo_ref = data.get("photo_ref", "photo.jpg")
    
    trip_service.handle_client_request(UUID(trip_id), "finish", photo_ref)
    trip = trip_service._trips.get(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


@trips_bp.route("/<trip_id>/operator-contact", methods=["POST"])
def record_operator_contact(trip_id: str):
    """POST /trips/<id>/operator-contact — зафиксировать связь оператора с клиентом."""
    trip_service = trips_bp.trip_service
    data = request.get_json()
    
    has_problem = data.get("has_problem", False)
    description = data.get("description", "")
    
    trip_service.record_operator_contact(UUID(trip_id), has_problem, description)
    trip = trip_service._trips.get(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


@trips_bp.route("/<trip_id>/resolve-support", methods=["POST"])
def resolve_support_request(trip_id: str):
    """POST /trips/<id>/resolve-support — закрыть обращение ответом оператора."""
    trip_service = trips_bp.trip_service
    data = request.get_json()
    
    resolution = data.get("resolution", "")
    trip_service.resolve_support_request(UUID(trip_id), resolution)
    trip = trip_service._trips.get(UUID(trip_id))
    return jsonify(serialize_trip(trip)), 200


# =========================================================
# Маршруты для самокатов (Scooter)
# =========================================================

@scooters_bp.route("/<scooter_id>", methods=["GET"])
def get_scooter(scooter_id: str):
    """GET /scooters/<id> — получить состояние самоката."""
    trip_service = scooters_bp.trip_service
    scooter = trip_service._scooters.get_or_fail(UUID(scooter_id))
    return jsonify(serialize_scooter(scooter)), 200


# =========================================================
# Маршруты для пользователей (User)
# =========================================================

@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id: str):
    """GET /users/<id> — получить состояние пользователя."""
    trip_service = users_bp.trip_service
    user = trip_service._users.get_or_fail(UUID(user_id))
    return jsonify(serialize_user(user)), 200


# =========================================================
# Служебные маршруты
# =========================================================

@internal_bp.route("/tick", methods=["POST"])
def tick():
    """POST /internal/tick — перевести часы приложения и проверить таймеры.
    Принимает JSON: {"now": "2026-10-01T10:00:00"} или пустое тело."""
    trip_service = internal_bp.trip_service
    clock = internal_bp.clock
    
    data = request.get_json(silent=True) or {}
    
    if "now" in data:
        # Перевести часы на указанное время
        target_time = datetime.fromisoformat(data["now"])
        clock.move_to(target_time)
    
    # Вызвать методы событий таймера для всех сущностей
    trip_service.on_tick()
    
    return jsonify({"status": "ok", "current_time": clock.now().isoformat()}), 200

# =========================================================
# Служебные маршруты для создания тестовых данных
# =========================================================

@internal_bp.route("/users", methods=["POST"])
def create_test_user():
    """POST /internal/users — создать тестового пользователя."""
    trip_service = internal_bp.trip_service
    data = request.get_json()
    
    from domain.user import User
    from decimal import Decimal
    
    user_id = UUID(data["user_id"])
    debt = Decimal(str(data.get("debt", 0)))
    
    user = User(user_id=user_id)
    if debt > 0:
        user.add_debt(debt)
    trip_service._users.save(user)
    
    return jsonify(serialize_user(user)), 201


@internal_bp.route("/scooters", methods=["POST"])
def create_test_scooter():
    """POST /internal/scooters — создать тестовый самокат."""
    trip_service = internal_bp.trip_service
    data = request.get_json()
    
    from domain.scooter import Scooter
    
    scooter_id = UUID(data["scooter_id"])
    battery_level = int(data.get("battery_level", 80))
    
    scooter = Scooter(scooter_id=scooter_id, _battery_level=battery_level)
    trip_service._scooters.save(scooter)
    
    return jsonify(serialize_scooter(scooter)), 201