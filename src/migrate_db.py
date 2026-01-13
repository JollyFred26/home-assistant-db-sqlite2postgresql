import sqlite3
import psycopg2
from psycopg2 import sql
import logging
import io
import binascii
import csv

# Configuration
SQLITE_DB_PATH = 'c:/temp/tmp/home-assistant_v2-prod.db'
PG_HOST = 'myurl'
PG_DB = 'my ha db name'
PG_PORT = 'my port'
PG_USER = 'my user'
PG_PASSWORD = 'my password'

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Connexion à SQLite
sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
sqlite_conn.text_factory = str  # Pour éviter les erreurs d'encodage
sqlite_cursor = sqlite_conn.cursor()

# Connexion à PostgreSQL
pg_conn = psycopg2.connect(
    host=PG_HOST,
    database=PG_DB,
    user=PG_USER,
    password=PG_PASSWORD,
    port = PG_PORT
)
pg_cursor = pg_conn.cursor()

# Désactiver les contraintes de clé étrangère
pg_cursor.execute("SET session_replication_role = 'replica';")

# Colonnes booléennes à convertir
BOOLEAN_COLUMNS = {
    'statistics_meta': ['has_mean', 'has_sum', 'has_min', 'has_max'],
    'recorder_runs': ['closed_incorrect'],  # Ajout de la colonne booléenne de recorder_runs
}

# Fonction pour migrer une table avec COPY
def migrate_table_with_copy(table_name):
    logging.info(f"Migration de la table : {table_name}")

    # Récupérer les données de SQLite
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()

    if not rows:
        logging.info(f"Aucune donnée dans la table {table_name}")
        return

    # Récupérer les noms de colonnes
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = sqlite_cursor.fetchall()
    columns = [column[1] for column in columns_info]

    # Créer un fichier temporaire en mémoire pour COPY
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(columns)  # Écrire les en-têtes

    for row in rows:
        # Convertir les valeurs booléennes si nécessaire
        row = list(row)
        if table_name in BOOLEAN_COLUMNS:
            for i, col in enumerate(columns):
                if col in BOOLEAN_COLUMNS[table_name]:
                    if row[i] == 0:
                        row[i] = 'false'
                    elif row[i] == 1:
                        row[i] = 'true'
        # Convertir les données binaires en format hexadécimal pour bytea
        if table_name in ['events', 'states']:
            for i, col in enumerate(columns):
                if col.endswith('_bin') or col == 'context_id_bin':
                    if isinstance(row[i], bytes):
                        row[i] = binascii.hexlify(row[i]).decode('utf-8')
        writer.writerow(row)

    # Revenir au début du fichier virtuel
    output.seek(0)

    # Utiliser COPY pour importer les données
    try:
        pg_cursor.copy_expert(
            f"COPY {table_name} ({','.join(columns)}) FROM STDIN WITH (FORMAT CSV, HEADER)",
            output
        )
        pg_conn.commit()
        logging.info(f"Migration terminée pour {table_name}")
    except Exception as e:
        logging.error(f"Erreur lors de l'import COPY pour {table_name}: {e}")
        pg_conn.rollback()

# Fonction pour migrer la table recorder_runs avec INSERT
def migrate_recorder_runs_with_insert():
    logging.info("Migration de la table 'recorder_runs' avec INSERT...")

    # Récupérer les données de SQLite
    sqlite_cursor.execute(f"SELECT * FROM recorder_runs")
    rows = sqlite_cursor.fetchall()

    if not rows:
        logging.info(f"Aucune donnée dans la table recorder_runs")
        return

    # Récupérer les noms de colonnes
    sqlite_cursor.execute(f"PRAGMA table_info(recorder_runs)")
    columns_info = sqlite_cursor.fetchall()
    columns = [column[1] for column in columns_info]

    # Préparer la requête d'insertion
    placeholders = ', '.join(['%s'] * len(columns))
    query = sql.SQL("INSERT INTO recorder_runs ({}) VALUES ({})").format(
        sql.SQL(', ').join(map(sql.Identifier, columns)),
        sql.SQL(', ').join([sql.Placeholder()] * len(columns))
    )

    # Insérer les données
    for row in rows:
        try:
            # Convertir les valeurs booléennes si nécessaire
            row = list(row)
            for i, col in enumerate(columns):
                if col in ['closed_incorrect']:
                    if row[i] == 0:
                        row[i] = False
                    elif row[i] == 1:
                        row[i] = True
            pg_cursor.execute(query, row)
        except Exception as e:
            logging.error(f"Erreur lors de l'insertion dans recorder_runs: {e}")
            pg_conn.rollback()
            continue

    pg_conn.commit()
    logging.info(f"Migration terminée pour recorder_runs")

# Liste des tables dans l'ordre des dépendances
tables_order = [
    'event_data',
    'event_types',
    'states_meta',
    'state_attributes',
    'statistics_meta',
    'statistics_runs',
    'schema_changes',
    'events',
    'states',
    'statistics',
    'statistics_short_term',
    'recorder_runs',
    'migration_changes'
]

# Migrer toutes les tables dans l'ordre
for table in tables_order:
    try:
        if table == 'recorder_runs':
            migrate_recorder_runs_with_insert()
        else:
            migrate_table_with_copy(table)
    except Exception as e:
        logging.error(f"Erreur globale lors de la migration de {table}: {e}")
        continue

# Réactiver les contraintes de clé étrangère
pg_cursor.execute("SET session_replication_role = 'origin';")
pg_conn.commit()

for table in tables_order:
    # Récupérer le nom de la clé primaire
    pg_cursor.execute(f"""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = '{table}'::regclass AND i.indisprimary
    """)
    primary_key = pg_cursor.fetchone()[0]

    # Trouver l'ID maximum actuel
    pg_cursor.execute(f"SELECT MAX({primary_key}) FROM {table}")
    max_id = pg_cursor.fetchone()[0]

    # Réinitialiser la séquence d'ID
    if max_id is not None:
        if isinstance(max_id, int):
            pg_cursor.execute(f"ALTER SEQUENCE {table}_{primary_key}_seq RESTART WITH {max_id + 1}")
            print(f"Séquence d'ID pour la table {table} réinitialisée à {max_id + 1}")

        pg_conn.commit()
 
# Fermer les connexions
sqlite_conn.close()
pg_conn.close()

logging.info("Migration terminée avec succès pour toutes les tables !")
