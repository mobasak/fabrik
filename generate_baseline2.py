import dataclasses
import hashlib
import json
import os

from fabrik.wordpress.deployer import SiteDeployer

os.environ.clear()
os.environ["WP_CONTAINER_NAME_OCORON_COM"] = "ocoron-com-wordpress-1"

deployer = SiteDeployer('ocoron.com', dry_run=True)
result = deployer.deploy()

json_str = json.dumps(dataclasses.asdict(result), sort_keys=True)
hash_val = hashlib.sha256(json_str.encode()).hexdigest()

with open('tests/wordpress/fixtures/ocoron_baseline.json', 'w') as f:
    f.write(json_str)

print(f"Hash: {hash_val}")
