# Task Manager Webapp

This simple web application allows users to log in from multiple devices and manage their tasks.

## Features
- User login with session handling.
- View and add personal tasks with a priority (High, Mid, or Low).
- Each user has a role and belongs to one or more branches.
- Tasks and user metadata are stored persistently in `data/users.json`.
- Owners, Leaders, and IT staff can view everyone's tasks and assign tasks to any user.
- Responsive Bootstrap-based interface for a cleaner look and easier navigation.


### Sample accounts
- `Ali` / `password` – Owner for branches Mzone & UNIPRO
- `sadegh` / `password` – Worker for branches Mzone & UNIPRO
- `X` / `password` – Leader for branch UNIPRO
- `pedram` / `password` – IT for branch Babol


- Owners, Leaders, and IT staff can view everyone's tasks and assign tasks to any user.

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
