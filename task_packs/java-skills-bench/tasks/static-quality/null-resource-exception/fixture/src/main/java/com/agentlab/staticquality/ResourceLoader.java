package com.agentlab.staticquality;

import java.io.BufferedReader;
import java.io.FileReader;
import java.nio.file.Path;
import java.util.Optional;

public class ResourceLoader {
    public Optional<String> loadFirstLine(Path path) throws Exception {
        BufferedReader reader = new BufferedReader(new FileReader(path.toFile()));
        String line = reader.readLine();
        return Optional.of(line.trim());
    }
}
