package com.game.npc;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;

/**
 * Minimal Java client for the NPC simulation server.
 * Returns raw JSON strings so game teams can map responses with their preferred JSON library.
 */
public class NpcSimClient {
    private final String baseUrl;
    private final HttpClient http;

    public NpcSimClient(String baseUrl) {
        this.baseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        this.http = HttpClient.newHttpClient();
    }

    public String getSimulation() throws IOException, InterruptedException {
        return get("/api/sim");
    }

    public String setRunning(boolean running) throws IOException, InterruptedException {
        return post("/api/sim", "{\"running\":" + running + "}");
    }

    public String listAgents() throws IOException, InterruptedException {
        return get("/api/agents");
    }

    public String getAgent(String agentId) throws IOException, InterruptedException {
        return get("/api/agents/" + agentId);
    }

    public String getMemories(String agentId) throws IOException, InterruptedException {
        return get("/api/agents/" + agentId + "/memories");
    }

    public String askAgent(String agentId, String question) throws IOException, InterruptedException {
        String safeQuestion = question.replace("\\", "\\\\").replace("\"", "\\\"");
        return post("/api/agents/" + agentId + "/ask", "{\"question\":\"" + safeQuestion + "\"}");
    }

    private String get(String path) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .GET()
                .build();
        return send(request);
    }

    private String post(String path, String body) throws IOException, InterruptedException {
        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + path))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body, StandardCharsets.UTF_8))
                .build();
        return send(request);
    }

    private String send(HttpRequest request) throws IOException, InterruptedException {
        HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
        int status = response.statusCode();
        if (status < 200 || status >= 300) {
            throw new IOException("HTTP " + status + ": " + response.body());
        }
        return response.body();
    }
}
