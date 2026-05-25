class ContainerResolver:
    def __init__(self, site_name: str):
        self.site_name = site_name

    def _slug(self) -> str:
        return self.site_name.replace(".", "_").replace("-", "_").upper()


r = ContainerResolver("ocoron.com")
print(r._slug())
