# Elastic Cloud Setup Guide

This guide will help you set up authentication for connecting the OTEL Query Server to your Enterprise Elastic Cloud deployment.

## Getting Your Elastic Cloud API Key

### Method 1: Using Kibana Dev Tools (Recommended)

1. **Navigate to Kibana Dev Tools**:
   - Go to: https://dcsites-non-prod-usw2.kb.us-west-2.aws.found.io:9243/app/dev_tools#/console

2. **Create an API Key**:
   Execute this command in the Dev Tools console:
   ```json
   POST /_security/api_key
   {
     "name": "otel-query-server-key",
     "role_descriptors": {
       "otel_reader": {
         "cluster": ["monitor"],
         "indices": [
           {
             "names": ["*"],
             "privileges": ["read", "view_index_metadata"]
           }
         ]
       }
     },
     "metadata": {
       "application": "otel-query-server",
       "environment": "testing"
     }
   }
   ```

3. **Save the Response**:
   The response will look like:
   ```json
   {
     "id": "xxx",
     "name": "otel-query-server-key",
     "api_key": "yyy",
     "encoded": "base64_encoded_key_here"
   }
   ```
   
   **Important**: Save the `encoded` value - this is your API key!

### Method 2: Using Kibana UI

1. **Navigate to Stack Management**:
   - Click on the hamburger menu (☰)
   - Go to Management → Stack Management

2. **Create API Key**:
   - Under Security, click "API Keys"
   - Click "Create API key"
   - Name: `otel-query-server-key`
   - Set appropriate privileges (at minimum: read access to indices)
   - Click "Create API key"

3. **Copy the API Key**:
   - Copy the generated API key (base64 encoded format)
   - Store it securely

### Method 3: Using Elasticsearch REST API

If you have credentials already, you can use curl:

```bash
curl -X POST "https://dcsites-non-prod-usw2.es.us-west-2.aws.found.io:9243/_security/api_key" \
  -H "Content-Type: application/json" \
  -u "username:password" \
  -d '{
    "name": "otel-query-server-key",
    "role_descriptors": {
      "otel_reader": {
        "cluster": ["monitor", "read"],
        "indices": [
          {
            "names": ["*"],
            "privileges": ["read", "view_index_metadata"]
          }
        ]
      }
    }
  }'
```

## Using the API Key

Once you have the API key, update your `config-elastic-test.yaml`:

```yaml
elastic_cloud:
  enabled: true
  elasticsearch_url: https://dcsites-non-prod-usw2.es.us-west-2.aws.found.io:9243
  api_key: "YOUR_BASE64_ENCODED_API_KEY_HERE"
```

Or use environment variables:

```bash
export OTEL_QUERY_BACKENDS__ELASTIC_CLOUD__API_KEY="YOUR_BASE64_ENCODED_API_KEY_HERE"
```

## Testing the Connection

1. **Start the server**:
   ```bash
   python -m otel_query_server.server --config config-elastic-test.yaml
   ```

2. **Test with MCP client**:
   ```bash
   mcp-client connect stdio -- python -m otel_query_server.server --config config-elastic-test.yaml
   ```

3. **Query server info**:
   Use the `get_server_info` tool to verify the connection is working.

## Troubleshooting

### SSL Certificate Issues

If you encounter SSL certificate errors, you can temporarily disable certificate verification (not recommended for production):

```yaml
elastic_cloud:
  verify_certs: false
```

### Authentication Errors

- Ensure you're using the `encoded` value from the API key response, not the raw `api_key`
- Check that the API key has the necessary permissions
- Verify the Elasticsearch URL is correct (should end with :9243, not include /app/...)

### Connection Timeouts

Increase the timeout if needed:

```yaml
elastic_cloud:
  timeout_seconds: 60
``` 