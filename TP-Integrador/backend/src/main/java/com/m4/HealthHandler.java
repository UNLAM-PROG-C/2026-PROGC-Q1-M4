package com.m4;

import com.sun.net.httpserver.HttpExchange;
import java.net.HttpURLConnection;
import java.io.IOException;

/**
 * GET /health
 * Usado por Docker para verificar que el servidor está listo.
 */
public class HealthHandler extends BaseHandler {

  private static final String ALLOWED_METHODS = "GET, OPTIONS";
  private static final String OK_BODY = "{\"status\":\"ok\"}";

  @Override
  protected String allowedMethods() {
    return ALLOWED_METHODS;
  }

  @Override
  protected void handleRequest(HttpExchange exchange) throws IOException {
    sendJson(exchange, HttpURLConnection.HTTP_OK, OK_BODY);
  }
}
