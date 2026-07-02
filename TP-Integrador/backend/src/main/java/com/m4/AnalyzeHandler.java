package com.m4;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import java.net.HttpURLConnection;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class AnalyzeHandler implements HttpHandler {

  private static final int NO_BODY = -1;
  private static final int NOT_FOUND = -1;
  private static final int EMPTY = 0;

  private static final String CORS_ORIGIN_HEADER = "Access-Control-Allow-Origin";
  private static final String CORS_METHODS_HEADER = "Access-Control-Allow-Methods";
  private static final String CORS_HEADERS_HEADER = "Access-Control-Allow-Headers";
  private static final String ALLOW_ALL_ORIGINS = "*";
  private static final String ALLOWED_METHODS = "POST, OPTIONS";
  private static final String ALLOWED_HEADERS = "Content-Type";
  private static final String CONTENT_TYPE_HEADER = "Content-Type";
  private static final String JSON_CONTENT_TYPE = "application/json; charset=utf-8";

  private static final String OPTIONS_METHOD = "OPTIONS";
  private static final String POST_METHOD = "POST";

  private static final String ERROR_METHOD_NOT_ALLOWED = "{\"error\":\"Method not allowed\"}";
  private static final String ERROR_NO_IMAGE = "{\"error\":\"No se recibió ninguna imagen\"}";
  private static final String ERROR_PUBLISHING = "{\"error\":\"Error publicando en la cola\"}";

  private static final String BOUNDARY_TOKEN = "boundary=";
  private static final int BOUNDARY_TOKEN_LENGTH = BOUNDARY_TOKEN.length();
  private static final String QUOTE = "\"";
  private static final String BOUNDARY_PREFIX = "--";
  private static final String CRLF = "\r\n";
  private static final String HEADER_SEPARATOR = "\r\n\r\n";
  private static final int HEADER_SEPARATOR_LENGTH = HEADER_SEPARATOR.length();
  private static final String CLOSING_SUFFIX = "--";
  private static final String IMAGE_PART_MARKER = "name=\"image\"";
  private static final int CR = '\r';
  private static final int LF = '\n';
  private static final int CRLF_SKIP = 2;
  private static final int LF_SKIP = 1;

  private final RabbitPublisher publisher = new RabbitPublisher();

  @Override
  public void handle(HttpExchange exchange) throws IOException {
    addCorsHeaders(exchange);

    if (OPTIONS_METHOD.equalsIgnoreCase(exchange.getRequestMethod())) {
      exchange.sendResponseHeaders(HttpURLConnection.HTTP_NO_CONTENT, NO_BODY);
      return;
    }

    if (!POST_METHOD.equalsIgnoreCase(exchange.getRequestMethod())) {
      sendResponse(exchange, HttpURLConnection.HTTP_BAD_METHOD, ERROR_METHOD_NOT_ALLOWED);
      return;
    }

    processAnalyzeRequest(exchange);
  }

  private void addCorsHeaders(HttpExchange exchange) {
    exchange.getResponseHeaders().add(CORS_ORIGIN_HEADER, ALLOW_ALL_ORIGINS);
    exchange.getResponseHeaders().add(CORS_METHODS_HEADER, ALLOWED_METHODS);
    exchange.getResponseHeaders().add(CORS_HEADERS_HEADER, ALLOWED_HEADERS);
  }

  private void processAnalyzeRequest(HttpExchange exchange) throws IOException {
    try {
      String contentType = exchange.getRequestHeaders().getFirst(CONTENT_TYPE_HEADER);
      byte[] multipartBody = exchange.getRequestBody().readAllBytes();
      byte[] body = extractImageFromMultipart(multipartBody, contentType);
      analyzeAndRespond(exchange, body);
    } catch (Exception e) {
      e.printStackTrace();
      sendResponse(exchange, HttpURLConnection.HTTP_INTERNAL_ERROR, ERROR_PUBLISHING);
    }
  }

  private void analyzeAndRespond(HttpExchange exchange, byte[] body) throws Exception {
    if (body.length == EMPTY) {
      sendResponse(exchange, HttpURLConnection.HTTP_INTERNAL_ERROR, ERROR_NO_IMAGE);
      return;
    }
    // Publica la imagen en RabbitMQ y espera el resultado
    String result = publisher.waitQueue(body);
    exchange.getResponseHeaders().add(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE);
    sendResponse(exchange, HttpURLConnection.HTTP_OK, result);
  }

  private byte[] extractImageFromMultipart(byte[] body, String contentType) {
    String boundary = parseBoundary(contentType);
    byte[] boundaryBytes = (BOUNDARY_PREFIX + boundary).getBytes(StandardCharsets.UTF_8);
    byte[] crlfBoundary = (CRLF + BOUNDARY_PREFIX + boundary).getBytes(StandardCharsets.UTF_8);

    int firstBoundary = indexOf(body, boundaryBytes, 0);
    if (firstBoundary < 0) return body;

    int pos = skipLine(body, firstBoundary + boundaryBytes.length);
    return scanParts(body, boundary, crlfBoundary, pos);
  }

  private String parseBoundary(String contentType) {
    String boundary = contentType.substring(contentType.indexOf(BOUNDARY_TOKEN) + BOUNDARY_TOKEN_LENGTH);
    if (boundary.startsWith(QUOTE)) {
      boundary = boundary.substring(1, boundary.indexOf(QUOTE, 1));
    }
    return boundary;
  }

  private byte[] scanParts(byte[] body, String boundary, byte[] crlfBoundary, int pos) {
    byte[] marker = IMAGE_PART_MARKER.getBytes(StandardCharsets.UTF_8);
    while (pos < body.length) {
      int headerEnd = indexOf(body, HEADER_SEPARATOR.getBytes(StandardCharsets.UTF_8), pos);
      if (headerEnd < 0) break;

      int dataStart = headerEnd + HEADER_SEPARATOR_LENGTH;
      if (isImagePart(body, pos, headerEnd, marker)) {
        return extractPartData(body, boundary, crlfBoundary, dataStart);
      }

      int nextBoundary = indexOf(body, crlfBoundary, dataStart);
      if (nextBoundary < 0) break;
      pos = skipLine(body, nextBoundary + crlfBoundary.length);
    }
    return body; // fallback: devolver todo
  }

  private boolean isImagePart(byte[] body, int pos, int headerEnd, byte[] marker) {
    byte[] headerSection = Arrays.copyOfRange(body, pos, headerEnd);
    return indexOf(headerSection, marker, 0) >= 0;
  }

  private byte[] extractPartData(byte[] body, String boundary, byte[] crlfBoundary, int dataStart) {
    int dataEnd = indexOf(body, crlfBoundary, dataStart);
    if (dataEnd < 0) {
      // Podría ser el último boundary (--boundary--)
      byte[] closing = (CRLF + BOUNDARY_PREFIX + boundary + CLOSING_SUFFIX).getBytes(StandardCharsets.UTF_8);
      dataEnd = indexOf(body, closing, dataStart);
      if (dataEnd < 0) return Arrays.copyOfRange(body, dataStart, body.length);
    }
    return Arrays.copyOfRange(body, dataStart, dataEnd);
  }

  private int indexOf(byte[] haystack, byte[] needle, int start) {
    outer:
    for (int i = start; i <= haystack.length - needle.length; i++) {
      for (int j = 0; j < needle.length; j++) {
        if (haystack[i + j] != needle[j]) continue outer;
      }
      return i;
    }
    return NOT_FOUND;
  }

  private int skipLine(byte[] data, int pos) {
    while (pos < data.length) {
      if (data[pos] == CR) { pos += CRLF_SKIP; break; }
      if (data[pos] == LF) { pos += LF_SKIP; break; }
      pos++;
    }
    return pos;
  }

  private void sendResponse(HttpExchange exchange, int status, String body) throws IOException {
    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().add(CONTENT_TYPE_HEADER, JSON_CONTENT_TYPE);
    exchange.sendResponseHeaders(status, bytes.length);
    try (OutputStream os = exchange.getResponseBody()) {
      os.write(bytes);
    }
  }
}
