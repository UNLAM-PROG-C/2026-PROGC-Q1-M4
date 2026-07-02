package com.m4;

import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import com.rabbitmq.client.MessageProperties;
import com.rabbitmq.client.AMQP;
import java.util.UUID;

import java.nio.charset.StandardCharsets;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;

public class RabbitPublisher {

  private static final String QUEUE_NAME = "image_queue";
  private static final int TIMEOUT_SECONDS = 90;
  private static final int BLOCK_RESPONSE_QUEUE_SIZE = 1;

  private static final String DEFAULT_EXCHANGE = "";
  private static final String REPLY_QUEUE_PREFIX = "reply.";
  private static final int PERSISTENT_DELIVERY_MODE = 2;

  private static final boolean QUEUE_DURABLE = true;
  private static final boolean QUEUE_EXCLUSIVE = false;
  private static final boolean QUEUE_AUTO_DELETE = false;
  private static final boolean REPLY_QUEUE_EXCLUSIVE = false;
  private static final boolean REPLY_QUEUE_AUTO_DELETE = true;
  private static final boolean CONSUMER_AUTO_ACK = true;

  private static final String HOST_ENV_VAR = "RABBITMQ_HOST";
  private static final String PORT_ENV_VAR = "RABBITMQ_PORT";
  private static final String USER_ENV_VAR = "RABBITMQ_USER";
  private static final String PASS_ENV_VAR = "RABBITMQ_PASS";
  private static final String DEFAULT_HOST = "host.docker.internal";
  private static final String DEFAULT_PORT = "30672";
  private static final String DEFAULT_USER = "admin";
  private static final String DEFAULT_PASS = "admin";

  private static final String TIMEOUT_ERROR_MESSAGE = "Timeout esperando resultado del worker";

  private final ConnectionFactory factory;

  public RabbitPublisher() {
    factory = new ConnectionFactory();
    factory.setHost(System.getenv().getOrDefault(HOST_ENV_VAR, DEFAULT_HOST));
    factory.setPort(Integer.parseInt(System.getenv().getOrDefault(PORT_ENV_VAR, DEFAULT_PORT)));
    factory.setUsername(System.getenv().getOrDefault(USER_ENV_VAR, DEFAULT_USER));
    factory.setPassword(System.getenv().getOrDefault(PASS_ENV_VAR, DEFAULT_PASS));
  }

  public void publish(byte[] imageBytes) throws Exception {
    try (Connection connection = factory.newConnection();
         Channel channel = connection.createChannel()) {

      channel.queueDeclare(QUEUE_NAME, QUEUE_DURABLE, QUEUE_EXCLUSIVE, QUEUE_AUTO_DELETE, null);
      channel.basicPublish(DEFAULT_EXCHANGE, QUEUE_NAME, MessageProperties.PERSISTENT_BASIC, imageBytes);
      System.out.println("Imagen publicada en la cola. Tamaño: " + imageBytes.length + " bytes");
    }
  }

  public String waitQueue(byte[] imageBytes) throws Exception {
    try (Connection connection = factory.newConnection();
         Channel channel = connection.createChannel()) {

      channel.queueDeclare(QUEUE_NAME, QUEUE_DURABLE, QUEUE_EXCLUSIVE, QUEUE_AUTO_DELETE, null);

      String correlationId = UUID.randomUUID().toString();
      String replyQueue = REPLY_QUEUE_PREFIX + correlationId;
      channel.queueDeclare(replyQueue, QUEUE_DURABLE, REPLY_QUEUE_EXCLUSIVE, REPLY_QUEUE_AUTO_DELETE, null);

      return publishAndAwaitResult(channel, imageBytes, correlationId, replyQueue);
    }
  }

  private String publishAndAwaitResult(Channel channel, byte[] imageBytes, String correlationId, String replyQueue)
      throws Exception {
    AMQP.BasicProperties props = buildReplyProperties(correlationId, replyQueue);
    BlockingQueue<String> response = new ArrayBlockingQueue<>(BLOCK_RESPONSE_QUEUE_SIZE);

    // Primero suscribirse, después publicar
    String consumerTag = consumeResult(channel, replyQueue, correlationId, response);

    channel.basicPublish(DEFAULT_EXCHANGE, QUEUE_NAME, props, imageBytes);
    System.out.println("Imagen publicada. Tamaño: " + imageBytes.length
        + " bytes. Esperando respuesta en " + replyQueue + "...");

    String result = response.poll(TIMEOUT_SECONDS, TimeUnit.SECONDS);
    channel.basicCancel(consumerTag);

    if (result == null) throw new RuntimeException(TIMEOUT_ERROR_MESSAGE);
    return result;
  }

  private static AMQP.BasicProperties buildReplyProperties(String correlationId, String replyQueue) {
    return new AMQP.BasicProperties.Builder()
        .correlationId(correlationId)
        .replyTo(replyQueue)
        .deliveryMode(PERSISTENT_DELIVERY_MODE)
        .build();
  }

  private static String consumeResult(Channel channel, String replyQueue, String correlationId,
      BlockingQueue<String> response) throws Exception {
    return channel.basicConsume(replyQueue, CONSUMER_AUTO_ACK,
        (tag, delivery) -> deliverIfMatches(delivery, correlationId, response),
        tag -> {}
    );
  }

  private static void deliverIfMatches(com.rabbitmq.client.Delivery delivery, String correlationId,
      BlockingQueue<String> response) {
    if (correlationId.equals(delivery.getProperties().getCorrelationId())) {
      String body = new String(delivery.getBody(), StandardCharsets.UTF_8);
      System.out.println("Respuesta del worker recibida: " + body);
      response.offer(body);
    }
  }
}
