from fastapi.testclient import TestClient

from backend.server import app


def test_ping_and_sim_state():
    with TestClient(app) as client:
        ping = client.get('/ping')
        assert ping.status_code == 200
        assert ping.json()['status'] == 'ok'

        sim = client.get('/api/sim')
        assert sim.status_code == 200
        payload = sim.json()
        assert 'running' in payload
        assert 'tick_seconds' in payload
        assert payload['max_memories'] >= 1


def test_smallville_compatible_endpoints():
    with TestClient(app) as client:
        create_location = client.post('/locations', json={'name': 'Workshop'})
        assert create_location.status_code == 200
        assert create_location.json()['success'] is True

        create_agent = client.post(
            '/agents',
            json={
                'name': 'John',
                'memories': ['likes fixing tools'],
                'location': 'Workshop',
                'activity': 'repairing gear',
            },
        )
        assert create_agent.status_code == 200
        assert create_agent.json()['success'] is True

        state = client.get('/state')
        assert state.status_code == 200
        payload = state.json()
        assert 'agents' in payload
        assert 'locations' in payload
        assert any(agent['name'] == 'John' for agent in payload['agents'])
        assert any(loc['name'] == 'Workshop' for loc in payload['locations'])
