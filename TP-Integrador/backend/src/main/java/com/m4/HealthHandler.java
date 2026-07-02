package com.m4;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import java.net.HttpURLConnection;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * GET /health
 * Usado por Docker para verificar que el servidor está listo.
 */
public class HealthHandler implements HttpHandler {

  private static final String CORS_ORIGIN_HEADER = "Access-Control-Allow-Origin";
  private static final String ALLOW_ALL_ORIGINS = "*";
  private static final String CONTENT_TYPE_HEADER = "Content-Type";
  private static final String JSON_CONTENT_TYPE = "application/json; charset=utf-8";
  private static final String OK_BODY = "{\"status\":\"ok\"}";

  @Override
  public void handle(HttpExchange exchange) throws IOException {
    exchange.getResponseHeaders().add(CORS_ORIGIN_HEADER, ALLOW_ALL_ORIGINS);
    byte[] body = OK_BODY.getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().add(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE);
    exchange.sendResponseHeaders(HttpURLConnection.HTTP_OK, body.length);
    try (OutputStream os = exchange.getResponseBody()) {
      os.write(body);
    }
  }
}
