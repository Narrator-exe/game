from __future__ import annotations

import asyncio
import json
import os
import random
import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


@dataclass
class Memory:
    id: str
    timestamp: float
    text: str
    source: str
    importance: int


@dataclass
class Agent:
    id: str
    name: str
    x: int
    y: int
    location: str = "Town Square"
    current_action: str = "idle"
    mood: str = "neutral"
    emoji: str = "🙂"
    goals: List[str] = field(default_factory=list)
    memories: List[Memory] = field(default_factory=list)


@dataclass
class WorldObject:
    name: str
    state: str


@dataclass
class WorldLocation:
    name: str
    parent: Optional[str] = None
    objects: List[WorldObject] = field(default_factory=list)


@dataclass
class DialogueLine:
    name: str
    dialog: str


@dataclass
class Conversation:
    name: str
    other: str
    dialog: List[DialogueLine]


class AskRequest(BaseModel):
    question: str


class SimControl(BaseModel):
    running: bool


# Smallville-inspired request models for compatibility
class CreateAgentRequest(BaseModel):
    name: str
    memories: List[str] = Field(default_factory=list)
    location: str = "Town Square"
    activity: str = "idle"


class CreateLocationRequest(BaseModel):
    name: str
    parent: Optional[str] = None


class CreateObjectRequest(BaseModel):
    parent: str
    name: str
    state: str = "idle"


class AddObservationRequest(BaseModel):
    name: str
    observation: str
    reactable: bool = False


class GodInterventionRequest(BaseModel):
    message: str
    mode: str = "all"  # single | multiple | all
    agent_ids: List[str] = Field(default_factory=list)


EMOJIS = {
    "cook": "🍳",
    "walk": "🚶",
    "chat": "🗣️",
    "collect": "🧺",
    "rest": "🛌",
    "paint": "🎨",
    "eat": "🍽️",
    "think": "🤔",
}


