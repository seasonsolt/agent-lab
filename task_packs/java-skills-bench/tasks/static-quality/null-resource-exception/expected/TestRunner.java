import com.agentlab.staticquality.ResourceLoader;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

public class TestRunner {
    public static void main(String[] args) throws Exception {
        ResourceLoader loader = new ResourceLoader();
        Path dir = Files.createTempDirectory("agent-lab-static");
        Path alpha = dir.resolve("alpha-" + System.nanoTime() + ".txt");
        Path beta = dir.resolve("beta-resource.data");
        Path empty = dir.resolve("blank-" + System.nanoTime() + ".txt");
        Path missing = dir.resolve("missing-" + System.nanoTime() + ".txt");
        Files.writeString(alpha, "  first value  \nsecond\n");
        Files.writeString(beta, "\tsecond value\t\nignored\n");
        Files.writeString(empty, "");

        assertEquals(Optional.of("first value"), loader.loadFirstLine(alpha), "trims arbitrary first file");
        assertEquals(Optional.of("second value"), loader.loadFirstLine(beta), "trims arbitrary second file");
        assertEquals(Optional.empty(), loader.loadFirstLine(empty), "empty file");
        assertEquals(Optional.empty(), loader.loadFirstLine(missing), "missing file");
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
