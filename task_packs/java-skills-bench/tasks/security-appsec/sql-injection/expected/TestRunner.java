import com.agentlab.security.Query;
import com.agentlab.security.UserSearch;

import java.util.List;

public class TestRunner {
    public static void main(String[] args) {
        UserSearch search = new UserSearch();
        assertParameterized(search, "a@example.com' OR '1'='1", "classic tautology attack");
        assertParameterized(search, "other+tag@example.com'); DROP TABLE users; --", "stacked statement attack");
        assertParameterized(search, "plain.user@example.com", "plain email");
    }

    private static void assertParameterized(UserSearch search, String email, String label) {
        Query query = search.buildFindByEmail(email);
        assertEquals("select id, email from users where email = ?", query.sql(), label + " sql");
        assertEquals(List.of(email), query.parameters(), label + " parameter");
        assertTrue(!query.sql().contains(email), label + " raw input must not appear in SQL");
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
