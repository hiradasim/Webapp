# Task Manager Webapp

This simple web application allows users to log in from multiple devices and manage their tasks.

## Features
- User login with session handling.
- View and add personal tasks.
- Each user has a role and belongs to one or more branches.
- Tasks and user metadata are stored persistently in `data/users.json`.

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   flask --app app run
   ```

## Running tests
```bash
pytest
```
