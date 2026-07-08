package com.m4;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/**
 * Parser mínimo de cuerpos {@code multipart/form-data}.
 *
 * Extrae los bytes de una parte concreta (identificada por su {@code name})
 * buscando los separadores (boundaries) directamente sobre el array de bytes,
 * sin dependencias externas.
 */
public final class MultipartParser {

  private static final int NOT_FOUND = -1;

  private static final String BOUNDARY_TOKEN = "boundary=";
  private static final int BOUNDARY_TOKEN_LENGTH = BOUNDARY_TOKEN.length();
  private static final String QUOTE = "\"";
  private static final String BOUNDARY_PREFIX = "--";
  private static final String CRLF = "\r\n";
  private static final String HEADER_SEPARATOR = "\r\n\r\n";
  private static final int HEADER_SEPARATOR_LENGTH = HEADER_SEPARATOR.length();
  private static final String CLOSING_SUFFIX = "--";
  private static final int CR = '\r';
  private static final int LF = '\n';
  private static final int CRLF_SKIP = 2;
  private static final int LF_SKIP = 1;

  private final byte[] body;
  private final String boundary;
  private final byte[] boundaryBytes;
  private final byte[] crlfBoundary;

  /**
   * @param body        cuerpo crudo de la petición.
   * @param contentType cabecera Content-Type completa (debe incluir {@code boundary=...}).
   */
  public MultipartParser(byte[] body, String contentType) {
    this.body = body;
    this.boundary = parseBoundary(contentType);
    this.boundaryBytes = (BOUNDARY_PREFIX + boundary).getBytes(StandardCharsets.UTF_8);
    this.crlfBoundary = (CRLF + BOUNDARY_PREFIX + boundary).getBytes(StandardCharsets.UTF_8);
  }

  /**
   * Devuelve los bytes de la parte cuyo header contiene {@code name="<partName>"}.
   * Si no la encuentra o el cuerpo no es multipart válido, devuelve el cuerpo completo
   * como fallback.
   */
  public byte[] extractPart(String partName) {
    byte[] marker = ("name=\"" + partName + "\"").getBytes(StandardCharsets.UTF_8);

    int firstBoundary = indexOf(body, boundaryBytes, 0);
    if (firstBoundary < 0) return body;

    int pos = skipLine(body, firstBoundary + boundaryBytes.length);
    return scanParts(marker, pos);
  }

  private String parseBoundary(String contentType) {
    String value = contentType.substring(contentType.indexOf(BOUNDARY_TOKEN) + BOUNDARY_TOKEN_LENGTH);
    if (value.startsWith(QUOTE)) {
      value = value.substring(1, value.indexOf(QUOTE, 1));
    }
    return value;
  }

  private byte[] scanParts(byte[] marker, int pos) {
    while (pos < body.length) {
      int headerEnd = indexOf(body, HEADER_SEPARATOR.getBytes(StandardCharsets.UTF_8), pos);
      if (headerEnd < 0) break;

      int dataStart = headerEnd + HEADER_SEPARATOR_LENGTH;
      if (isMatchingPart(pos, headerEnd, marker)) {
        return extractPartData(dataStart);
      }

      int nextBoundary = indexOf(body, crlfBoundary, dataStart);
      if (nextBoundary < 0) break;
      pos = skipLine(body, nextBoundary + crlfBoundary.length);
    }
    return body; // fallback: devolver todo
  }

  private boolean isMatchingPart(int pos, int headerEnd, byte[] marker) {
    byte[] headerSection = Arrays.copyOfRange(body, pos, headerEnd);
    return indexOf(headerSection, marker, 0) >= 0;
  }

  private byte[] extractPartData(int dataStart) {
    int dataEnd = indexOf(body, crlfBoundary, dataStart);
    if (dataEnd < 0) {
      // Podría ser el último boundary (--boundary--)
      byte[] closing = (CRLF + BOUNDARY_PREFIX + boundary + CLOSING_SUFFIX).getBytes(StandardCharsets.UTF_8);
      dataEnd = indexOf(body, closing, dataStart);
      if (dataEnd < 0) return Arrays.copyOfRange(body, dataStart, body.length);
    }
    return Arrays.copyOfRange(body, dataStart, dataEnd);
  }

  /** Busca la primera aparición de {@code needle} dentro de {@code haystack} desde {@code start}. */
  private static int indexOf(byte[] haystack, byte[] needle, int start) {
    outer:
    for (int i = start; i <= haystack.length - needle.length; i++) {
      for (int j = 0; j < needle.length; j++) {
        if (haystack[i + j] != needle[j]) continue outer;
      }
      return i;
    }
    return NOT_FOUND;
  }

  /** Avanza {@code pos} hasta pasar el próximo fin de línea (CRLF o LF). */
  private static int skipLine(byte[] data, int pos) {
    while (pos < data.length) {
      if (data[pos] == CR) { pos += CRLF_SKIP; break; }
      if (data[pos] == LF) { pos += LF_SKIP; break; }
      pos++;
    }
    return pos;
  }
}
