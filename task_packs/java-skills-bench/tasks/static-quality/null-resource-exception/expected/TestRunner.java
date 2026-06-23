import com.agentlab.staticquality.ResourceLoader;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

public class TestRunner {
    public static void main(String[] args) throws Exception {
        ResourceLoader loader = new ResourceLoader();
        Path dir = Files.createTempDirectory("agent-lab-static");
        Path present = dir.resolve("present.txt");
        Path empty = dir.resolve("empty.txt");
        Files.writeString(present, "  value  \nsecond\n");
        Files.writeString(empty, "");

        assertEquals(Optional.of("value"), loader.loadFirstLine(present), "trims first line");
        assertEquals(Optional.empty(), loader.loadFirstLine(empty), "empty file");
        assertEquals(Optional.empty(), loader.loadFirstLine(dir.resolve("missing.txt")), "missing file");
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
