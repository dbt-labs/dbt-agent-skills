# Review dbt Run Results

## When to Use

If a user tells you there is a problem with the project, review the `target/run_results.json` file to identify which resources failed and why.

Check the `metadata.generated_at` key to ensure the information is fresh.

## Python Script

```python
import json

def review_dbt_run_results(run_results_path: str):
    """Review dbt run_results.json and identify failures."""
    with open(run_results_path) as f:
        data = json.load(f)
    
    results = data.get('results', [])
    failed = [r for r in results if r.get('status') == 'error']
    
    print(f"Total: {len(results)} | Failed: {len(failed)}")
    
    if failed:
        print("\nFailed Resources:")
        for r in failed:
            # Extract resource name from unique_id (e.g., "model.project.name" -> "name")
            resource_name = r['unique_id'].split('.')[-1]
            resource_type = r['unique_id'].split('.')[0]
            
            print(f"\n- {resource_type}: {resource_name}")
            
            # Parse error message for key details
            message = r.get('message', '')
            if message:
                # Extract the main error line
                error_lines = [line for line in message.split('\n') if line.strip()]
                print(f"  Error: {error_lines[0] if error_lines else message}")
            
            # Show compiled SQL if available
            compiled = r.get('compiled_code', '').strip()
            if compiled and len(compiled) < 200:
                print(f"  SQL: {compiled}")
            elif compiled:
                print(f"  SQL: {compiled[:200]}...")
    
    return failed

# Usage
failed_resources = review_dbt_run_results('target/run_results.json')
```
