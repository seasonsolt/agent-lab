package com.agentlab.security;

import java.util.List;

public record Query(String sql, List<String> parameters) {
}
