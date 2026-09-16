from django.db import models
from django.utils import timezone
import json

class SimulatorConfig(models.Model):
    """
    Singleton configuration for EMSP simulator identity, tokens, and endpoints.
    """
    cpo_url = models.CharField(max_length=255, default='https://test.vidyutyatraa.co.in', help_text='Live VidyutYatraa CPO Base URL')
    public_base_url = models.CharField(max_length=255, blank=True, default='', help_text='External routable base URL for callbacks (e.g. http://13.232.241.179:8000)')
    token_a = models.CharField(max_length=128, default='REPLACE_WITH_YOUR_BOOTSTRAP_TOKEN', help_text='Token A (Bootstrap handshake token)')
    token_b = models.CharField(max_length=128, default='9e30083e464bec1ddee8e08e5342095d4ea9e1f4a13ba137', help_text='Token B (EMSP uses this to call CPO)')
    token_c = models.CharField(max_length=128, default='emsp-callback-token-secret', help_text='Token C (CPO uses this when calling EMSP)')
    party_id = models.CharField(max_length=3, default='ION', help_text='EMSP Party ID (e.g. ION, SAV, HUB)')
    country_code = models.CharField(max_length=2, default='IN', help_text='EMSP Country Code')
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def bootstrap_token(self):
        return self.token_a

    @bootstrap_token.setter
    def bootstrap_token(self, value):
        self.token_a = value

    @classmethod
    def get_config(cls):
        cfg, _ = cls.objects.get_or_create(id=1)
        return cfg

    def __str__(self):
        return f"EMSP Config ({self.country_code}-{self.party_id}) -> CPO: {self.cpo_url}"


class CommandCallback(models.Model):
    """
    Stores asynchronous CommandResult callbacks delivered by CPO to response_url.
    """
    command_id = models.CharField(max_length=64, blank=True, db_index=True)
    command_type = models.CharField(max_length=32, default='START_SESSION', help_text='START_SESSION or STOP_SESSION')
    result = models.CharField(max_length=32, db_index=True, help_text='ACCEPTED, REJECTED, EVSE_INOPERATIVE, FAILED, etc.')
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f"Callback [{self.result}] for {self.command_type} at {self.received_at.strftime('%Y-%m-%d %H:%M:%S')}"


class ChargingSession(models.Model):
    """
    Stores live charging sessions pushed by CPO (PUT/PATCH /sessions).
    """
    session_id = models.CharField(max_length=64, unique=True, db_index=True)
    country_code = models.CharField(max_length=2, default='IN')
    party_id = models.CharField(max_length=3, default='VYT')
    start_date_time = models.CharField(max_length=64, blank=True)
    end_date_time = models.CharField(max_length=64, blank=True)
    kwh = models.FloatField(default=0.0)
    total_cost = models.FloatField(default=0.0)
    currency = models.CharField(max_length=5, default='INR')
    status = models.CharField(max_length=32, default='ACTIVE')
    raw_data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Session {self.session_id} [{self.status}] {self.kwh} kWh"


class ChargeDetailRecord(models.Model):
    """
    Stores finalized Charge Detail Records (CDRs) pushed by CPO.
    """
    cdr_id = models.CharField(max_length=64, unique=True, db_index=True)
    session_id = models.CharField(max_length=64, blank=True, db_index=True)
    start_date_time = models.CharField(max_length=64, blank=True)
    end_date_time = models.CharField(max_length=64, blank=True)
    total_energy = models.FloatField(default=0.0)
    total_cost = models.FloatField(default=0.0)
    currency = models.CharField(max_length=5, default='INR')
    raw_data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"CDR {self.cdr_id} ({self.total_energy} kWh, {self.currency} {self.total_cost})"


class AuditLog(models.Model):
    """
    Audit log for tracking all incoming and outgoing OCPI HTTP requests.
    """
    DIRECTION_CHOICES = [
        ('IN', 'CPO -> EMSP (Received)'),
        ('OUT', 'EMSP -> CPO (Dispatched)'),
    ]
    direction = models.CharField(max_length=4, choices=DIRECTION_CHOICES)
    module = models.CharField(max_length=32, default='general')
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10, default='POST')
    status_code = models.IntegerField(null=True, blank=True)
    summary = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.direction} {self.method} {self.endpoint} [{self.status_code}]"

