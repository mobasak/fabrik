import dataclasses
import json
import os

from fabrik.wordpress.deployer import SiteDeployer

os.environ.pop("WP_ADMIN_PASSWORD", None)
os.environ["WP_CONTAINER_NAME_OCORON_COM"] = "ocoron-com-wordpress-1"

deployer = SiteDeployer("ocoron.com", dry_run=True)
result = deployer.deploy()
# substitute CreatedPage if any (dry run should have none or empty)
result_dict = dataclasses.asdict(result)
with open("tests/wordpress/fixtures/ocoron_baseline.json", "w") as f:
    json.dump(result_dict, f, sort_keys=True, indent=2)
