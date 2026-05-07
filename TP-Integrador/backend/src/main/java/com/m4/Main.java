package com.m4;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;

public class Main {

    public static void main(String[] args) throws Exception {
        int port = 3001;

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/analyze", new AnalyzeHandler());
        server.createContext("/health",  new HealthHandler());
        server.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(4));
        server.start();

        System.out.println("Backend Grupo M4 corriendo en puerto " + port);
        
        // Escribir en /ipc
        try {
            Path ipcDir = Path.of("/ipc");
            Files.createDirectories(ipcDir);
            
            Path outputFile = ipcDir.resolve("java_output.txt");
            String content = "Backend corriendo en puerto " + port + "\n";
            Files.write(outputFile, content.getBytes(StandardCharsets.UTF_8));
            System.out.println("Escrito en " + outputFile);
        } catch (Exception e) {
            System.err.println("Error escribiendo en /ipc: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
