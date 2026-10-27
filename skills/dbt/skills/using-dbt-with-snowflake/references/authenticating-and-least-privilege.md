# Authenticating and Least Privilege on Snowflake

## Key-pair authentication for the dbt service user

Use a key pair (`SNOWFLAKE_JWT`) instead of a password, for people and for service users.

1. Generate a key pair. Keep the private key outside the repository and readable only by its owner:

   ```bash
   # private key (PKCS#8, unencrypted here; use an encrypted key if your tooling supports a passphrase)
   openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -nocrypt -out <key_dir>/dbt_rsa_key.p8
   chmod 600 <key_dir>/dbt_rsa_key.p8
   # public key, to register on the user
   openssl rsa -in <key_dir>/dbt_rsa_key.p8 -pubout -out <key_dir>/dbt_rsa_key.pub
   ```

2. An administrator creates the service user and registers the public key (the key body only, without the header lines):

   ```sql
   create user <dbt_user>
     type = service
     default_role = <dbt_role>
     default_secondary_roles = ()        -- no secondary roles: the session has the dbt role's privileges only
     rsa_public_key = '<public key body>';
   ```

3. Read every connection value from the environment in `profiles.yml`:

   ```yaml
   my_project:
     target: test
     outputs:
       test:
         type: snowflake
         account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
         user: "{{ env_var('SNOWFLAKE_USER') }}"
         authenticator: snowflake_jwt
         private_key_path: "{{ env_var('SNOWFLAKE_PRIVATE_KEY_PATH') }}"
         # object names are not secrets: written here, not read from the environment
         role: <dbt_role>
         warehouse: <warehouse>
         database: <test_db>
         schema: <default_schema>
         threads: 4
       prod:
         # same, with database: <prod_db>
   ```

Never commit keys, passwords, account identifiers or local paths. If the project ships an example environment file, it contains placeholders only.

## The secondary-roles trap

A session has a **primary role** and its **secondary roles**. Snowflake authorizes most statements (`SELECT`, DML such as `DELETE` and `UPDATE`, `DROP`) with the privileges of **all** active roles together. Only `CREATE <object>` is authorized by the primary role alone, and a new object is owned by the primary role.

Consequence: setting `role: READ_ONLY_ROLE` does **not** make a session read-only if the user also holds an admin role and secondary roles are active. For the dbt service user, set `default_secondary_roles = ()`. To test a restricted role in your own session:

```sql
use role <restricted_role>;
use secondary roles none;
```

## Never test permissions destructively

Do not prove that a role "cannot write" by running `DELETE`, `DROP`, `TRUNCATE`, `UPDATE` or `CREATE OR REPLACE` against a real table. If an assumption is wrong (secondary roles, an inherited grant), real data is gone. Instead:

```sql
show grants to role <role>;                      -- what the role can do
show grants on table <db>.<schema>.<table>;      -- who can do what on an object
show grants of role <role>;                      -- who holds the role
```

If a write must be exercised, do it on a scratch object created for the test, with secondary roles off.

## Shape of a dbt setup

| Object | Purpose |
|---|---|
| raw database | data as delivered; the loader role writes, the dbt role only reads |
| test and prod databases | where dbt writes; owned by the dbt role; one schema per layer in each |
| dbt service user and role | key pair, `SELECT` on raw, no secondary roles |
| read role for BI or analysts | `SELECT` on the marts only |
| warehouse | a small warehouse for dbt with auto-suspend |

## Where grants live

- Read grants on dbt-built objects: the `+grants` config in `dbt_project.yml`, or a `post_hook` for objects `+grants` does not cover.
- `copy_grants: true` keeps grants when dbt replaces a table or view (`dbt-snowflake` adds `COPY GRANTS`).
- Future grants need the `MANAGE GRANTS` privilege; if the dbt role does not have it, define grants through dbt.
- Keep the one-time admin SQL (databases, roles, users, grants) in a reviewed script that an administrator runs; an agent does not run it on its own.
