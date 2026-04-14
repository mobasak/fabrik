# Coolify API Reference

## Base URL

```bash
https://coolify.vps1.ocoron.com/api/v1
```

## Authentication

```bash
# Use Bearer token in Authorization header
Authorization: Bearer 5|YA40VYboS1RjL4uxt8vaS1Qy4IXc3vLpiiRGjkmw8c2f33b7
```

## Create Docker Image Application

### Endpoint

```bash
POST /applications/dockerimage
```

### Request Body

```json
{
  "project_uuid": "z4ok8804o0s440gsk0wgcggw",
  "server_uuid": "jk4wskkcks8csg4gcokwgw8s",
  "environment_name": "production",
  "docker_registry_image_name": "image:tag",
  "name": "application-name",
  "description": "Application description",
  "domains": "https://domain.vps1.ocoron.com",
  "ports_exposes": "3000",
  "ports_mappings": "3000:3000",
  "health_check_enabled": true,
  "health_check_path": "/",
  "health_check_port": "3000",
  "health_check_host": "localhost",
  "health_check_method": "GET",
  "health_check_return_code": 200,
  "health_check_scheme": "http",
  "health_check_interval": 30,
  "health_check_timeout": 10,
  "health_check_retries": 3,
  "health_check_start_period": 15,
  "limits_memory": "512M",
  "limits_cpus": "1.0",
  "instant_deploy": true
}
```

### Important Notes
- `ports_mappings` must be in format "host:container"
- `health_check_start_period` should be longer for heavy applications (60+ seconds)
- Browserless requires more memory (2G) and longer startup time
- Port 3000 is already used by Gotenberg, use different port for Browserless

## Get Application Status

### Endpoint

```bash
GET /applications/{uuid}
```

### Response
```json
{
  "uuid": "application-uuid",
  "name": "application-name",
  "status": "running:healthy|exited:unhealthy",
  "image": "image:tag"
}
```

## Delete Application

### Endpoint

```bash
DELETE /applications/{uuid}
```

## Get Application Logs

### Endpoint

```bash
GET /applications/{uuid}/logs
```

### Response
```json
{
  "logs": "log content here"
}
```

## Known Issues & Solutions

### Browserless Deployment Issues

- **Memory Requirements**: Browserless needs at least 2G memory
- **Port Conflict**: Cannot use port 3000 (already used by Gotenberg)
- **Startup Time**: Requires longer health_check_start_period (60+ seconds)
- **Health Check**: May need to disable health check initially

### Successful Deployments Examples

#### Gotenberg (Working)

```json
{
  "docker_registry_image_name": "gotenberg/gotenberg:8",
  "ports_mappings": "3000:3000",
  "limits_memory": "512M",
  "health_check_start_period": 15
}
```

#### Browserless (Needs Fix)

```json
{
  "docker_registry_image_name": "browserless/chrome:1-chrome-stable",
  "ports_mappings": "3001:3000",
  "limits_memory": "2G",
  "health_check_start_period": 60,
  "health_check_enabled": false
}
```