class SimulationEngine:
    def __init__(self) -> None:
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "tinyllama:1.1b")
        self.tick_seconds = float(os.getenv("SIM_TICK_SECONDS", "8"))
        self.max_memories = int(os.getenv("MAX_MEMORIES", "48"))
        self.running = False
        self.tick_count = 0
        self.agents: Dict[str, Agent] = {}
        self.locations: Dict[str, WorldLocation] = {}
        self.conversations: List[Conversation] = []
        self._task: Optional[asyncio.Task] = None
        self._subscribers: Set[WebSocket] = set()

    def seed_world(self) -> None:
        for location in ["Town Square", "Red House", "Lake", "Market"]:
            self.locations[location] = WorldLocation(name=location)

        self.locations["Red House"].objects.append(WorldObject(name="Kitchen", state="available"))
        self.locations["Market"].objects.append(WorldObject(name="Oven", state="busy"))

    def seed_agents(self) -> None:
        seeds = [
            ("a1", "Maya", 2, 1, "Red House", "prepare lunch", ["prepare lunch", "check on Sam"]),
            ("a2", "Sam", 5, 2, "Market", "gather wood", ["gather wood", "eat something"]),
            ("a3", "Iris", 3, 4, "Lake", "paint by the lake", ["paint by the lake", "find berries"]),
        ]
        for agent_id, name, x, y, location, action, goals in seeds:
            agent = Agent(id=agent_id, name=name, x=x, y=y, location=location, current_action=action, goals=goals)
            agent.emoji = self._emoji_for_action(action)
            agent.memories.append(
                Memory(
                    id=str(uuid.uuid4()),
                    timestamp=time.time(),
                    text=f"{name} wakes up feeling ready for the day.",
                    source="init",
                    importance=5,
                )
            )
            self.agents[agent_id] = agent

    async def ollama_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                response.raise_for_status()
            return True
        except Exception:
            return False

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        if not self.locations:
            self.seed_world()
        if not self.agents:
            self.seed_agents()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self.running:
            await self.tick()
            await asyncio.sleep(self.tick_seconds)

    async def tick(self) -> None:
        self.tick_count += 1
        self.conversations = []
        for agent in list(self.agents.values()):
            observation = self._observe(agent)
            await self._remember(agent, observation, source="observation", importance=4)
            decision = await self._decide_next_action(agent, observation)
            agent.current_action = decision.get("action", "idle")
            agent.mood = decision.get("mood", agent.mood)
            agent.emoji = self._emoji_for_action(agent.current_action)
            self._move_agent(agent)
            await self._remember(
                agent,
                f"Decided to {agent.current_action} while feeling {agent.mood}.",
                source="decision",
                importance=6,
            )

        self._update_conversations()
        await self.broadcast(
            {
                "type": "tick",
                "tick": self.tick_count,
                "agents": [self._agent_summary(a) for a in self.agents.values()],
                "conversations": [self._conversation_to_dict(c) for c in self.conversations],
            }
        )

    def _observe(self, agent: Agent) -> str:
        nearby = []
        for other in self.agents.values():
            if other.id == agent.id:
                continue
            distance = abs(other.x - agent.x) + abs(other.y - agent.y)
            if distance <= 3:
                nearby.append(f"{other.name} is {other.current_action} at ({other.x},{other.y})")

        objects_here = self.locations.get(agent.location, WorldLocation(agent.location)).objects
        object_descriptions = [f"{obj.name} is {obj.state}" for obj in objects_here][:2]
        local_context = random.choice(
            [
                "smells fresh bread from a nearby house",
                "hears birds singing",
                "notices clouds getting darker",
                "spots edible herbs",
            ]
        )
        parts = [f"{agent.name} {local_context}"]
        if nearby:
            parts.append(f"sees: {'; '.join(nearby)}")
        if object_descriptions:
            parts.append(f"objects: {'; '.join(object_descriptions)}")
        return "; ".join(parts)

    async def _remember(self, agent: Agent, text: str, source: str, importance: int) -> None:
        memory = Memory(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            text=text,
            source=source,
            importance=importance,
        )
        agent.memories.append(memory)
        agent.memories = sorted(agent.memories, key=lambda m: m.timestamp)[-self.max_memories:]
        await self.broadcast(
            {
                "type": "memory",
                "agent_id": agent.id,
                "memory": self._memory_to_dict(memory),
            }
        )

    def _recent_relevant_memories(self, agent: Agent, limit: int = 6) -> List[Memory]:
        return sorted(agent.memories, key=lambda m: (m.importance, m.timestamp), reverse=True)[:limit]

    async def _decide_next_action(self, agent: Agent, observation: str) -> Dict[str, str]:
        memories = self._recent_relevant_memories(agent)
        prompt = {
            "agent": {
                "name": agent.name,
                "goals": agent.goals,
                "current_action": agent.current_action,
                "mood": agent.mood,
                "location": agent.location,
            },
            "observation": observation,
            "memories": [m.text for m in memories],
            "instruction": "Return compact JSON only with keys action,mood,reason. Make action concrete and physical.",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": json.dumps(prompt),
                        "stream": False,
                        "format": "json",
                    },
                )
                response.raise_for_status()
                content = response.json().get("response", "{}")
                parsed = json.loads(content)
                if parsed.get("action"):
                    return parsed
        except Exception:
            pass

        choices = [
            "cook a quick meal",
            "walk to the market square",
            "chat with a neighbor",
            "collect useful supplies",
            "rest beside the lake",
        ]
        return {
            "action": random.choice(choices),
            "mood": random.choice(["focused", "hungry", "curious", "calm"]),
            "reason": "fallback-policy",
        }

    def _move_agent(self, agent: Agent) -> None:
        agent.x = max(0, min(9, agent.x + random.choice([-1, 0, 1])))
        agent.y = max(0, min(9, agent.y + random.choice([-1, 0, 1])))
        if agent.x <= 2:
            agent.location = "Red House"
        elif agent.x >= 6:
            agent.location = "Market"
        elif agent.y >= 6:
            agent.location = "Lake"
        else:
            agent.location = "Town Square"

    async def ask_agent(self, agent_id: str, question: str) -> Dict[str, str]:
        agent = self.agents.get(agent_id)
        if not agent:
            raise KeyError(agent_id)

        memories = self._recent_relevant_memories(agent, limit=8)
        prompt = {
            "agent_name": agent.name,
            "question": question,
            "current_action": agent.current_action,
            "current_location": agent.location,
            "recent_memories": [m.text for m in memories],
            "instruction": "Respond in first person, 1-3 sentences.",
        }

        answer = None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": json.dumps(prompt),
                        "stream": False,
                    },
                )
                response.raise_for_status()
                answer = response.json().get("response", "").strip()
        except Exception:
            answer = f"I'm {agent.name}. Right now I'm {agent.current_action} at {agent.location}."

        await self._remember(agent, f"Was asked: '{question}'. Replied: '{answer}'", source="dialogue", importance=7)
        await self.broadcast(
            {
                "type": "qa",
                "agent_id": agent.id,
                "question": question,
                "answer": answer,
            }
        )
        return {"agent_id": agent.id, "answer": answer}

    def add_location(self, name: str, parent: Optional[str] = None) -> None:
        self.locations[name] = WorldLocation(name=name, parent=parent)

    def add_object(self, parent: str, name: str, state: str) -> None:
        if parent not in self.locations:
            raise KeyError(parent)
        self.locations[parent].objects.append(WorldObject(name=name, state=state))

    async def add_agent(self, req: CreateAgentRequest) -> Agent:
        if any(a.name.lower() == req.name.lower() for a in self.agents.values()):
            raise ValueError("Agent already exists")
        if req.location not in self.locations:
            self.add_location(req.location)
        agent = Agent(
            id=f"a{len(self.agents) + 1}",
            name=req.name,
            x=random.randint(1, 8),
            y=random.randint(1, 8),
            location=req.location,
            current_action=req.activity,
        )
        agent.emoji = self._emoji_for_action(req.activity)
        for memory in req.memories:
            agent.memories.append(
                Memory(id=str(uuid.uuid4()), timestamp=time.time(), text=memory, source="seed", importance=6)
            )
        self.agents[agent.id] = agent
        await self.broadcast({"type": "agent_created", "agent": self._agent_detail(agent)})
        return agent

    async def add_observation(self, req: AddObservationRequest) -> None:
        agent = next((a for a in self.agents.values() if a.name == req.name), None)
        if not agent:
            raise KeyError(req.name)
        await self._remember(agent, req.observation, source="external_observation", importance=8)
        if req.reactable:
            decision = await self._decide_next_action(agent, req.observation)
            agent.current_action = decision.get("action", agent.current_action)
            agent.emoji = self._emoji_for_action(agent.current_action)



    async def god_intervention(self, message: str, mode: str, agent_ids: List[str]) -> List[str]:
        if not message.strip():
            raise ValueError("Intervention message cannot be empty")

        if mode == "all":
            targets = list(self.agents.values())
        elif mode == "single":
            if len(agent_ids) != 1:
                raise ValueError("Single mode requires exactly one agent id")
            target = self.agents.get(agent_ids[0])
            if not target:
                raise KeyError(agent_ids[0])
            targets = [target]
        elif mode == "multiple":
            if not agent_ids:
                raise ValueError("Multiple mode requires at least one agent id")
            targets = []
            for aid in agent_ids:
                agent = self.agents.get(aid)
                if not agent:
                    raise KeyError(aid)
                targets.append(agent)
        else:
            raise ValueError("Mode must be one of: single, multiple, all")

        informed_ids = []
        for agent in targets:
            text = f"God intervention message for {agent.name}: {message.strip()}"
            await self._remember(agent, text=text, source="god_intervention", importance=9)
            informed_ids.append(agent.id)

        await self.broadcast({
            "type": "intervention",
            "mode": mode,
            "message": message.strip(),
            "agent_ids": informed_ids,
        })
        return informed_ids

    def _update_conversations(self) -> None:
        agents = list(self.agents.values())
        for i, first in enumerate(agents):
            for second in agents[i + 1 :]:
                distance = abs(first.x - second.x) + abs(first.y - second.y)
                if distance <= 1 and random.random() < 0.35:
                    convo = Conversation(
                        name=first.name,
                        other=second.name,
                        dialog=[
                            DialogueLine(name=first.name, dialog=f"I am {first.current_action} right now."),
                            DialogueLine(name=second.name, dialog=f"Good to know; I am {second.current_action}."),
                        ],
                    )
                    self.conversations.append(convo)

    def _emoji_for_action(self, action: str) -> str:
        lower = action.lower()
        for key, emoji in EMOJIS.items():
            if key in lower:
                return emoji
        return "🙂"

    def _memory_to_dict(self, memory: Memory) -> Dict:
        return {
            "id": memory.id,
            "timestamp": memory.timestamp,
            "text": memory.text,
            "source": memory.source,
            "importance": memory.importance,
        }

    def _agent_summary(self, agent: Agent) -> Dict:
        return {
            "id": agent.id,
            "name": agent.name,
            "x": agent.x,
            "y": agent.y,
            "location": agent.location,
            "current_action": agent.current_action,
            "activity": agent.current_action,
            "mood": agent.mood,
            "emoji": agent.emoji,
        }

    def _agent_detail(self, agent: Agent) -> Dict:
        return {
            **self._agent_summary(agent),
            "goals": agent.goals,
            "memories": [self._memory_to_dict(m) for m in sorted(agent.memories, key=lambda x: x.timestamp)[-40:]],
        }

    def _location_to_dict(self, location: WorldLocation) -> Dict:
        return {
            "name": location.name,
            "description": location.name,
            "parent": location.parent,
            "objects": [{"name": obj.name, "state": obj.state} for obj in location.objects],
        }

    def _conversation_to_dict(self, conversation: Conversation) -> Dict:
        return {
            "name": conversation.name,
            "other": conversation.other,
            "dialog": [{"name": d.name, "dialog": d.dialog} for d in conversation.dialog],
        }

    def state_payload(self) -> Dict:
        return {
            "agents": [self._agent_summary(a) for a in self.agents.values()],
            "locations": [self._location_to_dict(l) for l in self.locations.values()],
            "conversations": [self._conversation_to_dict(c) for c in self.conversations],
            "tick": self.tick_count,
        }

    async def subscribe(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._subscribers.add(websocket)
        await websocket.send_json({"type": "snapshot", "running": self.running, **self.state_payload()})

    async def unsubscribe(self, websocket: WebSocket) -> None:
        self._subscribers.discard(websocket)

    async def broadcast(self, event: Dict) -> None:
        stale = []
        for ws in self._subscribers:
            try:
                await ws.send_json(event)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._subscribers.discard(ws)


engine = SimulationEngine()
app = FastAPI(title="Generative NPC Simulation")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")


@app.on_event("startup")
async def startup() -> None:
    engine.seed_world()
    engine.seed_agents()
    await engine.start()


@app.on_event("shutdown")
async def shutdown() -> None:
    await engine.stop()


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(str(DASHBOARD_DIR / "index.html"))


@app.get("/ping")
async def ping() -> Dict:
    return {"status": "ok"}


@app.get("/api/health")
async def health() -> Dict:
    return {"status": "ok", "ollama_available": await engine.ollama_available()}


@app.get("/api/sim")
async def sim_state() -> Dict:
    return {
        "running": engine.running,
        "tick": engine.tick_count,
        "tick_seconds": engine.tick_seconds,
        "agent_count": len(engine.agents),
        "ollama_url": engine.ollama_url,
        "ollama_model": engine.ollama_model,
        "ollama_available": await engine.ollama_available(),
        "max_memories": engine.max_memories,
    }


@app.post("/api/sim")
async def set_sim_state(body: SimControl) -> Dict:
    if body.running:
        await engine.start()
    else:
        await engine.stop()
    return {"running": engine.running}


@app.post("/api/sim/tick")
async def force_tick() -> Dict:
    await engine.tick()
    return {"tick": engine.tick_count}


@app.get("/api/agents")
async def list_agents() -> List[Dict]:
    return [engine._agent_summary(agent) for agent in engine.agents.values()]


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> Dict:
    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return engine._agent_detail(agent)


@app.get("/api/agents/{agent_id}/memories")
async def get_agent_memories(agent_id: str) -> List[Dict]:
    agent = engine.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return [engine._memory_to_dict(m) for m in sorted(agent.memories, key=lambda x: x.timestamp)]


@app.post("/api/agents/{agent_id}/ask")
async def ask(agent_id: str, body: AskRequest) -> Dict:
    try:
        return await engine.ask_agent(agent_id, body.question)
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent not found")


# Smallville-compatible APIs
@app.get("/state")
async def state() -> Dict:
    return engine.state_payload()


@app.post("/state")
async def update_state() -> Dict:
    await engine.tick()
    return engine.state_payload()


@app.post("/agents")
async def create_agent(body: CreateAgentRequest) -> Dict:
    try:
        agent = await engine.add_agent(body)
        return {"success": True, "agent": engine._agent_detail(agent)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/locations")
async def create_location(body: CreateLocationRequest) -> Dict:
    engine.add_location(body.name, body.parent)
    return {"success": True, "location": engine._location_to_dict(engine.locations[body.name])}


@app.post("/objects")
async def create_object(body: CreateObjectRequest) -> Dict:
    try:
        engine.add_object(body.parent, body.name, body.state)
        return {"success": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Parent location not found")


@app.post("/react")
async def add_observation(body: AddObservationRequest) -> Dict:
    try:
        await engine.add_observation(body)
        return {"success": True}
    except KeyError:
        raise HTTPException(status_code=404, detail="Agent not found")




@app.post("/api/interventions")
async def god_interventions(body: GodInterventionRequest) -> Dict:
    try:
        informed = await engine.god_intervention(body.message, body.mode, body.agent_ids)
        return {"success": True, "informed_agent_ids": informed, "count": len(informed)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Agent not found: {str(exc)}")


@app.websocket("/ws/events")
async def events(ws: WebSocket) -> None:
    await engine.subscribe(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await engine.unsubscribe(ws)


def main() -> None:
    import uvicorn

    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
