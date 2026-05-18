package com.m4;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;
import java.nio.charset.StandardCharsets;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public class AnalyzeHandler implements HttpHandler {

    private final RabbitPublisher publisher = new RabbitPublisher();
    private static final int ERROR_CODE_QUEUE = 500;
    private static final int ERROR_CODE_IMAGE = 500;
    private static final int ERROR_CODE_METHOD = 405;
    private static final int OK_CODE = 200; 
    private static final int OPTIONS_NO_CONTENT = 204;

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        exchange.getResponseHeaders().add("Access-Control-Allow-Origin",  "*");
        exchange.getResponseHeaders().add("Access-Control-Allow-Methods", "POST, OPTIONS");
        exchange.getResponseHeaders().add("Access-Control-Allow-Headers", "Content-Type");

        if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(OPTIONS_NO_CONTENT, -1);
            return;
        }

        if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
            sendResponse(exchange, ERROR_CODE_METHOD, "{\"error\":\"Method not allowed\"}");
            return;
        }

        try {
            byte[] body = exchange.getRequestBody().readAllBytes();

            if (body.length == 0) {
                sendResponse(exchange, ERROR_CODE_IMAGE, "{\"error\":\"No se recibió ninguna imagen\"}");
                return;
            }

            // Publica la imagen en RabbitMQ
            publisher.publish(body);

            // DESPUÉS:
            String result = publisher.waitQueue(body);
            exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
            sendResponse(exchange, OK_CODE, result);

        } catch (Exception e) {
            e.printStackTrace();
            sendResponse(exchange, ERROR_CODE_QUEUE, "{\"error\":\"Error publicando en la cola\"}");
        }
    }

    private void sendResponse(HttpExchange exchange, int status, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }
}