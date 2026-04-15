import com.game.npc.NpcSimClient;

public class ExampleUsage {
    public static void main(String[] args) throws Exception {
        NpcSimClient client = new NpcSimClient("http://localhost:8000");
        System.out.println("Simulation: " + client.getSimulation());
        System.out.println("Agents: " + client.listAgents());
        System.out.println("Ask: " + client.askAgent("a1", "What are you doing right now?"));
    }
}
