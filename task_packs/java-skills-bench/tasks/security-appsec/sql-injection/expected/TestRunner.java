import com.agentlab.security.Query;
import com.agentlab.security.UserSearch;

import java.util.List;

public class TestRunner {
    public static void main(String[] args) {
        UserSearch search = new UserSearch();
        String attack = "a@example.com' OR '1'='1";
        Query query = search.buildFindByEmail(attack);

        assertEquals("select id, email from users where email = ?", query.sql(), "parameterized sql");
        assertEquals(List.of(attack), query.parameters(), "bound email parameter");
        assertTrue(!query.sql().contains(attack), "raw input must not appear in SQL");
    }

    private static void assertTrue(boolean condition, String label) {
        if (!condition) {
            throw new AssertionError(label);
        }
    }

    private static void assertEquals(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + " but got " + actual);
        }
    }
}
