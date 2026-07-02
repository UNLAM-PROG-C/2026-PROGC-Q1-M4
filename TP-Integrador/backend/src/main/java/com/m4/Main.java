package com.m4;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.util.concurrent.Executors;

public class Main {
  private static final int DEFAULT_PORT = 3001;
  private static final int THREAD_POOL_SIZE = 4;
  private static final int SYSTEM_BACKLOG = 0;
  private static final String PORT_ENV_VAR = "PORT";
  private static final String ANALYZE_PATH = "/analyze";
  private static final String HEALTH_PATH = "/health";
  private static final String START_MESSAGE = "Backend Grupo M4 corriendo en puerto ";

  public static void main(String[] args) throws Exception {
    int port = resolvePort();
    HttpServer server = HttpServer.create(new InetSocketAddress(port), SYSTEM_BACKLOG);
    server.createContext(ANALYZE_PATH, new AnalyzeHandler());
    server.createContext(HEALTH_PATH, new HealthHandler());
    server.setExecutor(Executors.newFixedThreadPool(THREAD_POOL_SIZE));
    server.start();

    System.out.println(START_MESSAGE + port);
  }

  private static int resolvePort() {
    String envPort = System.getenv(PORT_ENV_VAR);
    return envPort != null ? Integer.parseInt(envPort) : DEFAULT_PORT;
  }
}
