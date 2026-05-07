package com.m4;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

/**
 * POST /analyze
 * Recibe multipart/form-data con el campo "image".
 * Devuelve un JSON con los objetos reconocidos y su probabilidad.
 *
 * TODO: reemplazar la respuesta mock por la llamada real al modelo de IA.
 */
public class AnalyzeHandler implements HttpHandler {

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        // CORS — necesario para que el frontend en otro origen pueda llamar
        exchange.getResponseHeaders().add("Access-Control-Allow-Origin",  "*");
        exchange.getResponseHeaders().add("Access-Control-Allow-Methods", "POST, OPTIONS");
        exchange.getResponseHeaders().add("Access-Control-Allow-Headers", "Content-Type");

        // Preflight OPTIONS
        if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(204, -1);
            return;
        }

        if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
            sendResponse(exchange, 405, "{\"error\":\"Method not allowed\"}");
            return;
        }

        try {
            // Leemos el body (multipart con la imagen)
            byte[] body = exchange.getRequestBody().readAllBytes();

            if (body.length == 0) {
                sendResponse(exchange, 400, "{\"error\":\"No se recibió ninguna imagen\"}");
                return;
            }

            // -----------------------------------------------------------------
            // TODO: acá va la lógica real de IA.
            // Por ahora devolvemos resultados mock.
            // Podés reemplazar esto por:
            //   - Una llamada a un modelo local (ONNX, DJL, etc.)
            //   - Una llamada a una API externa (OpenAI Vision, AWS Rekognition, etc.)
            // -----------------------------------------------------------------
            String json = buildMockResponse().toString();
            sendResponse(exchange, 200, json);

        } catch (Exception e) {
            e.printStackTrace();
            sendResponse(exchange, 500, "{\"error\":\"Error interno del servidor\"}");
        }
    }

    private JSONArray buildMockResponse() {
        JSONArray results = new JSONArray();
        results.put(new JSONObject().put("name", "Gato").put("probability", 85.3));
        results.put(new JSONObject().put("name", "Silla").put("probability", 42.7));
        results.put(new JSONObject().put("name", "Mesa").put("probability", 18.4));
        results.put(new JSONObject().put("name", "Laptop").put("probability", 9.2));
        return results;
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
