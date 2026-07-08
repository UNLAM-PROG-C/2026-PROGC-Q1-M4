package com.m4;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import java.net.HttpURLConnection;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Clase base para todos los handlers HTTP.
 *
 * Concentra la "plomería" HTTP común: cabeceras CORS, respuesta preflight OPTIONS
 * y envío de respuestas JSON. Las subclases solo implementan {@link #handleRequest},
 * sin preocuparse por cabeceras ni por cómo se escribe la respuesta.
 */
public abstract class BaseHandler implements HttpHandler {

  private static final int NO_BODY = -1;

  private static final String CORS_ORIGIN_HEADER = "Access-Control-Allow-Origin";
  private static final String CORS_METHODS_HEADER = "Access-Control-Allow-Methods";
  private static final String CORS_HEADERS_HEADER = "Access-Control-Allow-Headers";
  private static final String ALLOW_ALL_ORIGINS = "*";
  private static final String CONTENT_TYPE_HEADER = "Content-Type";
  private static final String JSON_CONTENT_TYPE = "application/json; charset=utf-8";

  private static final String OPTIONS_METHOD = "OPTIONS";

  @Override
  public final void handle(HttpExchange exchange) throws IOException {
    addCorsHeaders(exchange);

    if (OPTIONS_METHOD.equalsIgnoreCase(exchange.getRequestMethod())) {
      exchange.sendResponseHeaders(HttpURLConnection.HTTP_NO_CONTENT, NO_BODY);
      return;
    }

    handleRequest(exchange);
  }

  /**
   * Lógica específica de cada handler. Se invoca con CORS ya aplicado y
   * después de descartar las peticiones preflight OPTIONS.
   */
  protected abstract void handleRequest(HttpExchange exchange) throws IOException;

  /**
   * Métodos HTTP que este handler acepta (además de OPTIONS), separados por coma.
   * Se publica en la cabecera Access-Control-Allow-Methods.
   */
  protected abstract String allowedMethods();

  private void addCorsHeaders(HttpExchange exchange) {
    exchange.getResponseHeaders().add(CORS_ORIGIN_HEADER, ALLOW_ALL_ORIGINS);
    exchange.getResponseHeaders().add(CORS_METHODS_HEADER, allowedMethods());
    exchange.getResponseHeaders().add(CORS_HEADERS_HEADER, CONTENT_TYPE_HEADER);
  }

  /** Envía una respuesta JSON con el código de estado dado. */
  protected void sendJson(HttpExchange exchange, int status, String body) throws IOException {
    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().add(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE);
    exchange.sendResponseHeaders(status, bytes.length);
    try (OutputStream os = exchange.getResponseBody()) {
      os.write(bytes);
    }
  }
}
