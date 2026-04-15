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


def test_god_intervention_single_multiple_all():
    with TestClient(app) as client:
        # create two extra agents so target scopes are meaningful
        client.post('/locations', json={'name': 'Temple'})
        a1 = client.post('/agents', json={'name': 'Aster', 'memories': [], 'location': 'Temple', 'activity': 'watching sky'}).json()['agent']['id']
        a2 = client.post('/agents', json={'name': 'Bram', 'memories': [], 'location': 'Temple', 'activity': 'reading'}).json()['agent']['id']

        single = client.post('/api/interventions', json={'mode': 'single', 'agent_ids': [a1], 'message': 'A solar eclipse starts soon.'})
        assert single.status_code == 200
        assert single.json()['count'] == 1

        multiple = client.post('/api/interventions', json={'mode': 'multiple', 'agent_ids': [a1, a2], 'message': 'Meet near the square before dusk.'})
        assert multiple.status_code == 200
        assert multiple.json()['count'] == 2

        all_agents = client.post('/api/interventions', json={'mode': 'all', 'agent_ids': [], 'message': 'Rain will begin in one hour.'})
        assert all_agents.status_code == 200
        assert all_agents.json()['count'] >= 2

        detail = client.get(f'/api/agents/{a1}')
        memories = detail.json()['memories']
        assert any(m['source'] == 'god_intervention' for m in memories)
