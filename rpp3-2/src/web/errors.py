"""
Обработчик доменных исключений.
Транслирует бизнес-ошибки в HTTP-коды согласно Таблице 7 методического руководства.
"""
from flask import jsonify
from domain.exceptions import (
    TransitionNotAllowed,
    InvariantViolation,
    EntityNotFound,
    ClockMovedBack,
    GatewayUnresolved,
)


def register_error_handlers(app):
    """Зарегистрировать обработчики ошибок в Flask-приложении."""

    @app.errorhandler(TransitionNotAllowed)
    def handle_transition_not_allowed(error):
        """409 Conflict — событие недопустимо в текущем состоянии."""
        return jsonify({
            "error": "TRANSITION_NOT_ALLOWED",
            "message": str(error)
        }), 409

    @app.errorhandler(InvariantViolation)
    def handle_invariant_violation(error):
        """422 Unprocessable Content — нарушение инварианта."""
        return jsonify({
            "error": "INVARIANT_VIOLATION",
            "message": str(error)
        }), 422

    @app.errorhandler(EntityNotFound)
    def handle_entity_not_found(error):
        """404 Not Found — сущность не найдена."""
        return jsonify({
            "error": "ENTITY_NOT_FOUND",
            "message": str(error)
        }), 404

    @app.errorhandler(ClockMovedBack)
    def handle_clock_moved_back(error):
        """422 Unprocessable Content — перевод часов назад запрещён."""
        return jsonify({
            "error": "CLOCK_MOVED_BACK",
            "message": str(error)
        }), 422

    @app.errorhandler(GatewayUnresolved)
    def handle_gateway_unresolved(error):
        """500 Internal Server Error — шлюз не разрешился."""
        return jsonify({
            "error": "GATEWAY_UNRESOLVED",
            "message": str(error)
        }), 500

    @app.errorhandler(400)
    def handle_bad_request(error):
        """400 Bad Request — некорректный запрос."""
        return jsonify({
            "error": "BAD_REQUEST",
            "message": str(error)
        }), 400

    @app.errorhandler(404)
    def handle_not_found(error):
        """404 Not Found — маршрут не найден."""
        return jsonify({
            "error": "NOT_FOUND",
            "message": "Маршрут не найден"
        }), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        """500 Internal Server Error — внутренняя ошибка сервера."""
        return jsonify({
            "error": "INTERNAL_ERROR",
            "message": "Внутренняя ошибка сервера"
        }), 500