# Installing dbt Fusion

## PROBLEM

dbt Fusion (`dbtf`) must be installed and working before starting a cross-platform migration. Fusion provides the real-time compilation engine and rich error diagnostics that power the migration workflow.

## SOLUTION

### Check if Fusion is already installed

```bash
dbtf --version
```

If this returns a version number, Fusion is installed. Verify it can connect to your project:

```bash
dbtf debug
```

### Install Fusion

If `dbtf` is not found, install it following the official instructions:

**Using the install script**:
```bash
curl -fsSL https://public.cdn.getdbt.com/fs/install.sh | bash
```

**Verify installation**:
```bash
dbtf --version
dbtf debug
```

### Minimum requirements

- dbt Fusion must be able to connect to both the source and target platforms
- Run `dbtf debug` with each profile to verify connectivity before starting migration

## CHALLENGES

### Connection errors with dbtf debug

If `dbtf debug` fails to connect:
1. Verify your `profiles.yml` has the correct credentials
2. Check that the target warehouse/cluster is running and accessible
3. Ensure any required drivers are installed (e.g., Databricks ODBC/Simba driver)
4. Try the connection with standard `dbt debug` first to isolate Fusion-specific issues

### Fusion version compatibility

If you encounter unexpected parsing or compilation behavior, ensure you're running a recent version of Fusion:
```bash
dbtf --version
```

If Fusion is already installed, you can updated it to the latest version with
```bash
dbtf system update 
```