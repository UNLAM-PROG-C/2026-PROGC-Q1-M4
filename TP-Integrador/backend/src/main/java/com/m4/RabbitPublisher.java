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

    private static final String QUEUE_NAME           = "image_queue";
    private static final int    TIMEOUT_SECONDS      = 90;
    private static final int    BLOCKRESPONSE_QUEUE_SIZE = 1;

    private final ConnectionFactory factory;

    public RabbitPublisher() {
        factory = new ConnectionFactory();
        factory.setHost(System.getenv().getOrDefault("RABBITMQ_HOST", "host.docker.internal"));
        factory.setPort(Integer.parseInt(System.getenv().getOrDefault("RABBITMQ_PORT", "30672")));
        factory.setUsername(System.getenv().getOrDefault("RABBITMQ_USER", "admin"));
        factory.setPassword(System.getenv().getOrDefault("RABBITMQ_PASS", "admin"));
    }

    public void publish(byte[] imageBytes) throws Exception {
        try (Connection connection = factory.newConnection();
             Channel channel = connection.createChannel()) {

            channel.queueDeclare(QUEUE_NAME, true, false, false, null);
            channel.basicPublish("", QUEUE_NAME, MessageProperties.PERSISTENT_BASIC, imageBytes);
            System.out.println("Imagen publicada en la cola. Tamaño: " + imageBytes.length + " bytes");
        }
    }

    public String waitQueue(byte[] imageBytes) throws Exception {
        try (Connection connection = factory.newConnection();
             Channel channel = connection.createChannel()) {

            channel.queueDeclare(QUEUE_NAME, true, false, false, null);

            String correlationId = UUID.randomUUID().toString();
            String replyQueue    = "reply." + correlationId;

            channel.queueDeclare(replyQueue, true, false, true, null);
            //                               durable  excl  autoDelete

            AMQP.BasicProperties props = new AMQP.BasicProperties.Builder()
                .correlationId(correlationId)
                .replyTo(replyQueue)
                .deliveryMode(2)
                .build();

            BlockingQueue<String> response = new ArrayBlockingQueue<>(BLOCKRESPONSE_QUEUE_SIZE);

            // ✅ Primero suscribirse, después publicar
            String consumerTag = consumeResult(channel, replyQueue, correlationId, response);

            channel.basicPublish("", QUEUE_NAME, props, imageBytes);
            System.out.println("Imagen publicada. Tamaño: " + imageBytes.length + " bytes. Esperando respuesta en " + replyQueue + "...");

            String result = response.poll(TIMEOUT_SECONDS, TimeUnit.SECONDS);
            channel.basicCancel(consumerTag);

            if (result == null) throw new RuntimeException("Timeout esperando resultado del worker");
            return result;
        }
    }

    private static String consumeResult(Channel channel, String replyQueue, String correlationId, BlockingQueue<String> response) throws Exception {
        return channel.basicConsume(replyQueue, true,
            (tag, delivery) -> {
                if (correlationId.equals(delivery.getProperties().getCorrelationId())) {
                    String body = new String(delivery.getBody(), StandardCharsets.UTF_8);
                    System.out.println("Respuesta del worker recibida: " + body);
                    response.offer(body);
                }
            },
            tag -> {}
        );
    }
}