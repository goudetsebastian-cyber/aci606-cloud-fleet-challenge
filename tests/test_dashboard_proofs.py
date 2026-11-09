from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import event, update
from sqlalchemy.exc import OperationalError
from app.main import create_app
from app.db import TELEMETRY
from tests.test_service import SAMPLE


def test_proof_survives_restart_and_is_accessible_without_browser_storage(tmp_path):
    url = f"sqlite:///{(tmp_path / 'proof.db').as_posix()}"
    proof_id = 'a' * 32
    with TestClient(create_app(url)) as first:
        reference = first.post('/dashboard/proofs', json={'request_id': proof_id}).json()
        assert reference['count'] == 125
        assert len(reference['sha256']) == 64
        assert first.get('/dashboard/proofs/' + proof_id).json()['intact'] is True
        assert first.get('/dashboard/proofs/' + proof_id).json()['verified'] is False
        assert first.post('/dashboard/proofs', json={'request_id': proof_id}).json() == reference
        assert len(first.get('/dashboard/history/' + reference['robot_id']).json()) == 125
    with TestClient(create_app(url)) as another_device:
        assert reference in another_device.get('/dashboard/proofs').json()
        result = another_device.get('/dashboard/proofs/' + proof_id).json()
        assert result['verified'] is True
        assert result['after_instance_id'] != reference['before_instance_id']
        with another_device.app.state.storage.engine.begin() as conn:
            conn.execute(update(TELEMETRY).where(TELEMETRY.c.robot_id == reference['robot_id']).values(battery=0))
        assert another_device.get('/dashboard/proofs/' + proof_id).json()['intact'] is False


def test_proof_rolls_back_if_reference_cannot_be_saved(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'atomic.db').as_posix()}")) as client:
        def fail_reference(conn, cursor, statement, parameters, context, executemany):
            if statement.startswith('INSERT INTO persistence_proofs'):
                raise OperationalError('redacted', {}, Exception('failure'))
        event.listen(client.app.state.storage.engine, 'before_cursor_execute', fail_reference)
        assert client.post('/dashboard/proofs', json={'request_id':'b'*32}).status_code == 503
        assert client.get('/metrics').json()['stored_samples'] == 0
        assert client.get('/dashboard/proofs').json() == []


def test_proof_concurrent_replay_does_not_duplicate_samples(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'concurrent.db').as_posix()}")) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: client.post('/dashboard/proofs', json={'request_id':'c'*32}), range(2)))
        assert [r.status_code for r in responses] == [200, 200]
        assert responses[0].json() == responses[1].json()
        assert client.get('/metrics').json()['stored_samples'] == 125


def test_dashboard_controls_and_invalid_proof_ids(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'controls.db').as_posix()}")) as client:
        assert client.get('/dashboard').headers['cache-control'] == 'no-store'
        assert client.post('/dashboard/proofs', json={'request_id':'invalid'}).status_code == 422
        assert client.get('/dashboard/proofs/missing').status_code == 404
        assert client.get('/dashboard/scenario').status_code == 200
        assert client.post('/dashboard/predict', json=SAMPLE).status_code == 200
        assert client.post('/dashboard/telemetry', json=SAMPLE).status_code == 200
        assert client.post('/dashboard/telemetry', json={**SAMPLE,'battery':101}).status_code == 422
        metrics = client.get('/dashboard/data').json()['metrics']
        assert metrics['prediction_requests'] == 1
        assert metrics['telemetry_requests'] == 2
