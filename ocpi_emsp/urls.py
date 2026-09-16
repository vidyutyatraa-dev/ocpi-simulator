from django.urls import path
from . import views_ocpi, views_ui

urlpatterns = [
    # ── UI Dashboard & Polling ──
    path('', views_ui.dashboard_view, name='dashboard'),
    path('ui/action/handshake', views_ui.api_action_handshake, name='ui_handshake'),
    path('ui/action/locations', views_ui.api_action_locations, name='ui_locations'),
    path('ui/action/tariffs', views_ui.api_action_tariffs, name='ui_tariffs'),
    path('ui/action/register-token', views_ui.api_action_put_token, name='ui_register_token'),
    path('ui/action/start-session', views_ui.api_action_start_session, name='ui_start_session'),
    path('ui/action/stop-session', views_ui.api_action_stop_session, name='ui_stop_session'),
    path('ui/action/config', views_ui.api_action_update_config, name='ui_update_config'),

    path('ui/api/callbacks', views_ui.api_get_callbacks, name='api_callbacks'),
    path('ui/api/sessions', views_ui.api_get_sessions, name='api_sessions'),
    path('ui/api/logs', views_ui.api_get_logs, name='api_logs'),
    path('ui/api/clear-logs', views_ui.api_clear_logs, name='api_clear_logs'),

    # ── OCPI 2.2.1 Receiver Endpoints (Called by CPO / AWS Lambda) ──
    path('ocpi/versions', views_ocpi.ocpi_versions, name='ocpi_versions'),
    path('ocpi/emsp/2.2.1', views_ocpi.ocpi_version_details, name='ocpi_version_details'),
    path('ocpi/emsp/2.2.1/credentials', views_ocpi.ocpi_credentials, name='ocpi_credentials'),

    # Command Callbacks (CRITICAL for receiving async CommandResult)
    path('ocpi/emsp/2.2.1/commands/callback', views_ocpi.ocpi_command_callback, name='ocpi_command_callback'),
    path('ocpi/emsp/2.2.1/commands/<str:command_id>/callback', views_ocpi.ocpi_command_callback, name='ocpi_command_callback_with_id'),

    # Sessions Receiver (PUT on start, PATCH on meter readings)
    path('ocpi/emsp/2.2.1/sessions/<str:country_code>/<str:party_id>/<str:session_id>', views_ocpi.ocpi_session_receiver, name='ocpi_session_receiver_cc'),
    path('ocpi/emsp/2.2.1/sessions/<str:session_id>', views_ocpi.ocpi_session_receiver, name='ocpi_session_receiver_id'),

    # CDRs Receiver (POST on session completion)
    path('ocpi/emsp/2.2.1/cdrs', views_ocpi.ocpi_cdr_receiver, name='ocpi_cdr_receiver'),
    path('ocpi/emsp/2.2.1/cdrs/<str:cdr_id>', views_ocpi.ocpi_cdr_receiver, name='ocpi_cdr_receiver_id'),
]

