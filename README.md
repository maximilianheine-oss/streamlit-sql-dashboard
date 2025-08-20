# Zeiterfassung Dashboard mit Streamlit

Kostenloses, webbasiertes Dashboard mit direkter SQL Synchronisierung.

## Schnellstart auf Streamlit Cloud

1. Erstelle ein neues GitHub Repository und lade **app.py** und **requirements.txt** hoch.
2. Gehe zu https://streamlit.io/cloud und wähle **New app**. Verbinde dein Repo.
3. Setze **Secrets** für die Datenbank unter **Settings -> Secrets** zum Beispiel

```toml
# Variante 1 Ein Connection String
DATABASE_URL = "postgresql+psycopg2://user:pass@host:5432/dbname"

# Variante 2 Einzelwerte
DB_DIALECT = "postgresql"   # oder mysql oder mssql
DB_HOST = "db.example.com"
DB_PORT = "5432"
DB_NAME = "mfr"
DB_USER = "reporting_user"
DB_PASSWORD = "supersecret"

# Tabellen und Spaltennamen an euer Schema anpassen
TABLE_NAME = "time_events"
COL_EMPLOYEE = "employee_name"
COL_START = "start_time"
COL_END = "end_time"
COL_WORK_H = "work_hours"
COL_TRAVEL_H = "travel_hours"
COL_PLANT_H = "plant_hours"
COL_VAC = "vacation_flag"
COL_SICK = "sick_flag"
COL_PROJECT = "project_name"
COL_TEAM = "team_name"
```

4. Starte die App. Fertig. Das Dashboard lädt die Daten direkt aus SQL und ist per Link erreichbar.

## Hinweis zu MFR

Falls MFR keine fertige Tabelle in genau dieser Form liefert, erstelle eine **SQL View** die die benötigten Spalten bereitstellt. Beispiel

```sql
CREATE VIEW time_events AS
SELECT
  m.name          AS employee_name,
  z.start_time    AS start_time,
  z.end_time      AS end_time,
  EXTRACT(EPOCH FROM (z.end_time - z.start_time))/3600.0 AS work_hours,
  z.travel_hours  AS travel_hours,
  z.plant_hours   AS plant_hours,
  CASE WHEN a.type = 'Urlaub' THEN 1 ELSE 0 END AS vacation_flag,
  CASE WHEN a.type = 'Krankheit' THEN 1 ELSE 0 END AS sick_flag,
  p.project_name  AS project_name,
  t.team_name     AS team_name
FROM zeitbuchungen z
JOIN mitarbeiter m ON m.id = z.employee_id
LEFT JOIN projekte p ON p.id = z.project_id
LEFT JOIN teams t ON t.id = m.team_id
LEFT JOIN abwesenheiten a ON a.employee_id = m.id
  AND DATE(z.start_time) BETWEEN a.start_date AND a.end_date;
```

Passe Syntax und Funktionen an deinen Datenbanktyp an.