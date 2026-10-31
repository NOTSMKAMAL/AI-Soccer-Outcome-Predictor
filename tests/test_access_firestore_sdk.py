"""Runs the quota against the real Firestore SDK with only its network layer mocked.

tests/test_access.py uses an in-memory fake, which can't catch misuse of the SDK
itself. Here the real client, transaction and retry decorator execute, and the
assertions read the requests that would have gone to Firestore.
"""
import inspect
import os
import sys
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from google.api_core.exceptions import Aborted
from google.auth.credentials import AnonymousCredentials
from google.cloud import firestore
from google.cloud.firestore_v1.collection import CollectionReference

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import access

PROJECT = "test-project"
DAY = "2026-10-30"
DAY_PATH = f"projects/{PROJECT}/databases/(default)/documents/prediction_quota_days/{DAY}"


@pytest.fixture
def client():
    """Real Firestore client whose gRPC layer is a mock; all documents start missing."""
    real = firestore.Client(project=PROJECT, credentials=AnonymousCredentials())
    api = MagicMock()
    api.begin_transaction.return_value.transaction = b"tx-1"
    api.batch_get_documents.return_value = iter([])
    api.commit.return_value.write_results = []
    real._firestore_api_internal = api
    return real


def _quota(client):
    return access.DailyQuota(client=lambda: client, today=lambda: DAY)


def _commit_request(client, call=0):
    return client._firestore_api.commit.call_args_list[call].kwargs["request"]


def test_consume_commits_both_counters_in_one_transaction(client):
    receipt, message = _quota(client).check_and_consume("user-a")

    assert message == ""
    assert receipt == access.QuotaReceipt(key="user-a", day=DAY)
    client._firestore_api.begin_transaction.assert_called_once()
    request = _commit_request(client)
    assert request["transaction"] == b"tx-1"
    assert {w.update.name for w in request["writes"]} == {DAY_PATH, f"{DAY_PATH}/users/user-a"}


def test_consume_writes_the_expected_counts(client):
    _quota(client).check_and_consume("user-a")

    writes = {w.update.name: w.update.fields for w in _commit_request(client)["writes"]}
    assert writes[DAY_PATH]["total"].integer_value == 1
    assert writes[DAY_PATH]["users"].integer_value == 1
    assert writes[f"{DAY_PATH}/users/user-a"]["count"].integer_value == 1


def test_contended_transaction_is_retried_and_counted_once(client):
    client._firestore_api.batch_get_documents.side_effect = lambda **kwargs: iter([])
    success = MagicMock(write_results=[])
    client._firestore_api.commit.side_effect = [Aborted("contention"), success]

    receipt, _ = _quota(client).check_and_consume("user-a")

    assert receipt is not None
    assert client._firestore_api.commit.call_count == 2


def test_stream_accepts_the_timeout_the_quota_passes():
    assert "timeout" in inspect.signature(CollectionReference.stream).parameters


def test_delete_user_counts_uses_real_sdk_paths_and_batch(client, monkeypatch):
    day_doc = MagicMock()
    day_doc.reference = client.collection("prediction_quota_days").document(DAY)
    monkeypatch.setattr(CollectionReference, "stream", lambda self, timeout=None: iter([day_doc]))

    _quota(client).delete_user_counts("user-a")

    writes = _commit_request(client)["writes"]
    assert [w.delete for w in writes] == [f"{DAY_PATH}/users/user-a"]


def test_failure_starting_a_transaction_fails_closed(client, monkeypatch, capsys):
    # The SDK's cleanup hides the real cause behind a ValueError about the
    # transaction ID, so DEPLOY.md lists that message under troubleshooting.
    client._firestore_api.begin_transaction.side_effect = RuntimeError("database does not exist")
    monkeypatch.setattr(access, "quota", _quota(client))

    with pytest.raises(HTTPException) as exc:
        access.enforce({"uid": "u1", "email": "a@example.com", "email_verified": True})

    assert exc.value.status_code == 503
    assert "[Quota] check failed: ValueError" in capsys.readouterr().out
