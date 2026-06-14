package com.m4;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import java.net.HttpURLConnection;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class AnalyzeHandler implements HttpHandler {

    private final RabbitPublisher publisher = new RabbitPublisher();
    private static final int NO_BODY = -1;

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        exchange.getResponseHeaders().add("Access-Control-Allow-Origin",  "*");
        exchange.getResponseHeaders().add("Access-Control-Allow-Methods", "POST, OPTIONS");
        exchange.getResponseHeaders().add("Access-Control-Allow-Headers", "Content-Type");

        if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
            exchange.sendResponseHeaders(HttpURLConnection.HTTP_NO_CONTENT, NO_BODY);
            return;
        }

        if (!"POST".equalsIgnoreCase(exchange.getRequestMethod())) {
            sendResponse(exchange, HttpURLConnection.HTTP_BAD_METHOD, "{\"error\":\"Method not allowed\"}");
            return;
        }

        try {
            String contentType = exchange.getRequestHeaders().getFirst("Content-Type");
            byte[] multipartBody = exchange.getRequestBody().readAllBytes();
            byte[] body = extractImageFromMultipart(multipartBody, contentType);

            if (body.length == 0) {
                sendResponse(exchange, HttpURLConnection.HTTP_INTERNAL_ERROR, "{\"error\":\"No se recibió ninguna imagen\"}");
                return;
            }

            // Publica la imagen en RabbitMQ y espera el resultado
            String result = publisher.waitQueue(body);
            exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
            sendResponse(exchange, HttpURLConnection.HTTP_OK, result);

        } catch (Exception e) {
            e.printStackTrace();
            sendResponse(exchange, HttpURLConnection.HTTP_INTERNAL_ERROR, "{\"error\":\"Error publicando en la cola\"}");
        }
    }

    private byte[] extractImageFromMultipart(byte[] body, String contentType) {
        String boundary = contentType.substring(contentType.indexOf("boundary=") + 9);
        if (boundary.startsWith("\""))
            boundary = boundary.substring(1, boundary.indexOf("\"", 1));
        byte[] boundaryBytes = ("--" + boundary).getBytes(StandardCharsets.UTF_8);
        byte[] crlfBoundary = ("\r\n--" + boundary).getBytes(StandardCharsets.UTF_8);
        byte[] marker = "name=\"image\"".getBytes(StandardCharsets.UTF_8);
        int pos = 0;
        // Buscar el primer boundary
        int firstBoundary = indexOf(body, boundaryBytes, 0);
        if (firstBoundary < 0) return body;
        pos = firstBoundary + boundaryBytes.length;
        pos = skipLine(body, pos);
        while (pos < body.length) {
            int headerEnd = indexOf(body, "\r\n\r\n".getBytes(StandardCharsets.UTF_8), pos);
            if (headerEnd < 0) break;
            byte[] headerSection = Arrays.copyOfRange(body, pos, headerEnd);
            boolean isImagePart = indexOf(headerSection, marker, 0) >= 0;
            int dataStart = headerEnd + 4; // saltar \r\n\r\n
            if (isImagePart) {
                int dataEnd = indexOf(body, crlfBoundary, dataStart);
                if (dataEnd < 0) {
                    // Podría ser el último boundary (--boundary--)
                    byte[] closing = ("\r\n--" + boundary + "--").getBytes(StandardCharsets.UTF_8);
                    dataEnd = indexOf(body, closing, dataStart);
                    if (dataEnd < 0) return Arrays.copyOfRange(body, dataStart, body.length);
                }
                return Arrays.copyOfRange(body, dataStart, dataEnd);
            }
            // Saltar al siguiente boundary
            int nextBoundary = indexOf(body, crlfBoundary, dataStart);
            if (nextBoundary < 0) break;
            pos = nextBoundary + crlfBoundary.length;
            pos = skipLine(body, pos);
        }
        return body; // fallback: devolver todo
    }

    private int indexOf(byte[] haystack, byte[] needle, int start) {
        outer:
        for (int i = start; i <= haystack.length - needle.length; i++) {
            for (int j = 0; j < needle.length; j++) {
                if (haystack[i + j] != needle[j]) continue outer;
            }
            return i;
        }
        return -1;
    }

    private int skipLine(byte[] data, int pos) {
        while (pos < data.length) {
            if (data[pos] == '\r') { pos += 2; break; }
            if (data[pos] == '\n') { pos += 1; break; }
            pos++;
        }
        return pos;
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