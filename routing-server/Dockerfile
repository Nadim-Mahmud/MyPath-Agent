# Stage 1: Build the JAR
FROM gradle:8.12-jdk17 AS builder
WORKDIR /app
COPY gradle gradle/
COPY gradlew build.gradle settings.gradle ./
RUN chmod +x gradlew
COPY src src/
RUN ./gradlew bootJar -x test --no-daemon

# Stage 2: Runtime — JRE only (alpine has no ARM64 variant, use Debian slim)
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=builder /app/build/libs/mypath-0.0.1-SNAPSHOT.jar app.jar

# myPathDataStore is mounted as a volume at runtime (pre-built graph cache or auto-download)
VOLUME /app/myPathDataStore

EXPOSE 8080
ENTRYPOINT ["java", "-Xmx2g", "-jar", "app.jar"]
