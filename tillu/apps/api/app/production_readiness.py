"""Truthful production-readiness diagnostics; never marks untested services verified."""
from pathlib import Path
from .config import settings
from .providers import gateway
from .cloud import cloud

REQUIRED_MIGRATIONS=tuple(f'{n:03d}_' for n in range(1,17))

def report()->dict:
    migration_dir=Path(__file__).resolve().parents[3]/'supabase'/'migrations';files=[x.name for x in migration_dir.glob('*.sql')]
    migrations={prefix:any(name.startswith(prefix) for name in files) for prefix in REQUIRED_MIGRATIONS}
    checks={
      'production_environment':settings.environment=='production',
      'supabase_url':bool(settings.supabase_url),
      'supabase_service_role':bool(settings.supabase_service_role_key),
      'owner_user_id':bool(settings.owner_user_id),
      'owner_email':bool(settings.owner_email),
      'restricted_cors':bool(settings.cors_origins) and '*' not in settings.cors_origins and 'localhost' not in settings.cors_origins,
      'public_https_url':settings.public_app_url.startswith('https://'),
      'cron_secret':len(settings.cron_secret)>=24,
      'runtime_internal_url':settings.runtime_internal_url.startswith('https://'),
      'internal_service_secret':len(settings.tillu_internal_secret)>=24,
      'rpc_capability_secret':len(settings.rpc_capability_secret)>=32,
      'backup_encryption_key':len(settings.backup_encryption_key)>=32,
      'hosted_ai_provider':any(x.configured for x in gateway.providers()),
      'honcho_required_config':bool(settings.honcho_required and settings.honcho_api_key and settings.honcho_workspace_id and settings.honcho_base_url),
      'all_migrations_present':all(migrations.values()),
      'supabase_client_initialized':cloud.enabled,
    }
    integrations={
      'web_push_configured':bool(settings.vapid_public_key and settings.vapid_private_key),
      'gmail_configured':bool(settings.google_client_id and settings.google_client_secret and settings.gmail_refresh_token),
      'whatsapp_configured':bool(settings.whatsapp_access_token and settings.whatsapp_phone_number_id),
      'honcho_configured':bool(settings.honcho_api_key and settings.honcho_workspace_id),
    }
    blockers=[k for k,v in checks.items() if not v]
    return {'ready':not blockers,'checks':checks,'blockers':blockers,'integrations':integrations,'migrations':migrations,'verification':{'supabase_connectivity':'not_tested' if not cloud.enabled else 'client_initialized_only','rls':'not_tested','cron':'not_tested','web_push_delivery':'not_tested','gmail_delivery':'not_tested','whatsapp_delivery':'not_tested','honcho':'configured_not_live_tested' if settings.honcho_api_key else 'not_configured'},'note':'Configured does not mean live-verified. Use service tests and authenticated RLS probes before release.'}
