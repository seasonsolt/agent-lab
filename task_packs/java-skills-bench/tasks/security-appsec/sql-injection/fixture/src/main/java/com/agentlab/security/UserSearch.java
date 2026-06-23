package com.agentlab.security;

import java.util.List;

public class UserSearch {
    public Query buildFindByEmail(String email) {
        return new Query("select id, email from users where email = '" + email + "'", List.of());
    }
}
