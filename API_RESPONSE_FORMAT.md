# Authentication API Response Format

This document describes the expected format for the authentication API response that the Smart Calendar application expects.

## Endpoint

**POST** `/v1/auth/login`

## Request Format

```json
{
  "email": "user@example.com",
  "password": "userpassword",
  "remember_me": true
}
```

## Response Format

The API should return a JSON response with the following structure:

```json
{
  "user_id": "12345",
  "email": "user@example.com",
  "name": "John Doe",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "refresh_token_string_here",
  "token_expires_at": "2024-12-31T23:59:59Z",
  "subscription": {
    "tier": "premium",
    "status": "active",
    "expires_at": "2024-12-31T23:59:59Z",
    "features": ["feature1", "feature2", "feature3"]
  },
  "timezone": "America/New_York",
  "language": "en",
  "avatar_url": "https://example.com/avatars/user123.jpg",
  "organization": {
    "id": "org_123",
    "name": "Acme Corporation"
  },
  "role": "user",
  "api_version": "v1",
  "server_timestamp": "2024-01-15T10:30:00Z"
}
```

## Field Descriptions

### Required Fields

- **user_id** (string): Unique identifier for the user in the external system
- **email** (string): User's email address
- **name** (string): User's full name
- **access_token** (string): JWT or session token for API authentication

### Optional Fields

- **refresh_token** (string): Token used to refresh the access token
- **token_expires_at** (ISO 8601 datetime): When the access token expires
- **subscription** (object): Subscription information
  - **tier** (string): Subscription tier - `free`, `basic`, `premium`, `enterprise`
  - **status** (string): Subscription status - `active`, `cancelled`, `expired`, `trial`
  - **expires_at** (ISO 8601 datetime): When subscription expires
  - **features** (array of strings): List of enabled features
- **timezone** (string): User's timezone (IANA timezone name)
- **language** (string): User's preferred language code (e.g., "en", "es")
- **avatar_url** (string): URL to user's avatar image
- **organization** (object): Organization information
  - **id** (string): Organization identifier
  - **name** (string): Organization name
- **role** (string): User role - `user`, `admin`, `manager`
- **api_version** (string): API version used
- **server_timestamp** (ISO 8601 datetime): Server timestamp

## Error Responses

### 401 Unauthorized
```json
{
  "error": "Invalid credentials",
  "message": "Email or password is incorrect"
}
```

### 403 Forbidden
```json
{
  "error": "Account disabled",
  "message": "Your account has been disabled. Please contact support."
}
```

### 500 Internal Server Error
```json
{
  "error": "Server error",
  "message": "An internal server error occurred. Please try again later."
}
```

## Health Check Endpoint

**GET** `/v1/health`

Should return HTTP 200 if the server is operational.

## Notes

- All datetime fields should be in ISO 8601 format with timezone information
- The application stores the authentication data locally after successful login
- Tokens are stored securely in the local database
- The application checks token expiration and may prompt for re-authentication if expired
- Subscription features can be used to enable/disable features in the application
