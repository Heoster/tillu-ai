import asyncio
import pytest
from app.capabilities import registry,ACTION_SCHEMAS,ACTION_LABELS,validate_action_payload


def test_every_action_has_one_canonical_typed_entry():
    actions=registry.catalog('action')
    assert {x['name'] for x in actions}==set(ACTION_SCHEMAS)==set(ACTION_LABELS)
    assert all(x['approval_required'] and x['kind']=='action' for x in actions)
    assert all(x['input_schema']['additionalProperties'] is False for x in actions)


def test_action_payload_validation_is_fail_closed():
    assert validate_action_payload('delete_task',{'id':'abc'})=={'id':'abc'}
    assert validate_action_payload('delete_task',{}) is None
    assert validate_action_payload('delete_task',{'id':'abc','surprise':True}) is None
    assert validate_action_payload('not_registered',{}) is None


def test_action_cannot_execute_through_read_runtime():
    with pytest.raises(PermissionError):
        asyncio.run(registry.execute('delete_task',{'id':'abc'},'owner'))


def test_read_catalog_never_contains_actions():
    import app.orchestrator  # noqa: F401
    reads=registry.catalog('read')
    assert reads
    assert all(x['kind']=='read' and not x['approval_required'] for x in reads)
    assert not ({x['name'] for x in reads} & set(ACTION_SCHEMAS))
