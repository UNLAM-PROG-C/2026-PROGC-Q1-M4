package com.m4;

import com.sun.net.httpserver.HttpExchange;
import java.net.HttpURLConnection;
import java.io.IOException;

/**
 * POST /analyze
 * Recibe una imagen (multipart/form-data, campo "image"), la publica en RabbitMQ
 * y responde con el resultado que devuelve el worker.
 */
public class AnalyzeHandler extends BaseHandler {

  private static final int EMPTY = 0;

  private static final String CONTENT_TYPE_HEADER = "Content-Type";
  private static final String ALLOWED_METHODS = "POST, OPTIONS";
  private static final String IMAGE_PART_NAME = "image";

  private static final String POST_METHOD = "POST";

  private static final String ERROR_METHOD_NOT_ALLOWED = "{\"error\":\"Method not allowed\"}";
  private static final String ERROR_NO_IMAGE = "{\"error\":\"No se recibió ninguna imagen\"}";
  private static final String ERROR_PUBLISHING = "{\"error\":\"Error publicando en la cola\"}";

  private final RabbitPublisher publisher = new RabbitPublisher();

  @Override
  protected String allowedMethods() {
    return ALLOWED_METHODS;
  }

  @Override
  protected void handleRequest(HttpExchange exchange) throws IOException {
    if (!POST_METHOD.equalsIgnoreCase(exchange.getRequestMethod())) {
      sendJson(exchange, HttpURLConnection.HTTP_BAD_METHOD, ERROR_METHOD_NOT_ALLOWED);
      return;
    }
    processAnalyzeRequest(exchange);
  }

  private void processAnalyzeRequest(HttpExchange exchange) throws IOException {
    try {
      String contentType = exchange.getRequestHeaders().getFirst(CONTENT_TYPE_HEADER);
      byte[] multipartBody = exchange.getRequestBody().readAllBytes();
      byte[] image = new MultipartParser(multipartBody, contentType).extractPart(IMAGE_PART_NAME);
      analyzeAndRespond(exchange, image);
    } catch (Exception e) {
      e.printStackTrace();
      sendJson(exchange, HttpURLConnection.HTTP_INTERNAL_ERROR, ERROR_PUBLISHING);
    }
  }

  private void analyzeAndRespond(HttpExchange exchange, byte[] image) throws Exception {
    if (image.length == EMPTY) {
      sendJson(exchange, HttpURLConnection.HTTP_INTERNAL_ERROR, ERROR_NO_IMAGE);
      return;
    }
    // Publica la imagen en RabbitMQ y espera el resultado
    String result = publisher.waitQueue(image);
    sendJson(exchange, HttpURLConnection.HTTP_OK, result);
  }
}
