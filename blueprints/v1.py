import quart
from quart_discord import requires_authorization
from jinja2 import TemplateNotFound
import json

v1_api = quart.Blueprint("v1", __name__, template_folder="../templates", url_prefix="/v1")

@v1_api.route("/reset-token", methods=["POST"])
@requires_authorization
async def reset_token():
    provided = quart.request.headers.get("Authorization")
    if provided == (await quart.current_app.discord.get_authorization_token())["access_token"]:
        return quart.Response(json.dumps({"t": "objxyz"}), mimetype="application/json")