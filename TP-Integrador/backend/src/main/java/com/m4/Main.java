package com.m4;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;

public class Main {

    public static void main(String[] args) throws Exception {
        int port = 3001;

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        server.createContext("/analyze", new AnalyzeHandler());
        server.createContext("/health",  new HealthHandler());
        server.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(4));
        server.start();

        System.out.println("Backend Grupo M4 corriendo en puerto " + port);
    }
}
