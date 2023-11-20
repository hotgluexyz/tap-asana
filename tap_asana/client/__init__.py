from urllib.parse import urlencode
from asana import Client

from asana.resources.teams import Teams

class CustomTeams(Teams):
    def find_all(self, **options):
        return self.client.get("/teams", query=options)


class AsanaClient(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setattr(self, "teams", CustomTeams(self))
