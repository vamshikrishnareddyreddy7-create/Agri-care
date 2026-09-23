# Database

## Schema

`schema.sql` defines the MySQL schema: `users`, `equipment`, `maintenance`,
`operational_data`, `predictions`, `chat_history`, `notifications`, and
`password_reset` (hashed single-use reset tokens).

## Two ways to initialize

1. **Automatic (used by the app)** — when MySQL env vars are configured, the
   app connects and runs the `CREATE TABLE IF NOT EXISTS` statements from
   `schema.sql` on startup. No manual step needed; existing data is untouched.

2. **Manual** — full control, run from the project root:

   ```bash
   mysql -u root -p < database/schema.sql
   ```

## Connecting the app

Set the environment variables (in `.env` locally, or in the Render dashboard):

- Either `DATABASE_URL=mysql://user:password@host:3306/dbname`
  (URL-encode special characters in the password — this is the format Render's
  internal connection string uses), or the individual `MYSQL_HOST`,
  `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`.
- With no MySQL configured the app runs in Demo Mode on bundled sample data —
  all features work, data lives only in process memory.
