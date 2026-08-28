# Flask Users API

A small Flask CRUD API with SQLite storage and a browser dashboard for managing users.

## Features

- Create, read, update, and delete users
- Email validation and duplicate-email protection
- Pagination for the user list
- Search and sorting for the user list
- Dashboard edit, delete, search, and pagination controls
- API-key protection for write operations
- SQLite database using Flask-SQLAlchemy
- Simple responsive browser UI
- Automated API tests

## Project Structure

```text
API/
|-- main.py             Flask application and API routes
|-- templates/
|   `-- index.html      Browser dashboard
|-- test_api.py         API regression tests
|-- requirements.txt    Python dependencies
|-- .env.example        Environment variable template
|-- .gitignore          Local files excluded from Git
`-- instance/            SQLite database location
```

## Requirements

- Python 3.10 or newer
- PowerShell on Windows

## Installation

Open PowerShell in the project directory:

```powershell
cd D:\Manju\API

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this once for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

You can also run commands without activating the environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project directory by copying `.env.example`:

```powershell
Copy-Item .env.example .env
```

Edit `.env`:

```env
DATABASE_URL=sqlite:///users.db
API_KEY=replace-with-a-long-random-value
FLASK_DEBUG=0
```

`API_KEY` is required for `POST`, `PUT`, `PATCH`, and `DELETE` requests. Keep `.env` private and do not commit it.

## Run the Application

```powershell
.\.venv\Scripts\python.exe .\main.py
```

Open the dashboard:

```text
http://127.0.0.1:5000/
```

The API health endpoint is:

```text
http://127.0.0.1:5000/api
```

The SQLite database is created automatically on first startup.

## API Endpoints

| Method | URL | API key | Description |
|---|---|---:|---|
| GET | `/api` | No | API health check |
| GET | `/users` | No | List users |
| GET | `/stats` | No | User count and latest signup |
| GET | `/users/<id>` | No | Get one user |
| POST | `/users` | Yes | Create a user |
| PUT | `/users/<id>` | Yes | Replace a user |
| PATCH | `/users/<id>` | Yes | Update selected fields |
| DELETE | `/users/<id>` | Yes | Delete a user |

### List Users

```powershell
Invoke-RestMethod http://127.0.0.1:5000/users
```

Optional pagination parameters:

```text
GET /users?page=1&per_page=20
```

The response contains `items`, `page`, `per_page`, `total`, and `pages`.

Search by name or email and sort the results:

```text
GET /users?q=ada&sort=name&order=asc&page=1&per_page=20
```

### Statistics

```powershell
Invoke-RestMethod http://127.0.0.1:5000/stats
```

This returns the total number of users and the latest signup timestamp.

### Get One User

```powershell
Invoke-RestMethod http://127.0.0.1:5000/users/1
```

### Create a User

```powershell
$headers = @{
    "X-API-Key" = "replace-with-a-long-random-value"
}
$body = @{
    name = "Ada Lovelace"
    email = "ada@example.com"
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:5000/users `
    -Method Post `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### Replace a User with PUT

PUT requires both `name` and `email`:

```powershell
$body = @{
    name = "Ada Byron Lovelace"
    email = "ada@example.com"
} | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:5000/users/1 `
    -Method Put `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### Update a User with PATCH

PATCH accepts one or both fields:

```powershell
$body = @{ name = "Ada Lovelace" } | ConvertTo-Json

Invoke-RestMethod http://127.0.0.1:5000/users/1 `
    -Method Patch `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $body
```

### Delete a User

```powershell
Invoke-RestMethod http://127.0.0.1:5000/users/1 `
    -Method Delete `
    -Headers $headers
```

## Error Responses

Errors are returned as JSON:

```json
{
  "error": "Email already exists"
}
```

Common status codes:

- `200` successful read, update, or delete
- `201` user created
- `400` invalid request data
- `401` missing or invalid API key
- `404` user does not exist
- `409` duplicate email or data conflict
- `503` API key is not configured

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

The tests use the Flask test client and clear the user table between tests.

## Creating Another API Route

Add a route in `main.py` using Flask's route decorator:

```python
@app.route("/example", methods=["GET"])
def example():
    return jsonify({"message": "Example response"}), 200
```

For a protected write route, add `@require_api_key` below the route decorator:

```python
@app.route("/example", methods=["POST"])
@require_api_key
def create_example():
    data = request.get_json(silent=True)
    return jsonify(data), 201
```

For a new database model, define a class that extends `db.Model`:

```python
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
```

Restart the application after changing the model so `db.create_all()` can create new tables. For production schema changes, use a migration tool such as Flask-Migrate instead of relying on `create_all()`.

## Production Notes

The built-in Flask server is intended for development. For production, use a WSGI server such as Waitress or Gunicorn, place the app behind HTTPS, use a production database, and replace the simple API key with a proper authentication and authorization system.
