# ============================  
# Build stage (Native AOT)  
# ============================  
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build  
  
WORKDIR /src  
  
# Copy project file first for layer caching  
COPY SealEngine.csproj ./  
  
# Restore WITH runtime identifier (critical for AOT correctness)  
RUN dotnet restore \  
    -r linux-x64  
  
# Copy the rest of the source  
COPY . .  
  
# Publish (AOT settings come from csproj)  
RUN dotnet publish \  
    -c Release \  
    -r linux-x64 \  
    --self-contained true \  
    -o /out \  
    -p:StripSymbols=true \  
    -p:OptimizationPreference=Speed  
  
# ============================  
# Runtime stage (distroless)  
# ============================  
FROM mcr.microsoft.com/dotnet/runtime-deps:8.0-azurelinux3.0-distroless  
  
WORKDIR /app  
  
# Explicit runtime invariants  
ENV ASPNETCORE_URLS=http://0.0.0.0:8080 \  
    DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true \  
    DOTNET_EnableDiagnostics=0  
  
# Copy the native binary  
COPY --from=build /out/SealEngine /app/SealEngine  
  
# Service port  
EXPOSE 8080  
  
# Distroless non-root user  
USER nonroot  
  
# Native AOT binary — no dotnet host  
ENTRYPOINT ["/app/SealEngine"]  