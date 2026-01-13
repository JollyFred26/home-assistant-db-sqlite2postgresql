# home-assistant-db-sqlite2postgresql

---

# Migration of Home Assistant from SQLite to PostgreSQL

This project provides a method to migrate the Home Assistant database from SQLite to PostgreSQL. It includes instructions for creating the PostgreSQL database, managing the `ha` user, and creating the necessary tables.

---

## Prerequisites

- PostgreSQL installed and running
- Python 3.x installed
- Required Python libraries: `psycopg2`
- Save your home assistant sqlite database to home-assistant_v2-prod.db
---

## Migration Steps

### 1. Create the Database and User

1. **Create the `ha` user**:
   ```bash
   sudo -u postgres createuser ha
   ```

2. **Create the `homeassistant` database**:
   ```bash
   sudo -u postgres createdb homeassistant
   ```

3. **Grant privileges**:
   ```bash
   sudo -u postgres psql
   GRANT ALL PRIVILEGES ON DATABASE homeassistant TO ha;
   ```

---

### 2. Create the Tables

Use the `homeassistant-postgresql.sql` file to create the necessary tables in the PostgreSQL database.

```bash
psql -h IP_DU_CONTENEUR_POSTGRES -U ha -d homeassistant -f homeassistant-postgresql.sql
```

---

### 3. Execute the Python Code

1. **Create a virtual environment (venv)**:
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment**:
   - On Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

3. **Install dependencies**:
   ```bash
   pip install psycopg2
   ```

4. **Customize Your Parameters in migrate_db.py file**:
   ```python
   SQLITE_DB_PATH = '/your-location/home-assistant_v2-prod.db'
   PG_HOST = 'postgresql-server'
   PG_DB = 'homeassistant'
   PG_PORT = 'your-port'
   PG_USER = 'ha'
   PG_PASSWORD = 'your-password'
   ```

5. **Run the Python script**:
   ```bash
   python3 migrate_db.py
   ```

---

## Included Files

- `homeassistant-postgresql.sql`: SQL file to create the tables for the Home Assistant database in PostgreSQL.
- `migrate_db.py`: Python script to reset the ID sequences after copying the data.

---

## Conclusion

By following these steps, you can migrate the Home Assistant database from SQLite to PostgreSQL and ensure everything works correctly.
