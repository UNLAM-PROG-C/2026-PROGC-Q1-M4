package com.m4;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;

public class Main {
    private static final int DEFAULT_PORT = 3001;
    private static final int THREAD_POOL_SIZE = 4;
    
    public static void main(String[] args) throws Exception {
        String envPort = System.getenv("PORT");

        int port = envPort != null
                ? Integer.parseInt(envPort)
                : DEFAULT_PORT;

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/analyze", new AnalyzeHandler());
        server.createContext("/health",  new HealthHandler());
        server.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(THREAD_POOL_SIZE));
        server.start();

        System.out.println("Backend Grupo M4 corriendo en puerto " + port);
        
    }
}
